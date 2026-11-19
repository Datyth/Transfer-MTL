"""Pre-registered P1 grid and rank selection."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from gqa_audit.evaluation import load_subsets, probabilistic_metrics
from gqa_audit.stage2_core import canonical_hash
from .data import PilotData, TASKS
from .features import ROOT
from .train import train_run


def dev_log_loss(data: PilotData, task: str, predictions: pd.DataFrame) -> float:
    ids = data.membership[task]["dev"]
    if task == "verifyRel":
        subsets = load_subsets(data.root / "gqa_audit/outputs/stage2b/analysis_subsets.json")
        ids = subsets["subsets"]["verifyRel_relation"]["program_strict"]["verifyRel"]["dev"]
    frame = (data.by_id.loc[ids, ["answer"]].reset_index()
             .merge(predictions, on="question_id", validate="one_to_one"))
    if len(frame) != len(ids):
        raise ValueError("Missing primary-scope dev predictions")
    return probabilistic_metrics(frame, class_balanced=task == "verifyRel")["log_loss"]


def grid() -> list[dict]:
    return [{"lr_fusion": lr, "train_text": train_text, "epochs": epochs}
            for lr in (0.0001, 0.0003) for train_text in (False, True) for epochs in (10, 30)]


def run_recipe(root: Path = ROOT) -> dict:
    root = Path(root)
    if not (root / "data/features/clip_vitb16_224/manifest.json").exists():
        raise RuntimeError("Complete validated feature cache required before P1")
    data = PilotData(root)
    output = root / "gqa_audit/outputs/stage3_5"
    selected_path = output / "selected_recipe.json"
    if selected_path.exists():
        selected = json.loads(selected_path.read_text())
        if selected.get("recipe_hash") != canonical_hash(selected["recipe"]):
            raise ValueError("Selected recipe hash mismatch")
        return selected
    rows = []
    for task in TASKS:
        for budget in (250, 1000, 4000):
            for recipe in grid():
                config = {"task": task, "budget": budget, "seed": 1000,
                          "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
                          "blank": False, **recipe}
                run = train_run(config, data, root)
                predictions = pd.read_parquet(run / "predictions.parquet")
                rows.append({"task": task, "budget": budget, **recipe, "run_id": run.name,
                             "dev_log_loss": dev_log_loss(data, task, predictions),
                             "training_seconds": json.loads((run / "run.json").read_text())["training_seconds"]})
    frame = pd.DataFrame(rows)
    if len(frame) != 120:
        raise ValueError("P1 must have exactly 120 runs")
    frame["rank"] = frame.groupby(["task", "budget"]).dev_log_loss.rank(method="average", ascending=True)
    frame.to_csv(output / "recipe_selection.csv", index=False)
    ranked = frame.groupby(["lr_fusion", "train_text", "epochs"])["rank"].mean().reset_index()
    ranked = ranked.sort_values(["rank", "epochs", "train_text", "lr_fusion"])
    winner = ranked.iloc[0]
    recipe = {"lr_fusion": float(winner.lr_fusion), "train_text": bool(winner.train_text),
              "epochs": int(winner.epochs)}
    result = {"recipe": recipe, "recipe_hash": canonical_hash(recipe), "mean_rank": float(winner["rank"])}
    selected_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    # A deliberately conservative lower bound: training only, excluding every
    # evaluation and all P5 Qwen work. If it exceeds 24 GPU-hours, the protocol
    # requires an immediate stop regardless of the omitted positive costs.
    selected_rows = frame[(frame.lr_fusion == recipe["lr_fusion"]) &
                          (frame.train_text == recipe["train_text"]) &
                          (frame.epochs == recipe["epochs"])]
    selected_rate = float((selected_rows.training_seconds /
                           (selected_rows.budget * selected_rows.epochs)).median())
    full_sizes = sum(len(data.membership[task]["train_core"]) for task in TASKS)
    p2_examples = 4 * 5 * sum((250, 1000, 4000)) * recipe["epochs"] + 2 * 10 * full_sizes
    p3_examples = 3 * 5 * 4000 * recipe["epochs"] + 2 * 10 * full_sizes
    p4_source_examples = 3 * (3 * 10000 + 5371 + 2 * 10000 + 3 * 10000) * recipe["epochs"]
    p4_target_examples = (9 * 1000 + 45 * 1000 + 36 * 11000 + 9 * 6371) * recipe["epochs"]
    lower_hours = selected_rate * (p2_examples + p3_examples + p4_source_examples + p4_target_examples) / 3600
    progress = ("# Stage 3.5 P1 checkpoint\n\n"
                f"Completed P1 runs: {len(frame)}. Selected recipe: {recipe}.\n\n"
                f"Median P1 training time: {frame.training_seconds.median():.1f} s; "
                f"p90: {frame.training_seconds.quantile(.9):.1f} s.\n\n"
                f"Selected-recipe median training time per example seen: {selected_rate:.6f} s.\n\n"
                f"Projected P2 to P4 training-only GPU-hours: {lower_hours:.2f}. "
                "This excludes dev evaluation, checkpoint overhead and P5 Qwen, so total P2 to P5 is higher.\n\n"
                + ("STOP: lower bound exceeds 24 GPU-hours; human decision required.\n" if lower_hours > 24
                   else "INFO: full P2 to P5 projection still requires P5 training cost estimate.\n"))
    (output / "PROGRESS_P1.md").write_text(progress)
    return result
