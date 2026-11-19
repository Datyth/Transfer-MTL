"""Preflight and measured P1 cost checkpoint. Frozen YAML always wins."""
import json
import math
import numpy as np
import pandas as pd
import yaml
from gqa_audit.stage2_core import file_hash, canonical_hash
from gqa_audit.evaluation import load_registry, load_subsets
from .features import ROOT
from .train import _atomic_json


PILOT_HASH = "6a4581783f269f93d1e92bfc6f47f490eb1f08fe66c0f059f57c89284e0a9793"


def preflight(root=ROOT):
    path = root / "configs/pilot_protocol.FROZEN.yaml"
    if file_hash(path) != PILOT_HASH:
        raise ValueError("STOP: pilot protocol hash mismatch")
    protocol = yaml.safe_load(path.read_text())
    registry, subsets = load_registry(), load_subsets()
    applies = protocol["applies_to"]
    if registry["registry_sha256"] != applies["registry_sha256"]:
        raise ValueError("STOP: registry hash mismatch")
    for name, file in (("analysis_plan", "gqa_audit/config/analysis_plan.FROZEN.yaml"),
                       ("stage3_protocol", "configs/stage3_protocol.FROZEN.yaml")):
        if file_hash(root / file) != applies[f"{name}_sha256"]:
            raise ValueError(f"STOP: {name} hash mismatch")
    manifest = json.loads((root / "gqa_audit/outputs/stage2b/run_manifest.json").read_text())
    if subsets["analysis_subsets_sha256"] != manifest["analysis_subsets_sha256"]:
        raise ValueError("STOP: subsets hash mismatch")
    if file_hash(root / "gqa_audit/outputs/stage2b/registry_questions.parquet") != manifest["artifacts"]["registry_questions.parquet"]:
        raise ValueError("STOP: registry metadata hash mismatch")
    model_manifest = json.loads((root / "gqa_audit/outputs/stage3/model_manifest.json").read_text())["3b"]
    if model_manifest["revision"] != "66285546d2b821cf421d4f5eb2576359d3770cd3":
        raise ValueError("STOP: Qwen revision mismatch")
    for item in model_manifest["files"]:
        path = root / "checkpoints/Qwen2.5-VL-3B-Instruct" / item["path"]
        if not path.exists() or file_hash(path) != item["sha256"]:
            raise ValueError(f"STOP: Qwen local file changed: {path.name}")
    for task, sizes in {"exist": (18921, 2083), "verifyAttr": (23462, 2721),
                        "verifyRel": (50947, 5576), "compare": (15994, 1705), "logic": (101611, 11117)}.items():
        parts = registry["variants"]["program_strict"][task]
        if (len(parts["train_core"]), len(parts["dev"])) != sizes:
            raise ValueError(f"STOP: pool size mismatch: {task}")
    result = {"status": "PASS", "protocol_sha256": PILOT_HASH,
              "registry_sha256": registry["registry_sha256"], "subsets_sha256": subsets["analysis_subsets_sha256"]}
    _atomic_json(root / "gqa_audit/outputs/stage3_5/preflight.json", result)
    return result


def cost_checkpoint(root=ROOT):
    output = root / "gqa_audit/outputs/stage3_5"
    benchmark_path = output / "qwen_cost_benchmark.json"
    if not benchmark_path.exists():
        raise ValueError("STOP: run qwen-benchmark first; P1's 5.58h excludes Qwen and evaluation")
    benchmark = json.loads(benchmark_path.read_text())
    table = pd.read_csv(output / "recipe_selection.csv")
    selected = json.loads((output / "selected_recipe.json").read_text())["recipe"]
    table = table[(table.lr_fusion == selected["lr_fusion"]) &
                  (table.train_text == selected["train_text"]) & (table.epochs == selected["epochs"])]
    training_rate = float((table.training_seconds / (table.budget * table.epochs)).median())
    records = [json.loads((output / "runs" / identifier / "run.json").read_text()) for identifier in table.run_id]
    evaluation_rates = {task: float(np.median([r["evaluation_seconds"] for r in records if r["config"]["task"] == task]))
                        for task in ("exist", "verifyAttr", "verifyRel", "compare", "logic")}
    # Include all planned cells (even reused cells) as a conservative forecast.
    total_sizes = 18921 + 23462 + 50947 + 15994 + 101611
    epochs = selected["epochs"]
    p2 = 5 * 5 * 5250 * epochs + 2 * total_sizes * 10
    p3 = 5 * 3 * 4000 * epochs + 2 * total_sizes * 10
    p4_sources = 3 * (8 * 10000 + 5371) * epochs
    p4_targets = 3 * 3 * (1000 + 5 * 1000 + 4 * 11000 + 6371) * epochs
    evaluation = sum(evaluation_rates.values()) * (17 + 5 + 27)
    evaluation += sum(evaluation_rates[t] for t in ("logic", "verifyRel", "compare")) * 33
    qwen_train = (2 * (1000 + 4000) * 2) / benchmark["examples_per_second"]
    qwen_eval = 4 * 1705 / benchmark["evaluation_questions_per_second"]
    hours = (training_rate * (p2 + p3 + p4_sources + p4_targets + 1000 * epochs) +
             evaluation + evaluation_rates["compare"] + qwen_train + qwen_eval) / 3600
    result = {"projected_gpu_hours_P2_P5": hours, "qwen_training_hours": qwen_train / 3600,
              "qwen_evaluation_hours": qwen_eval / 3600,
              "assumptions": "P1 median seconds/example; end-only task evaluation; Qwen 8 optimizer steps and 32 dev questions",
              "status": "STOP" if hours > 24 else "PASS"}
    _atomic_json(output / "cost_checkpoint.json", result)
    progress = output / "PROGRESS_P1.md"
    prefix = progress.read_text().split("\n\nFull measured P2–P5 projection:")[0]
    progress.write_text(prefix + "\n\nFull measured P2–P5 projection:\n\n" + json.dumps(result, indent=2) + "\n")
    if hours > 24:
        raise ValueError(f"STOP: P2–P5 projection {hours:.2f} GPU-hours exceeds 24; human decision required")
    return result
