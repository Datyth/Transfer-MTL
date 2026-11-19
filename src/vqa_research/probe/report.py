"""Dev-only pilot tables, hierarchical contrasts and standalone research figures."""
import json
import itertools
import numpy as np
import pandas as pd

from gqa_audit.evaluation import (load_subsets, point_metrics, probabilistic_metrics,
                                 cluster_intervals, probabilistic_cluster_intervals, paired_contrast,
                                 seed_primary_interval)
from .data import PilotData, TASKS
from .features import ROOT
from .gates import gate_table, select_metric
from .train import _atomic_json, complete
from .train import run_id
from .transfer import phase_plan, transfer_plan, selected_recipe


def primary_frame(data, task, predictions):
    ids = data.membership[task]["dev"]
    if task == "verifyRel":
        ids = load_subsets(data.root / "gqa_audit/outputs/stage2b/analysis_subsets.json")["subsets"][
            "verifyRel_relation"]["program_strict"][task]["dev"]
    frame = data.by_id.loc[ids, ["answer", "image_id", "part"]].reset_index().rename(columns={"image_id": "imageId"})
    merged = frame.merge(predictions, on="question_id", validate="one_to_one")
    if len(merged) != len(ids) or not merged.part.eq("dev").all():
        raise ValueError("Missing dev primary-scope IDs")
    return merged


def summarize(frame, task, *, intervals=True):
    balanced = task == "verifyRel"
    point = point_metrics(frame)
    result = {"primary": point["balanced_accuracy" if balanced else "accuracy"],
              **probabilistic_metrics(frame, class_balanced=balanced)}
    if intervals:
        settings = {"seed": 1000, "resamples": 2000, "level": .95}
        ci = cluster_intervals(frame, settings)
        metric = "balanced_accuracy" if balanced else "accuracy"
        result.update(primary_ci_low=ci[f"{metric}_ci_low"], primary_ci_high=ci[f"{metric}_ci_high"])
        result.update(probabilistic_cluster_intervals(frame, settings, class_balanced=balanced))
    return result


def load_phase(phase, data):
    output = data.root / "gqa_audit/outputs/stage3_5"
    manifest = json.loads((output / f"{phase}_manifest.json").read_text())
    expected = {"curves": 85, "blank": 25, "transfer": 99}[phase]
    if len(manifest["runs"]) != expected:
        raise ValueError(f"Incomplete {phase}: {len(manifest['runs'])}/{expected}")
    planned = (transfer_plan(selected_recipe(data.root))[1] if phase == "transfer" else
               phase_plan(phase, selected_recipe(data.root)))
    if {entry["run_id"] for entry in manifest["runs"]} != {run_id(config) for config in planned}:
        raise ValueError(f"Manifest does not match frozen {phase} plan")
    entries = []
    for entry in manifest["runs"]:
        config = entry["config"]
        path = output / "runs" / entry["run_id"]
        ids = data.membership[config["task"]]["dev"]
        if not complete(path, config, ids):
            raise ValueError(f"Incomplete run: {path}")
        frame = primary_frame(data, config["task"], pd.read_parquet(path / "predictions.parquet"))
        entries.append({**entry, "frame": frame, "record": json.loads((path / "run.json").read_text())})
    return entries, manifest


def build_report(root=ROOT):
    output = root / "gqa_audit/outputs/stage3_5"
    data = PilotData(root)
    curves, _ = load_phase("curves", data)
    blank, _ = load_phase("blank", data)
    transfer, transfer_manifest = load_phase("transfer", data)
    tables = {}
    for name, phase in (("curves", curves), ("blank", blank)):
        rows = [{**entry["config"], **summarize(entry["frame"], entry["config"]["task"])} for entry in phase]
        tables[name] = pd.DataFrame(rows)
        tables[name].to_csv(output / f"{name}_metrics.csv", index=False)
    gates = gate_table(tables["curves"], tables["blank"], root)
    gates.to_csv(output / "gates.csv", index=False)
    contrasts, contrast_rows = [], []
    def contrast(name, task, arms, controls):
        result = paired_contrast(arms, controls, sorted(arms), class_balanced=task == "verifyRel")
        contrasts.append(result)
        contrast_rows.append({"contrast": name, "task": task,
                              **{f"{metric}_{stat}": value for metric, values in result.items()
                                 for stat, value in values.items()}})
    for task in TASKS:
        for high, low in ((1000, 250), (4000, 1000)):
            arms = {e["config"]["seed"]: e["frame"] for e in curves
                    if e["config"]["task"] == task and e["config"]["budget"] == high}
            controls = {e["config"]["seed"]: e["frame"] for e in curves
                        if e["config"]["task"] == task and e["config"]["budget"] == low}
            contrast(f"{high}_vs_{low}", task, arms, controls)
    groups = {}
    controls = {}
    for entry in transfer:
        config = entry["config"]
        if "arm" not in config:
            controls.setdefault(config["task"], {})[config["seed"]] = entry["frame"]
        else:
            groups.setdefault((config["task"], config["arm"], config["source"]), {})[config["seed"]] = entry["frame"]
    for (task, arm, source), arms in groups.items():
        contrast(f"{arm}:{source}_vs_B", task, arms, controls[task])
    pd.DataFrame(contrast_rows).to_csv(output / "contrasts.csv", index=False)
    metric = select_metric(contrasts)
    _atomic_json(output / "metric_selection.json", metric)
    zero = []
    for identifier in transfer_manifest["sources"]:
        path = output / "runs" / identifier
        config = json.loads((path / "run.json").read_text())["config"]
        for task in TASKS:
            frame = primary_frame(data, task, pd.read_parquet(path / "predictions.parquet"))
            zero.append({"source": config["source"], "seed": config["seed"], "task": task, **summarize(frame, task)})
    pd.DataFrame(zero).to_csv(output / "Z_metrics.csv", index=False)
    qwen_rows = []
    for path in (output / "qwen_runs").glob("*/run.json"):
        record = json.loads(path.read_text())
        config = record["config"]
        if complete(path.parent, config, data.membership["compare"]["dev"]):
            frame = primary_frame(data, "compare", pd.read_parquet(path.parent / "predictions.parquet"))
            metrics = summarize(frame, "compare")
            qwen_rows.append({**config, **metrics, "gain_vs_stage3": metrics["primary"] - .7214,
                              **{key: record[key] for key in ("training_seconds", "evaluation_seconds",
                                                              "examples_per_second", "peak_gpu_bytes")}})
    if len(qwen_rows) != 4 or {(row["budget"], row["seed"]) for row in qwen_rows} != {
            (budget, seed) for budget in (1000, 4000) for seed in (1000, 1001)}:
        raise ValueError("Report requires four complete Qwen runs")
    pd.DataFrame(qwen_rows).to_csv(output / "qwen_metrics.csv", index=False)
    timings = []
    for phase, entries in (("P2", curves), ("P3", blank), ("P4", transfer)):
        timings.extend({"phase": phase, "budget": e["config"]["budget"],
                        "seconds": e["record"]["training_seconds"] + e["record"]["evaluation_seconds"],
                        "examples_per_second": e["record"]["examples_per_second"]} for e in entries)
    timing = pd.DataFrame(timings)
    timing.to_csv(output / "timings.csv", index=False)
    timing_summary = timing.groupby(["phase", "budget"]).agg(
        median_seconds=("seconds", "median"), p90_seconds=("seconds", lambda values: values.quantile(.9)),
        median_examples_per_second=("examples_per_second", "median"))
    timing_summary.to_csv(output / "timing_summary.csv")
    # Per-budget tables retain seed points; CIs above are clustered per seed.
    summary = tables["curves"].groupby(["task", "budget"]).primary.agg(["mean", "std", "count"])
    for (task, budget), group in summary.iterrows():
        frames = [e["frame"] for e in curves if e["config"]["task"] == task and str(e["config"]["budget"]) == str(budget)]
        interval = seed_primary_interval(frames, class_balanced=task == "verifyRel")
        for key, value in interval.items():
            summary.loc[(task, budget), key] = value
    summary.to_csv(output / "learning_curve_summary.csv")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    def save(fig, name):
        fig.tight_layout()
        fig.savefig(figures / f"{name}.png", dpi=200)
        fig.savefig(figures / f"{name}.pdf")
        plt.close(fig)
    fig, axes = plt.subplots(1, 5, figsize=(17, 3))
    for axis, task in zip(axes, TASKS):
        frame = tables["curves"][tables["curves"].task == task]
        for i, budget in enumerate((250, 1000, 4000, "full")):
            values = frame[frame.budget.astype(str) == str(budget)].primary
            axis.scatter([i] * len(values), values)
            axis.plot(i, values.mean(), "k_")
        axis.set(title=task, xticks=range(4), xticklabels=[250, 1000, 4000, "full"], ylim=(0, 1))
    save(fig, "learning_curves")
    fig, axis = plt.subplots(figsize=(8, 4))
    axis.bar(np.arange(5) - .2, gates.full, .4, label="image")
    axis.bar(np.arange(5) + .2, gates.blank_full, .4, label="blank")
    axis.set_xticks(np.arange(5), gates.task)
    axis.legend()
    save(fig, "image_reliance")
    forest = pd.DataFrame(contrast_rows).iloc[10:]
    fig, axis = plt.subplots(figsize=(10, 12))
    mean = forest.primary_gain_mean.to_numpy()
    axis.errorbar(mean, range(len(forest)), xerr=[np.maximum(0, mean - forest.primary_gain_ci_low),
                   np.maximum(0, forest.primary_gain_ci_high - mean)], fmt="o")
    axis.set_yticks(range(len(forest)), forest.task + ":" + forest.contrast)
    axis.axvline(0, color="gray")
    save(fig, "transfer_forest")
    fig, axis = plt.subplots()
    axis.hist(timing.seconds, bins=30)
    axis.set(xlabel="Train + evaluation seconds", ylabel="Runs")
    save(fig, "runtime_distribution")
    short = timing[timing.budget.astype(str) != "full"].seconds.median()
    qwen_seconds = np.mean([r["training_seconds"] + r["evaluation_seconds"] for r in qwen_rows])
    costs = {"task_matrix_3_seeds_hours": float(816 * short / 3600),
             "task_matrix_5_seeds_hours": float(1360 * short / 3600),
             "qwen_93_trainings_hours": float(93 * qwen_seconds / 3600),
             "assumption": "median measured short run; Qwen mean of four pilot budgets; family projection pending matched-size timing"}
    joint = [e for e in transfer if e["config"].get("arm") == "Joint"]
    if joint:
        per_example = np.median([e["record"]["training_seconds"] / e["record"]["examples_seen"] for e in joint])
        epochs = joint[0]["config"]["epochs"]
        evaluation_median = np.median([e["record"]["evaluation_seconds"] for e in joint])
        costs["family_matrix_630_hours"] = float(630 * (2500 * epochs * per_example + evaluation_median) / 3600)
        costs["assumption"] = "Task: median measured short run. Family: 2000 source + 500 target at measured Joint seconds/example, same E and median eval. Qwen: mean measured four runs, eval batch 1."
    _atomic_json(output / "cost_projection.json", costs)
    recipe_table = pd.read_csv(output / "recipe_selection.csv")
    parameter_counts = {}
    for text_setting in (False, True):
        identifier = recipe_table[recipe_table.train_text == text_setting].iloc[0].run_id
        parameter_counts["trainable_text" if text_setting else "frozen_text"] = json.loads(
            (output / "runs" / identifier / "run.json").read_text())["parameters"]
    report = ["# Stage 3.5 pilot report", "Dev only; exploratory pilot. Gates never change the protocol.",
              "## Preflight", (output / "preflight.json").read_text(),
              "## Feature manifest", (root / "data/features/clip_vitb16_224/manifest.json").read_text(),
              "## Probe parameters", str(parameter_counts),
              "## P1 grid", recipe_table.to_string(index=False),
              "## Selected recipe", (output / "selected_recipe.json").read_text(),
              "## Learning curves", summary.to_string(),
              "## Blank-image text floor", tables["blank"].to_string(index=False),
              "## Gates and text floors", gates.to_string(index=False),
              "## Transfer contrasts", forest.to_string(index=False), "## Z", pd.DataFrame(zero).to_string(index=False),
              "Seq and Joint see more examples than B; self is the compute-matched control.",
              "## Metric selection", str(metric), "## Qwen", pd.DataFrame(qwen_rows).to_string(index=False),
              "## Nondeterminism", (output / "repeat.json").read_text(),
              "## Timings", timing_summary.to_string(),
              "## Cost projections", str(costs), "## Open decisions for the human",
              "If G1 or G2 flags: decide whether to use pre-specified F1, CLIP ViT-L/14 at 224.",
              "Review measured timing assumptions before freezing the main study."]
    (output / "PILOT_REPORT.md").write_text("\n\n".join(report) + "\n")
