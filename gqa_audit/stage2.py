"""Stage 2 frozen audit: registry, leakage checks, blind baselines and reports."""

from __future__ import annotations

import itertools
import json
import math
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from .stage2_core import canonical_hash, choose_dev_images, file_hash, fit_question_baseline, load_frozen
from .stage2_data import build_cache, load_tables, regression_rows, retained_mask


ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "gqa_audit/config"
OUTPUT = ROOT / "gqa_audit/outputs/stage2"
ANALYSIS_SPLITS = ("train_core", "dev", "val")
ALL_SPLITS = (*ANALYSIS_SPLITS, "testdev")


def write_csv(path: Path, rows, context: dict) -> pd.DataFrame:
    frame = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame["config_bundle_sha256"] = context["bundle"]
    frame.to_csv(path, index=False, lineterminator="\n")
    return frame


def image_and_reference_checks(basic: dict, dev_images: set, context: dict) -> tuple[list, list]:
    images = {s: set(f.image_id) for s, f in basic.items()}
    image_rows = [
        {"split_a": a, "split_b": b, "overlap_images": len(images[a] & images[b]),
         "images_a": len(images[a]), "images_b": len(images[b])}
        for a, b in itertools.combinations(images, 2)
    ]
    mapping, raw_mapping = {}, {}
    for split, frame in basic.items():
        frame["analysis_split"] = (
            np.where(frame.image_id.isin(dev_images), "dev", "train_core") if split == "train" else split
        )
        for qid, assigned in zip(frame.question_id, frame.analysis_split):
            if qid in mapping:
                raise ValueError(f"Question ID appears in multiple raw splits: {qid}")
            mapping[qid], raw_mapping[qid] = assigned, split
    counts = Counter()
    for frame in basic.values():
        for row in frame[["question_id", "analysis_split", "entailed", "equivalent"]].itertuples(index=False):
            for field in ("entailed", "equivalent"):
                for target in getattr(row, field):
                    destination = mapping.get(target, "outside_balanced_files")
                    counts[(field, row.analysis_split, destination, row.question_id == target,
                            destination != row.analysis_split and destination != "outside_balanced_files",
                            target in raw_mapping and raw_mapping[target] != raw_mapping[row.question_id])] += 1
    references = [
        {"field": field, "from_split": source, "to_split": dest, "self_reference": self_ref,
         "crosses_analysis_split": crosses, "crosses_original_split": crosses_raw, "references": n}
        for (field, source, dest, self_ref, crosses, crosses_raw), n in sorted(counts.items())
    ]
    return image_rows, references


def unit_definitions(context: dict):
    rules = context["task_rules"]
    for task in rules["pilot_tasks"]:
        yield "task", task, "", ""
    for name, family in context["answer_families"]["families"].items():
        if family["task"] in rules["pilot_tasks"]:
            yield "family", family["task"], name, ""
    for task, strata in rules["strata"].items():
        for name in strata:
            yield "stratum", task, "", name


def select_unit(frame, task, family="", stratum=""):
    mask = frame.task.eq(task)
    if family:
        mask &= frame.family.eq(family)
    if stratum:
        mask &= frame.stratum.eq(stratum)
    return frame[mask]


def collect_statistics(raw: pd.DataFrame, selected: dict, context: dict) -> tuple[list, list]:
    stats, profiles = [], []
    for variant, chosen in selected.items():
        for split in ALL_SPLITS:
            raw_split, chosen_split = raw[raw.analysis_split.eq(split)], chosen[chosen.analysis_split.eq(split)]
            sealed = split == "testdev"
            for level, task, family, stratum in unit_definitions(context):
                source = select_unit(raw_split, task, family, stratum)
                frame = select_unit(chosen_split, task, family, stratum)
                n = len(frame)
                eligible = int(source.eligible.sum())
                row = {
                    "variant": variant, "split": split, "level": level, "task": task, "family": family, "stratum": stratum,
                    "raw_questions": len(source), "eligible_before_filter": eligible,
                    "questions": n, "images": frame.image_id.nunique(),
                    "nonbinary_excluded": int((~source.binary).sum()),
                    "empty_program_excluded": int((source.binary & source.empty_program).sum()),
                    "relation_filter_excluded": eligible - n,
                    "filter_exclusion_rate": (eligible - n) / eligible if eligible else math.nan,
                    "yes": int(frame.answer.eq("yes").sum()) if not sealed else None,
                    "no": int(frame.answer.eq("no").sum()) if not sealed else None,
                    "yes_ratio": float(frame.answer.eq("yes").mean()) if not sealed and n else math.nan,
                    "sealed_counts_only": sealed,
                }
                if not sealed and n:
                    row.update({
                        "program_length_mean": frame.program_length.mean(),
                        "program_length_median": frame.program_length.median(),
                        "relation_steps_mean": frame.relation_steps.mean(),
                        "depth_mean": frame.depth.mean(), "depth_median": frame.depth.median(),
                        "depth_nan_count": int(frame.depth.isna().sum()), "depth_nan_rate": frame.depth.isna().mean(),
                    })
                    if task == "logic":
                        parsed = frame.logic_json.map(json.loads)
                        unparseable = sum(p["parse_status"] != "ok" for p in parsed)
                        both_exist = sum(p.get("operand_pair") == "exist + exist" for p in parsed)
                        row.update({
                            "unparseable_logic_count": unparseable, "unparseable_logic_rate": unparseable / n,
                            "both_exist_count": both_exist, "both_exist_share": both_exist / n,
                        })
                stats.append(row)
                if not sealed:
                    for op_family in context["op_family_map"]["allowed_families"]:
                        profiles.append({
                            "variant": variant, "split": split, "level": level, "task": task,
                            "family": family, "stratum": stratum, "operation_family": op_family,
                            "questions": n,
                            "fraction": float(frame.op_families.map(lambda ops: op_family in ops).mean()) if n else math.nan,
                        })
    return stats, profiles


def overlap_statistics(selected: dict, context: dict) -> list:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    tasks = list(context["task_rules"]["pilot_tasks"])
    rows = []
    for variant, data in selected.items():
        train = data[data.analysis_split.isin(["train_core", "dev"])]
        core = data[data.analysis_split.eq("train_core")].reset_index(drop=True)
        image_sets = {task: set(train[train.task.eq(task)].image_id) for task in tasks}
        settings = context["runtime"]["baseline"]
        vectorizer = TfidfVectorizer(ngram_range=tuple(settings["ngram_range"]), min_df=settings["min_df"])
        matrix = vectorizer.fit_transform(core.question.tolist())
        centroids, vocabularies, op_vectors = [], {}, []
        tokenizer = TfidfVectorizer(ngram_range=(1, 1)).build_analyzer()
        for task in tasks:
            indices = np.flatnonzero(core.task.eq(task).to_numpy())
            centroids.append(np.asarray(matrix[indices].mean(axis=0)).ravel())
            vocabularies[task] = set(word for q in core.iloc[indices].question for word in tokenizer(q))
            op_vectors.append([
                core.iloc[indices].op_families.map(lambda fs: f in fs).mean()
                for f in context["op_family_map"]["allowed_families"]
            ])
        lexical, operation = cosine_similarity(np.array(centroids)), cosine_similarity(np.array(op_vectors))
        for i, task_i in enumerate(tasks):
            for j, task_j in enumerate(tasks):
                a, b = image_sets[task_i], image_sets[task_j]
                values = {
                    "image_coverage": len(a & b) / len(b) if b else 0,
                    "image_jaccard": len(a & b) / len(a | b) if a | b else 0,
                    "lexical_cosine": lexical[i, j],
                    "vocabulary_jaccard": len(vocabularies[task_i] & vocabularies[task_j]) /
                                          len(vocabularies[task_i] | vocabularies[task_j]),
                    "operation_cosine": operation[i, j],
                }
                for metric, value in values.items():
                    rows.append({
                        "variant": variant, "metric": metric, "task_i": task_i, "task_j": task_j,
                        "value": value, "source_split": "train" if metric.startswith("image") else "train_core",
                    })
    return rows


def majority_label(answers) -> str:
    counts = Counter(answers)
    return sorted(counts, key=lambda label: (-counts[label], label))[0]


def baseline_statistics(selected: dict, context: dict) -> tuple[list, list]:
    metrics, predictions = [], []
    for variant, data in selected.items():
        for task in context["task_rules"]["pilot_tasks"]:
            frame = data[data.task.eq(task)]
            train = frame[frame.analysis_split.eq("train_core")]
            if train.answer.nunique() != 2:
                raise ValueError(f"{variant}/{task}: baseline train must contain both classes")
            print(f"Fitting question-only baseline: {variant}/{task}, train_core={len(train):,}", flush=True)
            model = fit_question_baseline(train.question.tolist(), train.answer.to_numpy(),
                                          context["runtime"]["baseline"], context["task_rules"]["seed"])
            for split in ("dev", "val"):
                evaluation = frame[frame.analysis_split.eq(split)].copy()
                evaluation["prediction"] = model.predict(evaluation.question.tolist())
                units = [("task", "", lambda f: np.ones(len(f), dtype=bool))]
                units += [("family", name, lambda f, name=name: f.family.eq(name)) for name in sorted(train.family.unique())]
                units += [("stratum", name, lambda f, name=name: f.stratum.eq(name))
                          for name in sorted(train.stratum.unique()) if name]
                if task == "verifyRel":
                    units += [("metric_subset", name, lambda f, spec=spec: f.detailed.isin(spec["yes"] + spec["no"]))
                              for name, spec in context["task_rules"]["metric_subsets"].items()]
                for level, unit, mask in units:
                    source, target = train[mask(train)], evaluation[mask(evaluation)]
                    if source.empty or target.empty:
                        continue
                    majority = majority_label(source.answer)
                    accuracy = float(target.prediction.eq(target.answer).mean())
                    majority_accuracy = float(target.answer.eq(majority).mean())
                    metrics.append({
                        "variant": variant, "task": task, "split": split, "level": level, "unit": unit,
                        "questions": len(target), "yes": int(target.answer.eq("yes").sum()),
                        "no": int(target.answer.eq("no").sum()),
                        "accuracy": accuracy, "majority_accuracy": majority_accuracy,
                        "majority_label_from_train_core": majority, "gain_over_majority": accuracy - majority_accuracy,
                        "tfidf_features": len(model["tfidf"].vocabulary_),
                        "solver_iterations": int(model["classifier"].n_iter_.max()),
                    })
                for row in evaluation[["question_id", "analysis_split", "task", "family", "stratum", "answer", "prediction"]].to_dict("records"):
                    predictions.append({"variant": variant, **row})
    if any(r["analysis_split"] not in ("dev", "val") for r in predictions):
        raise ValueError("Sealed split reached baseline predictions")
    return metrics, predictions


def stratified_sample(frame: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Equal family coverage up to capacity; no replacement, no training rebalancing."""
    if frame.empty:
        return frame
    groups = {str(k): group.sort_values("question_id") for k, group in frame.groupby("family")}
    quotas = {k: 0 for k in groups}
    remaining = min(n, len(frame))
    while remaining:
        for key, group in groups.items():
            if remaining and quotas[key] < len(group):
                quotas[key] += 1
                remaining -= 1
    return pd.concat([group.sample(n=quotas[k], random_state=seed) for k, group in groups.items()])


def manual_samples(pilot_train: pd.DataFrame, selected: dict, context: dict) -> tuple[list, list]:
    rows, availability = [], []
    n, seed = context["runtime"]["manual_samples_per_group"], context["task_rules"]["seed"]
    for variant, data in selected.items():
        train = data[data.analysis_split.isin(["train_core", "dev"])]
        for task in context["task_rules"]["pilot_tasks"]:
            frame = train[train.task.eq(task)]
            groups = [("retained", frame)]
            if task in context["task_rules"]["audit_variants"][variant]:
                removed = pilot_train[pilot_train.task.eq(task) & ~pilot_train.question_id.isin(frame.question_id)]
                groups.append(("removed_by_relation_filter", removed))
            for kind, source in groups:
                sample = stratified_sample(source, n, seed)
                availability.append({
                    "variant": variant, "task": task, "sample_kind": kind, "available": len(source),
                    "requested": n, "sampled": len(sample),
                })
                for r in sample.to_dict("records"):
                    program = json.loads(r["program_json"])
                    pretty = "\n".join(
                        f"{i}: {s['operation']} | {s['argument']} | deps={s.get('dependencies')}" for i, s in enumerate(program)
                    )
                    rows.append({
                        "variant": variant, "sample_kind": kind, "assigned_task": task,
                        "question_id": r["question_id"], "imageId": r["image_id"], "question": r["question"],
                        "answer": r["answer"], "detailed_type": r["detailed"], "family": r["family"],
                        "stratum": r["stratum"], "analysis_split": r["analysis_split"],
                        "program": pretty, "R_strict": r["strict"], "semantic_type": r["semantic_type"], "human_ok": "",
                    })
    return rows, availability


def preregistered_checks(stats: pd.DataFrame, baselines: pd.DataFrame, image_checks: list, context: dict) -> list:
    thresholds, waivers = context["task_rules"]["thresholds"], context["task_rules"]["waivers"]
    rows = []

    def add(name, variant, split, task, observed, threshold, passed, unit="", waived=False, info=False):
        rows.append({
            "check": name, "variant": variant, "split": split, "task": task, "unit": unit,
            "observed": observed, "threshold": str(threshold), "status": "INFO" if info else ("PASS" if passed else "FLAG"),
            "waived": bool(waived),
        })

    low, high = thresholds["yes_ratio_band"]
    for r in stats.to_dict("records"):
        if r["level"] == "stratum":
            continue
        v, split, task = r["variant"], r["split"], r["task"]
        if split == "testdev":
            if r["level"] == "task":
                add("testdev_size_info_only", v, split, task, r["questions"],
                    thresholds["testdev_questions_per_task_info_only"], True, info=True)
            continue
        if r["level"] == "family":
            n = r["questions"]
            add("family_has_both_answers", v, split, task, f"{r['yes']}/{r['no']}", "both > 0",
                r["yes"] > 0 and r["no"] > 0, unit=r["family"], info=n == 0)
            continue
        minimum = {
            "train_core": thresholds["min_train_core_questions_per_task"],
            "dev": thresholds["min_dev_questions_per_task"],
            "val": thresholds["min_val_questions_per_task"],
        }[split]
        add("task_size", v, split, task, r["questions"], f">= {minimum}", r["questions"] >= minimum)
        add("task_yes_ratio", v, split, task, r["yes_ratio"], f"[{low}, {high}]", low <= r["yes_ratio"] <= high)
        cap = thresholds["max_filter_exclusion_rate"]
        add("filter_exclusion_rate", v, split, task, r["filter_exclusion_rate"], f"<= {cap}",
            r["filter_exclusion_rate"] <= cap, waived=task in waivers["max_filter_exclusion_rate"])
        add("depth_nan_rate", v, split, task, r["depth_nan_rate"], f"<= {thresholds['max_depth_nan_rate']}",
            r["depth_nan_rate"] <= thresholds["max_depth_nan_rate"])
        if task == "logic":
            add("unparseable_logic_rate", v, split, task, r["unparseable_logic_rate"],
                f"<= {thresholds['max_unparseable_logic_rate']}",
                r["unparseable_logic_rate"] <= thresholds["max_unparseable_logic_rate"])
    for r in baselines[(baselines.level == "task") & (baselines.split == "val")].to_dict("records"):
        margin = thresholds["blind_baseline_margin_over_majority"]
        add("blind_accuracy_gain", r["variant"], "val", r["task"], r["gain_over_majority"],
            f"<= {margin}", r["gain_over_majority"] <= margin)
    for r in image_checks:
        add("original_split_image_disjointness", "", r["split_a"] + "/" + r["split_b"], "",
            r["overlap_images"], "0", r["overlap_images"] == 0)
    return rows


def make_registry(selected: dict, metadata: dict, dev_images: list, context: dict) -> dict:
    registry = {}
    for variant, frame in selected.items():
        if frame.question_id.duplicated().any():
            raise ValueError(f"{variant}: task or split memberships overlap")
        registry[variant] = {
            task: {split: sorted(frame.loc[frame.task.eq(task) & frame.analysis_split.eq(split), "question_id"].tolist())
                   for split in ALL_SPLITS}
            for task in context["task_rules"]["pilot_tasks"]
        }
    content = {
        "schema_version": 1, "variants": registry, "config_hashes": context["hashes"],
        "config_bundle_sha256": context["bundle"], "input_hashes": context["manifest"]["input_sha256"],
        "git_commit": metadata["git_commit"], "package_versions": metadata["package_versions"],
        "seed": context["task_rules"]["seed"], "dev_seed": context["task_rules"]["splits"]["dev_seed"],
        "dev_fraction_of_train_images": context["task_rules"]["splits"]["dev_fraction_of_train_images"],
        "dev_image_list_sha256": canonical_hash(dev_images),
        "dev_sampling_algorithm": "ceil(fraction*n_images); sorted IDs; numpy.default_rng(seed).choice without replacement",
        "testdev_policy": "sealed_counts_only",
        "hash_convention": "SHA-256 of UTF-8 JSON with sorted keys, compact separators, excluding registry_sha256",
    }
    content["registry_sha256"] = canonical_hash(content)
    return content


def run_stage2(questions: Path) -> int:
    context = load_frozen(CONFIG)
    rules = context["task_rules"]
    # Input and frozen hashes are mandatory gates; no analysis starts on a mismatch.
    for split, expected in context["manifest"]["input_sha256"].items():
        path = questions / f"{split}_balanced_questions.json"
        if not path.is_file() or file_hash(path) != expected:
            raise ValueError(f"{split}: input file hash differs from FROZEN_MANIFEST")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in ("task_rules.yaml", "op_family_map.yaml", "answer_families.yaml", "audit_runtime.yaml", "FROZEN_MANIFEST.json"):
        shutil.copyfile(CONFIG / name, OUTPUT / name)
    metadata = {
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "package_versions": {p: version(p) for p in ("ijson", "numpy", "pandas", "pyarrow", "scikit-learn", "matplotlib", "PyYAML", "pytest")},
        "config_hashes": context["hashes"], "config_bundle_sha256": context["bundle"],
        "input_hashes": context["manifest"]["input_sha256"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": {str(p.relative_to(ROOT)): file_hash(p) for p in sorted((ROOT / "gqa_audit").glob("*.py"))},
        "frozen_decisions": rules["decisions"],
    }
    cache_dir = OUTPUT / "cache"
    for split in ("train", "val", "testdev"):
        print(f"Preparing cache: {split}", flush=True)
        build_cache(questions / f"{split}_balanced_questions.json",
                    cache_dir / f"questions_{split}.parquet", split, context)
    basic, pilot = load_tables(cache_dir, context)
    regression = regression_rows(basic, context)
    write_csv(OUTPUT / "regression_checks.csv", regression, context)
    if any(r["status"] != "PASS" for r in regression):
        raise ValueError("Frozen regression targets differ; stopped before baselines. See regression_checks.csv")
    print(f"Frozen regression targets: {len(regression)} PASS", flush=True)
    dev_images = choose_dev_images(
        basic["train"].image_id, rules["splits"]["dev_fraction_of_train_images"], rules["splits"]["dev_seed"],
    )
    dev_set = set(dev_images)
    image_checks, references = image_and_reference_checks(basic, dev_set, context)
    write_csv(OUTPUT / "split_image_overlap.csv", image_checks, context)
    write_csv(OUTPUT / "cross_split_references.csv", references, context)
    (OUTPUT / "dev_images.json").write_text(json.dumps({
        "image_ids": dev_images, "sha256": canonical_hash(dev_images), "config_bundle_sha256": context["bundle"],
    }, indent=2) + "\n")
    for split, frame in pilot.items():
        frame["analysis_split"] = np.where(frame.image_id.isin(dev_set), "dev", "train_core") if split == "train" else split
    raw = pd.concat(basic.values(), ignore_index=True)
    all_pilot = pd.concat(pilot.values(), ignore_index=True)
    selected = {variant: all_pilot[retained_mask(all_pilot, variant, context)].copy()
                for variant in rules["audit_variants"]}
    for frame in selected.values():
        if set(frame.loc[frame.analysis_split.eq("train_core"), "image_id"]) & set(frame.loc[frame.analysis_split.eq("dev"), "image_id"]):
            raise ValueError("train_core/dev images overlap")
    secondary = raw[raw.task.eq(rules["unmatched_task"])]
    sizes = secondary.groupby(["analysis_split", "detailed"], sort=True).agg(
        questions=("question_id", "size"), images=("image_id", "nunique"),
    ).reset_index()
    write_csv(OUTPUT / "secondary_sizes.csv", sizes, context)
    stats_rows, profile_rows = collect_statistics(raw, selected, context)
    stats = write_csv(OUTPUT / "task_stats.csv", stats_rows, context)
    write_csv(OUTPUT / "family_stats.csv", stats[stats.level.eq("family")], context)
    write_csv(OUTPUT / "stratum_stats.csv", stats[stats.level.eq("stratum")], context)
    profiles = write_csv(OUTPUT / "op_family_profile.csv", profile_rows, context)
    write_csv(OUTPUT / "exclusion_counts.csv", stats[
        ["variant", "split", "level", "task", "family", "stratum", "raw_questions", "eligible_before_filter",
         "nonbinary_excluded", "empty_program_excluded", "relation_filter_excluded", "filter_exclusion_rate"]
    ], context)
    logic_rows, dash_rows = [], []
    for variant, data in selected.items():
        analysis = data[data.analysis_split.isin(ANALYSIS_SPLITS)]
        for r in analysis[analysis.task.eq("logic")][["question_id", "analysis_split", "stratum", "logic_json"]].itertuples(index=False):
            decomposition = json.loads(r.logic_json)
            for field in ("operand1_indices", "operand2_indices"):
                if field in decomposition:
                    decomposition[field] = json.dumps(decomposition[field])
            logic_rows.append({"variant": variant, "question_id": r.question_id,
                               "split": r.analysis_split, "stratum": r.stratum, **decomposition})
        for (split, detailed), frame in analysis[analysis.task.eq("verifyRel")].groupby(["analysis_split", "detailed"]):
            dash_rows.append({
                "variant": variant, "split": split, "detailed_type": detailed, "questions": len(frame),
                "verify_rel_dash_questions": int(frame.verify_rel_dash.sum()),
                "verify_rel_dash_rate": float(frame.verify_rel_dash.mean()),
                "any_program_dash_rate": float(frame.any_dash.mean()),
            })
    logic = write_csv(OUTPUT / "logic_decomposition.csv", logic_rows, context)
    write_csv(OUTPUT / "logic_operand_pairs.csv", logic.groupby(
        ["variant", "split", "stratum", "operator", "operand_pair", "parse_status"], dropna=False,
    ).size().rename("questions").reset_index(), context)
    write_csv(OUTPUT / "verifyrel_dash_rates.csv", dash_rows, context)
    samples, availability = manual_samples(pilot["train"], selected, context)
    write_csv(OUTPUT / "manual_review_sample.csv", samples, context)
    write_csv(OUTPUT / "manual_sample_availability.csv", availability, context)
    overlap = write_csv(OUTPUT / "overlap_matrices.csv", overlap_statistics(selected, context), context)
    baselines, predictions = baseline_statistics(selected, context)
    baseline_frame = write_csv(OUTPUT / "blind_baseline.csv", baselines, context)
    write_csv(OUTPUT / "blind_predictions.csv", predictions, context)
    checks = write_csv(OUTPUT / "preregistered_checks.csv",
                       preregistered_checks(stats, baseline_frame, image_checks, context), context)
    registry = make_registry(selected, metadata, dev_images, context)
    (OUTPUT / "task_registry.json").write_text(json.dumps(registry, sort_keys=True, indent=2) + "\n")
    write_csv(OUTPUT / "task_registry_summary.csv", [
        {"variant": variant, "task": task, "split": split, "questions": len(ids)}
        for variant, tasks in registry["variants"].items()
        for task, splits in tasks.items() for split, ids in splits.items()
    ], context)
    metadata["registry_sha256"] = registry["registry_sha256"]
    metadata["dev_images_sha256"] = canonical_hash(dev_images)
    metadata["dev_images_count"] = len(dev_images)
    metadata["train_images_count"] = basic["train"].image_id.nunique()
    metadata["sealed_testdev"] = {"policy": "counts_only", "baseline_predictions": 0, "program_feature_rows": 0}
    from .stage2_report import create_stage2_report
    create_stage2_report(OUTPUT, ROOT / "notebooks/gqa_stage2_audit.ipynb", stats, profiles,
                         overlap, baseline_frame, checks, logic, selected, metadata, context)
    metadata["artifacts"] = {
        str(path.relative_to(OUTPUT)): file_hash(path)
        for path in sorted(OUTPUT.rglob("*")) if path.is_file() and "cache" not in path.parts
        and path.name not in ("run_manifest.json", "independent_verification.json")
    }
    metadata["notebook_sha256"] = file_hash(ROOT / "notebooks/gqa_stage2_audit.ipynb")
    (OUTPUT / "run_manifest.json").write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n")
    print(f"Stage 2 complete: {OUTPUT}", flush=True)
    return 0
