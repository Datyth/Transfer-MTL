"""Frozen H-L scoring for later experiments; testdev requires explicit final mode."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .stage2_core import canonical_hash, file_hash, fit_question_baseline, load_frozen
from .stage2b_data import ROOT, REGISTRY_SHA256, load_plan, read_hashed_json


def load_registry(path: Path | None = None) -> dict:
    return read_hashed_json(Path(path) if path else ROOT / "gqa_audit/outputs/stage2/task_registry.json",
                            "registry_sha256", REGISTRY_SHA256)


def load_subsets(path: Path | None = None) -> dict:
    result = read_hashed_json(Path(path) if path else ROOT / "gqa_audit/outputs/stage2b/analysis_subsets.json",
                              "analysis_subsets_sha256")
    if result["registry_sha256"] != REGISTRY_SHA256:
        raise ValueError("Analysis subsets reference a different registry")
    from .stage2b_data import PLAN_SHA256
    if result.get("analysis_plan_sha256") != PLAN_SHA256:
        raise ValueError("Analysis subsets reference a different H-L plan")
    return result


def point_metrics(frame: pd.DataFrame) -> dict:
    n = len(frame)
    if not n:
        return {"n": 0, "accuracy": np.nan, "balanced_accuracy": np.nan, "yes_prediction_rate": np.nan,
                "yes_recall": np.nan, "no_recall": np.nan}
    yes, no = frame.answer.eq("yes"), frame.answer.eq("no")
    correct = frame.pred.eq(frame.answer)
    yes_recall = float(correct[yes].mean()) if yes.any() else np.nan
    no_recall = float(correct[no].mean()) if no.any() else np.nan
    balanced = (yes_recall + no_recall) / 2 if yes.any() and no.any() else np.nan
    return {"n": n, "accuracy": float(correct.mean()), "balanced_accuracy": balanced,
            "yes_prediction_rate": float(frame.pred.eq("yes").mean()),
            "yes_recall": yes_recall, "no_recall": no_recall}


def probabilistic_metrics(frame: pd.DataFrame, *, class_balanced=False) -> dict:
    """Pilot log-loss and score AUROC, with decision-H class balancing."""
    from sklearn.metrics import roc_auc_score
    if not {"answer", "p_yes", "score"} <= set(frame):
        raise ValueError("Probability metrics require answer, p_yes and score")
    yes = frame.answer.eq("yes").to_numpy()
    if not frame.answer.isin(("yes", "no")).all() or len(frame) == 0:
        raise ValueError("Probability metrics require binary labels and nonempty data")
    probabilities = frame.p_yes.to_numpy(dtype=np.float64)
    scores = frame.score.to_numpy(dtype=np.float64)
    if not np.isfinite(probabilities).all() or not np.isfinite(scores).all():
        raise ValueError("Nonfinite probability or score")
    probabilities = np.clip(probabilities, 1e-6, 1 - 1e-6)
    loss = -np.where(yes, np.log(probabilities), np.log1p(-probabilities))
    if class_balanced:
        if not yes.any() or yes.all():
            raise ValueError("Class-balanced log-loss requires both classes")
        value = (loss[yes].mean() + loss[~yes].mean()) / 2
    else:
        value = loss.mean()
    auroc = float(roc_auc_score(yes, scores)) if yes.any() and not yes.all() else np.nan
    return {"log_loss": float(value), "auroc": auroc}


def paired_contrast(arm_a, arm_c, seeds, *, class_balanced=False, bootstrap_seed=1000,
                    resamples=2000):
    """Hierarchical paired bootstrap; a single image draw shared across seeds/arms.

    Each arm is a mapping seed -> primary-scope frame containing question_id,
    imageId, answer, pred, p_yes, score. Log-loss is C minus A.
    """
    from sklearn.metrics import roc_auc_score
    seeds = list(seeds)
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Nonempty unique paired seeds required")
    first = arm_a[seeds[0]].sort_values("question_id").reset_index(drop=True)
    if first.question_id.map(type).ne(str).any() or first.question_id.duplicated().any():
        raise ValueError("Unique string question IDs required")
    if "part" in first and not first.part.eq("dev").all():
        raise ValueError("Stage 3.5 contrasts are dev-only")
    images, group = np.unique(first.imageId.to_numpy(), return_inverse=True)
    yes = first.answer.eq("yes").to_numpy()
    if not yes.any() or yes.all() or first.imageId.isna().any():
        raise ValueError("Both classes and image IDs required")
    arrays = []
    for seed in seeds:
        pair = []
        for mapping in (arm_a, arm_c):
            frame = mapping[seed].sort_values("question_id").reset_index(drop=True)
            for name in ("question_id", "imageId", "answer"):
                if frame[name].tolist() != first[name].tolist():
                    raise ValueError("Paired arms/seeds must have identical IDs, images and labels")
            if "part" in frame and not frame.part.eq("dev").all():
                raise ValueError("Stage 3.5 contrasts are dev-only")
            probabilistic_metrics(frame, class_balanced=class_balanced)
            probability = np.clip(frame.p_yes.to_numpy(dtype=float), 1e-6, 1 - 1e-6)
            pair.append((frame.pred.eq(frame.answer).to_numpy(dtype=float),
                         -np.where(yes, np.log(probability), np.log1p(-probability)),
                         frame.score.to_numpy(dtype=float)))
        arrays.append(pair)

    def metrics(values, weights):
        correct, loss, score = values
        if weights[yes].sum() == 0 or weights[~yes].sum() == 0:
            return np.full(3, np.nan)
        primary = ((np.average(correct[yes], weights=weights[yes]) +
                    np.average(correct[~yes], weights=weights[~yes])) / 2 if class_balanced else
                   np.average(correct, weights=weights))
        logloss = ((np.average(loss[yes], weights=weights[yes]) +
                    np.average(loss[~yes], weights=weights[~yes])) / 2 if class_balanced else
                   np.average(loss, weights=weights))
        return np.array([primary, logloss, roc_auc_score(yes, score, sample_weight=weights)])

    def difference(seed_indices, weights):
        return np.mean([ (metrics(arrays[i][0], weights) - metrics(arrays[i][1], weights)) *
                        np.array([1, -1, 1]) for i in seed_indices], axis=0)

    point = difference(range(len(seeds)), np.ones(len(first)))
    generator = np.random.default_rng(bootstrap_seed)
    samples = []
    for _ in range(resamples):
        drawn_seeds = generator.integers(0, len(seeds), len(seeds))
        drawn_images = generator.integers(0, len(images), len(images))
        weights = np.bincount(drawn_images, minlength=len(images))[group]
        samples.append(difference(drawn_seeds, weights))
    samples = np.asarray(samples)
    result = {}
    for column, name in enumerate(("primary_gain", "log_loss_gain", "auroc_gain")):
        finite = samples[np.isfinite(samples[:, column]), column]
        if len(finite) < 2:
            raise ValueError("Too few valid bootstrap resamples")
        low, high = np.quantile(finite, [.025, .975])
        se = float(finite.std(ddof=1))
        z = float(point[column] / se) if se else (0.0 if point[column] == 0 else float(np.copysign(np.inf, point[column])))
        result[name] = {"mean": float(point[column]), "ci_low": float(low), "ci_high": float(high),
                        "se": se, "z": z, "valid_resamples": len(finite)}
    return result


def seed_primary_interval(frames, *, class_balanced=False, seed=1000, resamples=2000):
    """CI of mean seed performance, resampling seeds and shared image clusters."""
    ordered = [frame.sort_values("question_id").reset_index(drop=True) for frame in frames]
    first = ordered[0]
    _, inverse = np.unique(first.imageId, return_inverse=True)
    groups = int(inverse.max()) + 1
    yes = first.answer.eq("yes").to_numpy()
    correct = []
    for frame in ordered:
        if frame.question_id.tolist() != first.question_id.tolist() or frame.imageId.tolist() != first.imageId.tolist():
            raise ValueError("Seed CI requires paired question/image sets")
        if "part" in frame and not frame.part.eq("dev").all():
            raise ValueError("Stage 3.5 intervals are dev-only")
        correct.append(frame.pred.eq(frame.answer).to_numpy(dtype=float))
    correct = np.asarray(correct)
    generator, samples = np.random.default_rng(seed), []
    for _ in range(resamples):
        selected = generator.integers(0, len(correct), len(correct))
        weights = np.bincount(generator.integers(0, groups, groups), minlength=groups)[inverse]
        if class_balanced:
            if weights[yes].sum() == 0 or weights[~yes].sum() == 0:
                continue
            values = (np.average(correct[selected][:, yes], axis=1, weights=weights[yes]) +
                      np.average(correct[selected][:, ~yes], axis=1, weights=weights[~yes])) / 2
        else:
            values = np.average(correct[selected], axis=1, weights=weights)
        samples.append(values.mean())
    low, high = np.quantile(samples, [.025, .975])
    return {"ci_low": float(low), "ci_high": float(high)}


def study_contrast(arms, controls, *, balanced=False, delta=0., metric='primary',
                   resamples=2000, bootstrap_seed=1000):
    """Main-study paired bootstrap over initializations and image clusters.

    Keep the pilot's dev-only API unchanged. This explicit study API permits dev
    or val, never testdev. Aggregate additive metrics by image before resampling.
    AUROC is secondary and reported as a point difference, not a bootstrap CI.
    One-sided centered-bootstrap tests evaluate effects beyond +/- delta.
    """
    if metric not in ('primary', 'log_loss') or len(arms) != len(controls) or not arms:
        raise ValueError('Invalid paired study contrast')
    first = arms[0].sort_values('question_id').reset_index(drop=True)
    if (not len(first) or first.question_id.duplicated().any()
            or first.question_id.map(type).ne(str).any()
            or first.imageId.isna().any() or not first.part.isin(['dev', 'val']).all()
            or first.part.nunique() != 1):
        raise ValueError('Study frames require unique dev/val IDs')
    yes = first.answer.eq('yes').to_numpy()
    if not yes.any() or yes.all():
        raise ValueError('Study contrast requires both answer classes')
    _, groups = np.unique(first.imageId.to_numpy(), return_inverse=True)
    n_groups = int(groups.max()) + 1
    denominator = np.stack([np.bincount(groups, weights=mask, minlength=n_groups)
                            for mask in ((yes, ~yes) if balanced else (np.ones(len(first)),))])
    differences, auc = [], []
    for a, c in zip(arms, controls):
        pair = []
        for f in (a, c):
            f = f.sort_values('question_id').reset_index(drop=True)
            if not f[['question_id', 'imageId', 'answer', 'part']].equals(
                    first[['question_id', 'imageId', 'answer', 'part']]):
                raise ValueError('Study arms must use identical IDs, labels and split')
            m = probabilistic_metrics(f, class_balanced=balanced)
            p = np.clip(f.p_yes.to_numpy(dtype=float), 1e-6, 1 - 1e-6)
            value = (f.pred.eq(f.answer).to_numpy(dtype=float) if metric == 'primary' else
                     np.where(yes, np.log(p), np.log1p(-p)))
            pair.append((value, m['auroc']))
        diff = pair[0][0] - pair[1][0]
        differences.append(np.stack([np.bincount(groups, weights=diff * mask, minlength=n_groups)
                                    for mask in ((yes, ~yes) if balanced else (np.ones(len(first)),))]))
        auc.append(pair[0][1] - pair[1][1])
    differences = np.asarray(differences)
    points = (differences.sum(axis=-1) / denominator.sum(axis=-1)).mean(axis=-1)
    generator = np.random.default_rng(bootstrap_seed)
    samples = []
    for _ in range(resamples):
        selected = generator.integers(0, len(arms), len(arms))
        weights = np.bincount(generator.integers(0, n_groups, n_groups), minlength=n_groups)
        den = denominator @ weights
        if (den == 0).any():
            continue
        samples.append(float(((differences[selected].mean(axis=0) @ weights) / den).mean()))
    samples = np.asarray(samples)
    if len(samples) < 2:
        raise ValueError('Insufficient bootstrap draws')
    mean = float(points.mean())
    low, high = np.quantile(samples, [.025, .975])
    error = samples - mean
    se = float(samples.std(ddof=1))
    return {'mean': mean, 'ci_low': float(low), 'ci_high': float(high), 'se': se,
            'z': mean / se if se else (0. if mean == 0 else float(np.sign(mean) * np.inf)),
            'positive_fraction': float((points > 0).mean()),
            'negative_fraction': float((points < 0).mean()), 'auroc_gain': float(np.mean(auc)),
            'p_positive': float((1 + (error >= mean - delta - 1e-12).sum()) / (len(error) + 1)),
            'p_negative': float((1 + (-error >= -mean - delta - 1e-12).sum()) / (len(error) + 1)),
            'valid_resamples': len(samples)}


def probabilistic_cluster_intervals(frame: pd.DataFrame, settings: dict, *, class_balanced=False) -> dict:
    """Image-cluster percentile intervals for probabilistic pilot metrics."""
    if frame.imageId.isna().any():
        raise ValueError("Image IDs are required for confidence intervals")
    clusters = [group for _, group in frame.groupby("imageId", sort=True)]
    generator = np.random.default_rng(settings["seed"])
    samples = []
    for _ in range(settings["resamples"]):
        draw = generator.integers(0, len(clusters), size=len(clusters))
        sampled = pd.concat([clusters[i] for i in draw], ignore_index=True)
        try:
            metric = probabilistic_metrics(sampled, class_balanced=class_balanced)
            samples.append((metric["log_loss"], metric["auroc"]))
        except ValueError:
            samples.append((np.nan, np.nan))
    values = np.asarray(samples)
    tail = (1 - settings["level"]) / 2
    result = {}
    for column, name in enumerate(("log_loss", "auroc")):
        finite = values[np.isfinite(values[:, column]), column]
        result[f"{name}_ci_low"], result[f"{name}_ci_high"] = (
            map(float, np.quantile(finite, [tail, 1 - tail])) if len(finite) else (np.nan, np.nan))
    return result


def cluster_intervals(frame: pd.DataFrame, settings: dict, *, return_samples=False):
    """Sample images with replacement, retaining every question of each image."""
    names = ("accuracy", "balanced_accuracy", "yes_prediction_rate")
    if not len(frame):
        result = {**{f"{name}_ci_{side}": np.nan for name in names for side in ("low", "high")},
                  "bootstrap_valid_balanced": 0, "images": 0}
        return (result, np.empty((0, 3))) if return_samples else result
    if frame.imageId.isna().any():
        raise ValueError("Image IDs are required for cluster-bootstrap confidence intervals")
    yes = frame.answer.eq("yes").to_numpy()
    correct = frame.pred.eq(frame.answer).to_numpy()
    work = pd.DataFrame({"imageId": frame.imageId.to_numpy(), "n": 1, "correct": correct.astype(int),
                         "yes": yes.astype(int), "yes_correct": (yes & correct).astype(int),
                         "no": (~yes).astype(int), "no_correct": (~yes & correct).astype(int),
                         "pred_yes": frame.pred.eq("yes").to_numpy().astype(int)})
    clusters = work.groupby("imageId", sort=True).sum().to_numpy(dtype=np.int64)
    rng, samples = np.random.default_rng(settings["seed"]), []
    groups = len(clusters)
    for start in range(0, settings["resamples"], 32):
        indices = rng.integers(0, groups, size=(min(32, settings["resamples"] - start), groups))
        totals = clusters[indices].sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            samples.append(np.column_stack((totals[:, 1] / totals[:, 0],
                                            (totals[:, 3] / totals[:, 2] + totals[:, 5] / totals[:, 4]) / 2,
                                            totals[:, 6] / totals[:, 0])))
    values = np.vstack(samples)
    tail = (1 - settings["level"]) / 2
    result = {"images": groups, "bootstrap_valid_balanced": int(np.isfinite(values[:, 1]).sum())}
    for i, name in enumerate(names):
        finite = values[np.isfinite(values[:, i]), i]
        low, high = np.quantile(finite, [tail, 1 - tail]) if len(finite) else (np.nan, np.nan)
        result.update({f"{name}_ci_low": float(low), f"{name}_ci_high": float(high)})
    # Identical paired image sets and seed produce the same bootstrap draws.
    # Expose existing draws so later experiments can calculate paired differences
    # without duplicating metric or resampling implementations.
    return (result, values) if return_samples else result


class Evaluator:
    def __init__(self, root: Path = ROOT, *, metadata=None, registry=None, subsets=None, plan=None, questions=None,
                 mode=None):
        if mode not in (None, "stage3_5"):
            raise ValueError("Unknown evaluation mode")
        self.mode = mode
        self.root = Path(root)
        self.registry = registry if registry is not None else load_registry(self.root / "gqa_audit/outputs/stage2/task_registry.json")
        self.subsets = subsets if subsets is not None else load_subsets(self.root / "gqa_audit/outputs/stage2b/analysis_subsets.json")
        self.plan = plan if plan is not None else load_plan(self.root)
        if metadata is None:
            output = self.root / "gqa_audit/outputs/stage2b"
            manifest = json.loads((output / "run_manifest.json").read_text())
            if file_hash(output / "registry_questions.parquet") != manifest["artifacts"]["registry_questions.parquet"]:
                raise ValueError("Evaluation registry metadata hash mismatch")
            if self.subsets["analysis_subsets_sha256"] != manifest["analysis_subsets_sha256"]:
                raise ValueError("Evaluation subset hash differs from run manifest")
            self.metadata = pq.read_table(output / "registry_questions.parquet").to_pandas()
        else:
            self.metadata = metadata.copy()
        if self.metadata.question_id.map(type).ne(str).any() or self.metadata.question_id.duplicated().any():
            raise ValueError("Registry metadata requires unique string question IDs")
        self.questions = Path(questions) if questions else self.root / "data/gqa/questions"
        self._metrics_cache = {}
        self._final_cache = {}

    def _metrics(self, frame):
        # Cache identical units across the two variants without changing any sample.
        ordered = frame.sort_values("question_id").reset_index(drop=True)
        key = canonical_hash(ordered[["question_id", "imageId", "answer", "pred"]].to_dict("split"))
        if key not in self._metrics_cache:
            self._metrics_cache[key] = {**point_metrics(ordered), **cluster_intervals(
                ordered, self.plan["metrics"]["confidence_intervals"])}
        return self._metrics_cache[key].copy()

    def _unseal(self, variant):
        """Only called by evaluate(..., final=True) when testdev is requested."""
        if variant in self._final_cache:
            return self._final_cache[variant]
        from .stage1 import iter_records
        from .stage2b_data import checked_predictions, load_analysis_tables
        context = load_frozen(self.root / "gqa_audit/config")
        test_path = self.questions / "testdev_balanced_questions.json"
        if file_hash(test_path) != self.registry["input_hashes"]["testdev"]:
            raise ValueError("Final testdev input hash differs from registry")
        rows = self.metadata[self.metadata.part.eq("testdev") & self.metadata[f"in_{variant}"]].copy()
        expected = set(rows.question_id)
        details = {}
        for qid, record in iter_records(test_path):
            if qid in expected:
                details[qid] = {"imageId": record["imageId"], "answer": record["answer"].strip().lower(),
                                "question": record["question"], "detailed": record["types"]["detailed"]}
        if set(details) != expected:
            raise ValueError("Final testdev metadata incomplete")
        for column in ("imageId", "answer", "question", "detailed"):
            rows[column] = rows.question_id.map(lambda qid: details[qid][column])
        final_subsets = {}
        for name, definition in self.plan["subsets"].items():
            if name == "text_hard":
                continue
            chosen = rows[rows.task.eq(definition["task"])]
            if "detailed_types" in definition:
                chosen = chosen[chosen.detailed.isin(definition["detailed_types"])]
            else:
                rule = definition["exclude_if"]
                chosen = chosen[~(chosen.family.eq(rule["family"]) & chosen.question.str.contains(rule["question_regex"], regex=True))]
            final_subsets[name] = set(chosen.question_id)
        # Reproduce the frozen baseline exactly before defining final text-hard IDs.
        raw, _, _ = load_analysis_tables(self.root, context, self.registry)
        baseline = checked_predictions(self.root / "gqa_audit/outputs/stage2/blind_predictions.csv", raw, self.registry)
        hard = set()
        for task in self.registry["variants"][variant]:
            train = raw[raw[f"in_{variant}"] & raw.part.eq("train_core") & raw.task.eq(task)]
            model = fit_question_baseline(train.question.tolist(), train.answer.to_numpy(),
                                          context["runtime"]["baseline"], context["task_rules"]["seed"])
            recorded = baseline[baseline.variant.eq(variant) & baseline.task.eq(task)]
            evaluation = raw.set_index("question_id").loc[recorded.question_id]
            if model.predict(evaluation.question.tolist()).tolist() != recorded.prediction.tolist():
                raise ValueError("Final baseline refit did not reproduce frozen dev/val predictions")
            chosen = rows[rows.task.eq(task)]
            if len(chosen):
                predicted = model.predict(chosen.question.tolist())
                hard.update(chosen.loc[predicted != chosen.answer.to_numpy(), "question_id"])
        final_subsets["text_hard"] = hard
        self._final_cache[variant] = rows, final_subsets
        return rows, final_subsets

    def evaluate(self, predictions, variant, parts, final=False):
        parts = [parts] if isinstance(parts, str) else list(parts)
        if self.mode == "stage3_5" and any(part != "dev" for part in parts):
            raise ValueError("Stage 3.5 evaluation is dev-only")
        if not parts or len(set(parts)) != len(parts) or not set(parts) <= {"train_core", "dev", "val", "testdev"}:
            raise ValueError("Invalid or duplicate evaluation parts")
        if "testdev" in parts and not final:
            raise ValueError("testdev is sealed; explicit final=True is required")
        if variant not in self.registry["variants"]:
            raise ValueError("Unknown registry variant")
        prediction = pd.DataFrame(predictions).copy()
        if not {"question_id", "pred"} <= set(prediction):
            raise ValueError("Predictions require question_id and pred")
        if prediction.question_id.map(type).ne(str).any() or prediction.question_id.duplicated().any():
            raise ValueError("Duplicate or non-string prediction IDs")
        if not prediction.pred.isin(["yes", "no"]).all():
            raise ValueError("Predictions must be yes/no strings")
        if "p_yes" in prediction and (prediction.p_yes.isna().any() or not prediction.p_yes.between(0, 1).all()):
            raise ValueError("p_yes must be finite and within [0,1]")
        expected = {qid for task in self.registry["variants"][variant].values() for part in parts for qid in task[part]}
        given = set(prediction.question_id)
        if given != expected:
            raise ValueError(f"Missing/extra question IDs: missing={len(expected - given)}, extra={len(given - expected)}")
        metadata = self.metadata[self.metadata.question_id.isin(expected)].copy()
        final_subsets = {}
        if "testdev" in parts:
            unsealed, final_subsets = self._unseal(variant)
            metadata = pd.concat([metadata[~metadata.part.eq("testdev")], unsealed], ignore_index=True)
        frame = metadata.merge(prediction[["question_id", "pred"]], on="question_id", validate="one_to_one")
        if len(frame) != len(expected) or not frame.answer.isin(["yes", "no"]).all():
            raise ValueError("Missing evaluation metadata/labels")
        rows = []
        for part in parts:
            data = frame[frame.part.eq(part)]
            units = []
            if part != "testdev":
                for task, chosen in data.groupby("task", sort=True):
                    units.append(("task", task, task, chosen))
            for (task, family), chosen in data.groupby(["task", "family"], sort=True):
                if family:
                    units.append(("family", task, family, chosen))
            for (task, stratum), chosen in data.groupby(["task", "stratum"], sort=True, dropna=False):
                if isinstance(stratum, str) and stratum:
                    units.append(("stratum", task, stratum, chosen))
            # L forbids pooled testdev task/subset numbers, even in final mode.
            if part != "testdev":
                for name, variants in self.subsets["subsets"].items():
                    for task, by_part in variants.get(variant, {}).items():
                        if part in by_part:
                            chosen = data[data.question_id.isin(by_part[part])]
                            units.append(("subset", task, name, chosen))
            for level, task, unit, chosen in units:
                metrics = self._metrics(chosen)
                primary = self.plan["metrics"]["per_task_primary"][task]
                primary_frame = chosen
                scope = unit
                if "@" in primary:
                    primary, subset = primary.split("@")
                    ids = (final_subsets.get(subset, set()) if part == "testdev" else
                           set(self.subsets["subsets"][subset][variant][task].get(part, [])))
                    if unit == "verifyRel_Co":
                        # Explicitly secondary Co accuracy; no single-class intersection.
                        primary, scope = "accuracy", unit
                    else:
                        primary_frame = chosen[chosen.question_id.isin(ids)]
                        scope = f"{unit} intersect {subset}" if unit != subset else subset
                primary_metrics = self._metrics(primary_frame)
                rows.append({"variant": variant, "part": part, "level": level, "task": task, "unit": unit,
                             **metrics, "primary_metric": primary, "primary_scope": scope,
                             "primary_n": len(primary_frame), "primary_value": primary_metrics[primary],
                             "ci_low": primary_metrics[f"{primary}_ci_low"], "ci_high": primary_metrics[f"{primary}_ci_high"],
                             "primary_status": "OK" if np.isfinite(primary_metrics[primary]) else "UNDEFINED",
                             "role": "secondary" if task == "verifyRel" and unit == "verifyRel_Co" else "analysis",
                             "registry_sha256": self.registry["registry_sha256"],
                             "analysis_subsets_sha256": self.subsets["analysis_subsets_sha256"]})
        return pd.DataFrame(rows)


def evaluate(predictions, variant, parts, final=False, mode=None):
    return Evaluator(mode=mode).evaluate(predictions, variant, parts, final=final)


def shortcut_control_table(edges, root: Path = ROOT):
    """Join edge summaries; text-hard values must come from corresponding scores.

    Supply long rows with subset=main/text_hard or an explicit value_on_text_hard
    column. Missing text-hard scores are flagged rather than inferred from totals.
    """
    table = pd.DataFrame(edges).copy()
    required = {"source", "target", "condition", "metric", "value"}
    if not required <= set(table):
        raise ValueError(f"Missing edge columns: {sorted(required - set(table))}")
    if "ci" in table and "ci_low" not in table:
        table["ci_low"] = table.ci.map(lambda value: value[0])
        table["ci_high"] = table.ci.map(lambda value: value[1])
    keys = ["source", "target", "condition", "metric"]
    for extra in ("variant", "part"):
        if extra in table:
            keys.append(extra)
    if "subset" in table:
        hard = table[table.subset.eq("text_hard")][keys + ["value"]].rename(columns={"value": "value_on_text_hard"})
        if hard.duplicated(keys).any():
            raise ValueError("Duplicate text-hard edge metrics")
        table = table[~table.subset.eq("text_hard")].drop(columns=["value_on_text_hard"], errors="ignore").merge(
            hard, on=keys, how="left", validate="many_to_one")
    if "value_on_text_hard" not in table:
        table["value_on_text_hard"] = np.nan
    blind = pd.read_csv(Path(root) / "gqa_audit/outputs/stage2/blind_baseline.csv", keep_default_na=False)
    blind = blind[blind.split.eq("val") & blind.level.eq("task")]
    if "variant" not in table:
        table["variant"] = "program_strict"
    lookup = blind.set_index(["variant", "task"]).gain_over_majority.to_dict()
    table["target_blind_gain_val"] = [lookup[(v, t)] for v, t in zip(table.variant, table.target)]
    table["target_blind_gain_metric"] = "pooled_accuracy_minus_training_majority_accuracy"
    table["target_no_image_gain"] = np.nan
    table["text_hard_status"] = np.where(table.value_on_text_hard.isna(), "MISSING", "OK")
    return table
