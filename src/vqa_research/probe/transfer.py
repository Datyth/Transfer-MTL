"""Protocol phase plans and shared source checkpoints."""
import json
import os
from .data import TASKS, PilotData
from .features import ROOT
from .train import _atomic_json, train_run, run_id
from gqa_audit.stage2_core import canonical_hash


TARGETS = {"logic": ["exist", "compare"], "verifyRel": ["exist", "compare"],
           "compare": ["verifyAttr", "exist"]}


def selected_recipe(root=ROOT):
    value = json.loads((root / "gqa_audit/outputs/stage3_5/selected_recipe.json").read_text())
    if value["recipe_hash"] != canonical_hash(value["recipe"]):
        raise ValueError("Frozen recipe hash mismatch")
    return value["recipe"]


def config_for(recipe, task, budget, seed, blank=False, **extra):
    return {**recipe, "task": task, "budget": budget, "seed": seed, "blank": blank,
            "epochs": 10 if budget == "full" else recipe["epochs"],
            "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"], **extra}


def phase_plan(phase, recipe):
    if phase not in ("curves", "blank"):
        raise ValueError(phase)
    blank = phase == "blank"
    return [config_for(recipe, task, budget, seed, blank) for task in TASKS
            for budget in ([4000, "full"] if blank else [250, 1000, 4000, "full"])
            for seed in (range(1000, 1002) if budget == "full" else
                         range(1000, 1003) if blank else range(1000, 1005))]


def run_curves(phase, root=ROOT):
    data = PilotData(root)
    configs = phase_plan(phase, selected_recipe(root))
    entries = []
    for config in configs:
        path = train_run(config, data, root)
        entries.append({"config": config, "run_id": path.name})
        _atomic_json(root / f"gqa_audit/outputs/stage3_5/{phase}_manifest.json", {"runs": entries})
    if phase == "curves":
        original = config_for(selected_recipe(root), "compare", 1000, 1000)
        repeat = {**original, "replicate": 2}
        path = train_run(repeat, data, root)
        import pandas as pd
        import numpy as np
        baseline = pd.read_parquet(root / "gqa_audit/outputs/stage3_5/runs" / run_id(original) / "predictions.parquet")
        repeated = pd.read_parquet(path / "predictions.parquet")
        merged = baseline.merge(repeated, on="question_id", validate="one_to_one")
        difference = float(np.abs(merged.score_x - merged.score_y).max())
        _atomic_json(root / "gqa_audit/outputs/stage3_5/repeat.json",
                     {"max_logit_difference": difference, "status": "FLAG" if difference > 1e-3 else "PASS"})


def source_spec(target, source):
    if source == "self":
        return f"self:{target}"
    if source == "placebo_shuffled":
        return f"shuffled:{TARGETS[target][0]}"
    return source


def source_sample(data, target, source, seed):
    shuffled = source == "placebo_shuffled"
    name = TARGETS[target][0] if shuffled else source
    ids = data.source_ids(target, name, seed)
    labels = data.shuffled_labels(ids, seed) if shuffled else None
    if source == "self" and set(ids) & set(data.target_ids(target, 4000, seed)):
        raise ValueError("Self source overlaps target budget")
    return ids, labels


def transfer_plan(recipe):
    sources, targets = {}, []
    for seed in range(1000, 1003):
        for target, real_sources in TARGETS.items():
            targets.append(config_for(recipe, target, 1000, seed))
            for source in [*real_sources, "placebo_global", "placebo_shuffled", "self"]:
                spec = source_spec(target, source)
                key = (spec, seed)
                sources[key] = config_for(recipe, "source", 1000, seed, source=spec, arm="source")
                for arm in ("Seq", "Joint"):
                    targets.append(config_for(recipe, target, 1000, seed, source=spec, arm=arm))
    assert len(sources) == 27 and len(targets) == 99
    return sources, targets


def run_transfer(root=ROOT):
    recipe, data = selected_recipe(root), PilotData(root)
    source_configs, target_configs = transfer_plan(recipe)
    all_dev = [qid for task in TASKS for qid in data.membership[task]["dev"]]
    done_sources, entries = {}, []
    for config in target_configs:
        target, seed = config["task"], config["seed"]
        target_ids = data.target_ids(target, 1000, seed)
        if "source" not in config:
            path = train_run(config, data, root)
        else:
            spec = config["source"]
            source = ("self" if spec.startswith("self:") else "placebo_shuffled"
                      if spec.startswith("shuffled:") else spec)
            ids, labels = source_sample(data, target, source, seed)
            key = (spec, seed)
            source_config = source_configs[key]
            if key not in done_sources:
                # Source identity contains no target for shared real/placebo sources.
                done_sources[key] = train_run(source_config, data, root, training_ids=ids,
                    evaluation_ids=all_dev, labels=labels, save_checkpoint=True).name
            if config["arm"] == "Seq":
                checkpoint = root / "checkpoints/probe_pilot" / f"{done_sources[key]}.pt"
                path = train_run(config, data, root, training_ids=target_ids, initial_checkpoint=checkpoint)
            else:
                path = train_run(config, data, root, training_ids=ids + target_ids, labels=labels)
        entries.append({"config": config, "run_id": path.name})
        _atomic_json(root / "gqa_audit/outputs/stage3_5/transfer_manifest.json",
                     {"runs": entries, "sources": list(done_sources.values())})
