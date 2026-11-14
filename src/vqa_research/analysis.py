"""Use the accepted evaluator for model comparisons and paired uncertainty."""

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve

from gqa_audit.evaluation import cluster_intervals, point_metrics, shortcut_control_table
from .data import ROOT, validate_predictions

KEYS = ["variant", "part", "level", "task", "unit"]


def paired_difference(frame, settings, metric):
    """Both conditions use precisely the same image bootstrap draws."""
    left = frame.rename(columns={"pred_image": "pred"})
    right = frame.rename(columns={"pred_no_image": "pred"})
    _, left_samples = cluster_intervals(left, settings, return_samples=True)
    _, right_samples = cluster_intervals(right, settings, return_samples=True)
    index = {"accuracy": 0, "balanced_accuracy": 1, "yes_prediction_rate": 2}[metric]
    differences = left_samples[:, index] - right_samples[:, index]
    finite = differences[np.isfinite(differences)]
    tail = (1 - settings["level"]) / 2
    low, high = np.quantile(finite, [tail, 1 - tail]) if len(finite) else (np.nan, np.nan)
    return {"difference": point_metrics(left)[metric] - point_metrics(right)[metric],
            "ci_low": low, "ci_high": high, "valid_resamples": len(finite)}


def unit_frame(evaluator, frame, row, primary=True):
    chosen = frame[frame.part.eq(row.part) & frame.task.eq(row.task)]
    chosen = chosen[chosen[f"in_{row.variant}"]]
    if row.level in ("family", "stratum"):
        chosen = chosen[chosen[row.level].eq(row.unit)]
    elif row.level == "subset":
        ids = evaluator.subsets["subsets"][row.unit][row.variant][row.task].get(row.part, [])
        chosen = chosen[chosen.question_id.isin(ids)]
    if primary and row.task == "verifyRel" and row.unit != "verifyRel_Co":
        ids = evaluator.subsets["subsets"]["verifyRel_relation"][row.variant][row.task].get(row.part, [])
        chosen = chosen[chosen.question_id.isin(ids)]
    return chosen


def evaluate_variants(evaluator, predictions):
    frames = []
    for variant, tasks in evaluator.registry["variants"].items():
        ids = {qid for parts in tasks.values() for part in ("dev", "val") for qid in parts[part]}
        frames.append(evaluator.evaluate(predictions[predictions.question_id.isin(ids)], variant, ["dev", "val"]))
    return pd.concat(frames, ignore_index=True)


def reference_tables(evaluator):
    output = ROOT / "gqa_audit/outputs/stage2b"
    blind = pd.read_csv(output / "demo_eval_blind.csv", keep_default_na=False).set_index(KEYS)
    majority = pd.read_csv(output / "demo_eval_majority.csv", keep_default_na=False).set_index(KEYS)
    for table in (blind, majority):
        for name in ("primary_value", "ci_low", "ci_high"):
            table[name] = pd.to_numeric(table[name], errors="coerce")
    pred = pd.read_csv(ROOT / "gqa_audit/outputs/stage2/blind_predictions.csv", dtype={"question_id": str})
    within = pd.read_csv(output / "verifyrel_within_subset_predictions.csv", dtype={"question_id": str})
    scores = []
    for variant in evaluator.registry["variants"]:
        selected = pred[pred.variant.eq(variant)][["question_id", "prediction"]].rename(columns={"prediction": "pred"})
        replacement = within[within.variant.eq(variant) & within.subset.eq("verifyRel_relation")].set_index("question_id").pred
        selected["pred"] = selected.question_id.map(replacement).fillna(selected.pred)
        scores.append(evaluator.evaluate(selected, variant, ["dev", "val"]))
    relation = pd.concat(scores).set_index(KEYS)
    refs = blind[["primary_value", "primary_metric"]].rename(columns={"primary_value": "pooled_blind_primary"})
    refs["text_floor"] = refs.pooled_blind_primary
    refs["text_floor_source"] = "pooled_task_blind_model"
    refs["text_floor_ci_low"], refs["text_floor_ci_high"] = blind.ci_low, blind.ci_high
    use_relation = (refs.index.get_level_values("task") == "verifyRel") & (refs.index.get_level_values("unit") != "verifyRel_Co")
    # Select the reference MODEL per task, then report that same model on each
    # family/stratum/subset. Never select a new winner independently per unit.
    selected_tasks = set()
    for key, row in refs.iterrows():
        variant, part, level, task, unit = key
        if level == "task" and task == "verifyRel" and relation.loc[key, "primary_value"] > row.pooled_blind_primary:
            selected_tasks.add((variant, part, task))
    use_within = use_relation & np.array([(v, p, t) in selected_tasks for v, p, _, t, _ in refs.index])
    refs.loc[use_within, "text_floor"] = relation.primary_value.reindex(refs.index)[use_within]
    refs.loc[use_within, "text_floor_source"] = "within_subset_model_selected_per_task"
    refs.loc[use_within, "text_floor_ci_low"] = relation.ci_low.reindex(refs.index)[use_within]
    refs.loc[use_within, "text_floor_ci_high"] = relation.ci_high.reindex(refs.index)[use_within]
    refs["majority"] = majority.primary_value
    refs["majority_ci_low"] = majority.ci_low
    refs["majority_ci_high"] = majority.ci_high
    return refs.reset_index()


def calibrate_thresholds(questions, predictions):
    merged = questions[["question_id", "task", "answer", "part"]].merge(predictions[["question_id", "score"]],
                                                                          on="question_id", validate="one_to_one")
    calibrated = predictions.copy()
    choices = []
    for task, group in merged[merged.part.eq("dev")].groupby("task", sort=True):
        fpr, tpr, cuts = roc_curve(group.answer.eq("yes"), group.score, drop_intermediate=False)
        values = (tpr + 1 - fpr) / 2
        thresholds = np.nextafter(cuts, -np.inf)
        thresholds[0] = float(group.score.max())  # all-no candidate, using score > threshold
        eligible = np.flatnonzero(np.isclose(values, values.max(), rtol=0, atol=1e-12))
        best = min(eligible, key=lambda i: (abs(thresholds[i]), thresholds[i]))
        threshold = float(thresholds[best])
        ids = set(merged.loc[merged.task.eq(task), "question_id"])
        mask = calibrated.question_id.isin(ids)
        calibrated.loc[mask, "pred"] = np.where(calibrated.loc[mask, "score"].astype(np.float64) > threshold, "yes", "no")
        choices.append({"task": task, "threshold": threshold, "dev_balanced_accuracy": float(values[best]),
                        "fit_part": "dev", "fit_population": "unfiltered task union, whole task",
                        "tie_rule": "smallest absolute threshold, then lower threshold"})
    return calibrated, pd.DataFrame(choices)


def evaluate_model(evaluator, questions, image, no_image, model_name, output):
    for predictions in (image, no_image):
        validate_predictions(predictions, questions.question_id)
        if predictions.part.tolist() != questions.part.tolist():
            raise ValueError("Prediction part labels differ from frozen dev/val metadata")
    image_scores = evaluate_variants(evaluator, image)
    no_image_scores = evaluate_variants(evaluator, no_image)
    references = reference_tables(evaluator)
    image_scores["condition"] = "image"
    no_image_scores["condition"] = "no_image"
    metrics = pd.concat([image_scores, no_image_scores], ignore_index=True).merge(
        references, on=KEYS + ["primary_metric"], validate="many_to_one")
    metrics["gain_over_text_floor"] = metrics.primary_value - metrics.text_floor
    metrics["gain_over_majority"] = metrics.primary_value - metrics.majority
    metrics["model"] = model_name
    metrics.to_csv(output / f"metrics_{model_name}.csv", index=False)
    paired = questions.merge(image[["question_id", "pred"]].rename(columns={"pred": "pred_image"}),
                             on="question_id", validate="one_to_one").merge(
        no_image[["question_id", "pred"]].rename(columns={"pred": "pred_no_image"}), on="question_id", validate="one_to_one")
    differences = []
    for row in image_scores.itertuples(index=False):
        chosen = unit_frame(evaluator, paired, row)
        if len(chosen) != row.primary_n:
            raise ValueError(f"Paired unit size differs from primary metric: {row.variant}/{row.part}/{row.task}/{row.unit}")
        differences.append({**{key: getattr(row, key) for key in KEYS}, "primary_metric": row.primary_metric,
            "model": model_name, "n": len(chosen), **paired_difference(chosen,
                evaluator.plan["metrics"]["confidence_intervals"], row.primary_metric)})
    pd.DataFrame(differences).to_csv(output / f"paired_differences_{model_name}.csv", index=False)
    secondary, thresholds = [], []
    for condition, predictions in (("image", image), ("no_image", no_image)):
        calibrated, choices = calibrate_thresholds(questions, predictions)
        table = evaluate_variants(evaluator, calibrated)
        table["condition"], table["model"], table["role"] = condition, model_name, "secondary_calibrated"
        secondary.append(table)
        choices["condition"], choices["model"] = condition, model_name
        thresholds.append(choices)
    pd.concat(secondary).to_csv(output / f"calibrated_metrics_{model_name}.csv", index=False)
    pd.concat(thresholds).to_csv(output / f"thresholds_{model_name}.csv", index=False)
    # Zero-shot has no source task or transfer edges; source=none labels this honestly.
    edges = []
    for row in metrics[metrics.part.eq("val") & metrics.level.isin(["task", "subset"])].itertuples():
        if row.level == "subset" and row.unit != "text_hard":
            continue
        edges.append({"source": "none", "target": row.task, "condition": f"{model_name}_{row.condition}",
                      "variant": row.variant, "part": row.part, "metric": row.primary_metric,
                      "value": row.primary_value, "ci_low": row.ci_low, "ci_high": row.ci_high,
                      "subset": "main" if row.level == "task" else "text_hard"})
    shortcut = shortcut_control_table(edges, ROOT)
    lookup = metrics[metrics.level.eq("task") & metrics.part.eq("val") & metrics.condition.eq("no_image")].set_index(
        ["variant", "task"]).gain_over_majority.to_dict()
    shortcut["target_no_image_gain"] = [lookup[(v, t)] for v, t in zip(shortcut.variant, shortcut.target)]
    shortcut["target_no_image_gain_metric"] = "target_primary_minus_train_core_majority_primary"
    shortcut["model"] = model_name
    shortcut.to_csv(output / f"shortcut_control_{model_name}.csv", index=False)
    return metrics
