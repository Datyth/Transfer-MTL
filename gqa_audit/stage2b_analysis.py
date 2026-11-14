"""Diagnostic models and question-level overlap, without changing task membership."""

from __future__ import annotations

import itertools
import json
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .evaluation import point_metrics
from .stage2 import majority_label
from .stage2_core import fit_question_baseline


def dash_diagnostics(raw, context):
    frame = raw.copy()
    frame["dash"] = frame.program_json.map(lambda value: any("(-)" in s["argument"] for s in json.loads(value)))
    result = frame.groupby(["detailed", "part", "answer"], sort=True).dash.agg(n="size", n_dash="sum").reset_index()
    result["dash_rate"] = result.n_dash / result.n
    expected = {typ: 1.0 for typ in context["analysis_runtime"]["dash_expected_one"]}
    expected.update({typ: 0.0 for typ in context["analysis_runtime"]["dash_expected_zero"]})
    result["expected_dash_rate"] = result.detailed.map(expected)
    result["status"] = ["INFO" if np.isnan(e) else "PASS" if a == e else "FLAG"
                        for a, e in zip(result.dash_rate, result.expected_dash_rate)]
    frame["relate_step_share"] = frame.relation_steps / frame.program_length
    rows = []
    for (typ, answer), selected in frame[frame.part.eq("train_core")].groupby(["detailed", "answer"], sort=True):
        row = {"detailed": typ, "answer": answer, "n": len(selected)}
        for column in ("program_length", "depth", "relate_step_share"):
            row.update({f"{column}_mean": selected[column].mean(), f"{column}_median": selected[column].median(),
                        f"{column}_p10": selected[column].quantile(.1), f"{column}_p90": selected[column].quantile(.9)})
        rows.append(row)
    return result, pd.DataFrame(rows)


def structure_baselines(raw, context):
    data = raw[raw.in_program_strict].copy()
    columns = context["analysis_runtime"]["structure_features"]
    features = data[columns].astype(float).copy()
    for family in context["op_family_map"]["allowed_families"]:
        features[f"family_presence_{family}"] = data.op_families.map(lambda values: family in values).astype(float)
    features["dash_flag"] = data.any_dash.astype(float)
    if not np.isfinite(features.to_numpy()).all():
        raise ValueError("Nonfinite structure baseline features")
    settings, seed = context["runtime"]["baseline"], context["task_rules"]["seed"]
    references = context["analysis_runtime"]["structure_reference_val"]
    tolerance = context["analysis_runtime"]["baseline_reference_tolerance"]
    rows, prediction_rows = [], []
    for task in context["task_rules"]["pilot_tasks"]:
        train = data[data.task.eq(task) & data.part.eq("train_core")]
        majority = majority_label(train.answer)
        for condition in ("structure", "structure_dash"):
            names = [column for column in features if column != "dash_flag" or condition == "structure_dash"]
            model = make_pipeline(StandardScaler(), LogisticRegression(C=settings["C"], max_iter=settings["max_iter"],
                                                                       solver=settings["solver"], random_state=seed))
            model.fit(features.loc[train.index, names], train.answer)
            for part in ("dev", "val"):
                chosen = data[data.task.eq(task) & data.part.eq(part)]
                pred = model.predict(features.loc[chosen.index, names])
                metrics = point_metrics(pd.DataFrame({"answer": chosen.answer.to_numpy(), "pred": pred}))
                expected = references.get(condition, {}).get(task, np.nan) if part == "val" else np.nan
                difference = metrics["accuracy"] - expected
                rows.append({"variant": "program_strict", "task": task, "part": part, "condition": condition,
                             **metrics, "majority_accuracy": float(chosen.answer.eq(majority).mean()),
                             "majority_label": majority, "reference_accuracy": expected, "difference": difference,
                             "status": "INFO" if np.isnan(expected) else "PASS" if abs(difference) <= tolerance else "FLAG",
                             "feature_columns": json.dumps(names), "iterations": int(model[-1].n_iter_.max())})
                prediction_rows.extend({"condition": condition, "task": task, "part": part, "question_id": qid,
                                        "answer": answer, "pred": prediction}
                                       for qid, answer, prediction in zip(chosen.question_id, chosen.answer, pred))
    return pd.DataFrame(rows), pd.DataFrame(prediction_rows)


def relation_baselines(raw, predictions, subsets, context):
    settings, seed = context["runtime"]["baseline"], context["task_rules"]["seed"]
    rows, prediction_rows, recalls = [], [], []
    indexed = raw.set_index("question_id", drop=False)
    for variant in context["task_rules"]["audit_variants"]:
        for name in ("verifyRel_relation", "verifyRel_Co"):
            by_part = subsets["subsets"][name][variant]["verifyRel"]
            train = indexed.loc[by_part["train_core"]]
            model = fit_question_baseline(train.question.tolist(), train.answer.to_numpy(), settings, seed)
            majority = majority_label(train.answer)
            for part in ("dev", "val"):
                chosen = indexed.loc[by_part[part]]
                pred = model.predict(chosen.question.tolist())
                metrics = point_metrics(pd.DataFrame({"answer": chosen.answer.to_numpy(), "pred": pred}))
                rows.append({"variant": variant, "subset": name, "part": part, "train_n": len(train), **metrics,
                             "majority_accuracy": float(chosen.answer.eq(majority).mean()), "majority_label": majority,
                             "iterations": int(model[-1].n_iter_.max())})
                prediction_rows.extend({"variant": variant, "subset": name, "part": part, "question_id": qid,
                                        "answer": answer, "pred": prediction}
                                       for qid, answer, prediction in zip(chosen.question_id, chosen.answer, pred))
        pooled = predictions[predictions.variant.eq(variant) & predictions.task.eq("verifyRel")]
        pooled = pooled.merge(raw[["question_id", "detailed"]], on="question_id", validate="one_to_one")
        for (part, typ), chosen in pooled.groupby(["analysis_split", "detailed"], sort=True):
            # This is a preregistered per-class recall diagnostic, never a general
            # detailed-type accuracy table. Cop is intentionally excluded.
            if typ not in context["analysis_runtime"]["pooled_recall_reference_val"]:
                continue
            expected = context["analysis_runtime"]["pooled_recall_reference_val"][typ] if part == "val" else np.nan
            actual = float(chosen.prediction.eq(chosen.answer).mean())
            recalls.append({"variant": variant, "part": part, "detailed": typ, "n": len(chosen),
                            "class_recall": actual, "reference_recall": expected, "difference": actual - expected})
    return pd.DataFrame(rows), pd.DataFrame(recalls), pd.DataFrame(prediction_rows)


def family_flags(predictions, raw, context):
    rows = []
    minimum = context["analysis_runtime"]["minimum_family_questions"]
    margin = context["task_rules"]["thresholds"]["blind_baseline_margin_over_majority"]
    for variant in context["task_rules"]["audit_variants"]:
        train = raw[raw[f"in_{variant}"] & raw.part.eq("train_core")]
        for (part, task, family), chosen in predictions[predictions.variant.eq(variant)].groupby(
                ["analysis_split", "task", "family"], sort=True):
            reference = train[train.task.eq(task) & train.family.eq(family)]
            label = majority_label(reference.answer)
            accuracy = float(chosen.prediction.eq(chosen.answer).mean())
            majority = float(chosen.answer.eq(label).mean())
            rows.append({"variant": variant, "part": part, "task": task, "family": family, "n": len(chosen),
                         "accuracy": accuracy, "majority_accuracy": majority, "training_majority_label": label,
                         "gain_over_majority": accuracy - majority, "threshold": margin,
                         "status": "INFO" if len(chosen) < minimum else "FLAG" if accuracy - majority > margin else "PASS"})
    return pd.DataFrame(rows)


def manual_relation_samples(raw, context):
    seed = context["task_rules"]["seed"]
    n = context["analysis_runtime"]["manual_samples_per_type"]
    frame = raw[raw.in_program_strict & raw.part.eq("train_core")]
    rows = []
    for typ in context["analysis_runtime"]["manual_verifyrel_types"]:
        chosen = frame[frame.detailed.eq(typ)].sort_values("question_id")
        if len(chosen) < n:
            raise ValueError(f"Not enough manual examples: {typ}")
        chosen = chosen.iloc[np.random.default_rng(seed).choice(len(chosen), size=n, replace=False)]
        for r in chosen.itertuples():
            program = json.loads(r.program_json)
            pretty = "\n".join(f"{i}: {s['operation']} | {s['argument']} | deps={s['dependencies']}" for i, s in enumerate(program))
            rows.append({"variant": "program_strict", "sample_kind": "verifyrel_extra", "assigned_task": r.task,
                         "question_id": r.question_id, "imageId": r.image_id, "question": r.question, "answer": r.answer,
                         "detailed_type": r.detailed, "family": r.family, "stratum": r.stratum,
                         "analysis_split": r.part, "program": pretty, "R_strict": r.strict,
                         "semantic_type": r.semantic_type, "human_ok": "", "config_bundle_sha256": context["bundle"]})
    return pd.DataFrame(rows)


def question_overlap(descriptors, predictions, context):
    data = descriptors[descriptors.in_program_strict].copy()
    data["token_set"] = data.token_multiset.map(set)
    tasks = list(context["task_rules"]["pilot_tasks"])
    source_df = {}
    for task in tasks:
        source_df[task] = Counter(token for tokens in data.loc[data.task.eq(task) & data.part.eq("train_core"), "token_set"] for token in tokens)
    counts, per_question = [], []
    for source, target in itertools.permutations(tasks, 2):
        frequency = source_df[source]
        for part in ("dev", "val"):
            chosen = data[data.task.eq(target) & data.part.eq(part)]
            sharing = chosen.token_set.map(lambda tokens: bool(tokens & frequency.keys()))
            continuous = chosen.token_set.map(lambda tokens: sum(frequency[token] for token in tokens))
            counts.append({"variant": "program_strict", "source": source, "target": target, "part": part,
                           "n_target": len(chosen), "n_sharing": int(sharing.sum()), "share": float(sharing.mean())})
            per_question.append(pd.DataFrame({"question_id": chosen.question_id, "source": source, "target": target,
                                              "part": part, "shared_binary": sharing, "shared_continuous": continuous}))
    counts = pd.DataFrame(counts)
    low, high = context["analysis_runtime"]["overlap_contrast_bounds"]
    viability = counts[counts.part.eq("val")].copy()
    viability["status"] = np.where((viability.share < low) | (viability.share > high), "NO_CONTRAST", "OK")
    values = pd.concat(per_question, ignore_index=True)
    pred = predictions[predictions.variant.eq("program_strict")][["question_id", "prediction"]]
    metadata = data[["question_id", "answer", "family", "stratum", "program_length", "depth"]].merge(
        pred, on="question_id", how="left", validate="one_to_one")
    merged = values.merge(metadata, on="question_id", validate="many_to_one")
    valid = set(zip(viability.loc[viability.status.eq("OK"), "source"], viability.loc[viability.status.eq("OK"), "target"]))
    confounds, mixes = [], []
    for (source, target, part, sharing), chosen in merged.groupby(["source", "target", "part", "shared_binary"], sort=True):
        if (source, target) not in valid:
            continue
        if chosen.prediction.isna().any():
            raise ValueError("Missing blind baseline predictions for overlap control")
        key = {"source": source, "target": target, "part": part, "shared_binary": bool(sharing)}
        family_mix, stratum_mix = chosen.family.value_counts().sort_index().to_dict(), chosen.stratum.value_counts().sort_index().to_dict()
        confounds.append({**key, "n": len(chosen), "program_length_mean": chosen.program_length.mean(),
                          "depth_mean": chosen.depth.mean(), "yes_ratio": chosen.answer.eq("yes").mean(),
                          "blind_accuracy": chosen.prediction.eq(chosen.answer).mean(),
                          "family_mix": json.dumps(family_mix, sort_keys=True), "stratum_mix": json.dumps(stratum_mix, sort_keys=True)})
        for name, mix in (("family", family_mix), ("stratum", stratum_mix)):
            mixes.extend({**key, "level": name, "unit": unit, "n": n, "share": n / len(chosen)} for unit, n in mix.items())
    return counts, viability, pd.DataFrame(confounds), pd.DataFrame(mixes), values


def entailment_by_task(basic, raw, context):
    dev_images = set(json.loads((context["root"] / "gqa_audit/outputs/stage2/dev_images.json").read_text())["image_ids"])
    mapping = {}
    for split, frame in basic.items():
        mapping.update({r.question_id: (("dev" if r.image_id in dev_images else "train_core") if split == "train" else split, r.task)
                        for r in frame.itertuples()})
    mapping.update({r.question_id: (r.part, r.task) for r in raw.itertuples()})
    counts = Counter()
    for r in raw.itertuples():
        for field in ("entailed", "equivalent"):
            for target in getattr(r, field):
                part, task = mapping.get(target, ("outside_balanced_files", "unknown"))
                counts[(field, r.part, r.task, part, task, r.question_id == target,
                        part not in (r.part, "outside_balanced_files"), task != r.task and task != "unknown")] += 1
    return pd.DataFrame([{"field": field, "from_part": part, "from_task": task, "to_part": destination,
                          "to_task": target, "self_reference": same, "cross_split": cross,
                          "cross_task": different_task, "references": n}
                         for (field, part, task, destination, target, same, cross, different_task), n in sorted(counts.items())])
