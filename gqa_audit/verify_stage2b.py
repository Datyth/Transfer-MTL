"""Independent read-only reconstruction of Stage 2b artifacts from train/val JSON."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .stage1 import iter_records
from .stage2_core import canonical_hash, file_hash, load_frozen
from .stage2b_data import ROOT, load_plan, read_hashed_json, REGISTRY_SHA256


def verify(root: Path, questions: Path) -> int:
    output = root / "gqa_audit/outputs/stage2b"
    manifest = json.loads((output / "run_manifest.json").read_text())
    errors = []
    for category, base in (("artifacts", output), ("source_hashes", root), ("test_hashes", root),
                           ("accepted_stage1_stage2_snapshot", root)):
        for name, expected in manifest[category].items():
            if file_hash(base / name) != expected:
                errors.append(f"{category} hash changed: {name}")
    if file_hash(root / "notebooks/gqa_stage2b_analysis.ipynb") != manifest["notebook_sha256"]:
        errors.append("Stage 2b notebook hash mismatch")
    plan, frozen = load_plan(root), load_frozen(root / "gqa_audit/config")
    registry = read_hashed_json(root / "gqa_audit/outputs/stage2/task_registry.json", "registry_sha256", REGISTRY_SHA256)
    subsets = read_hashed_json(output / "analysis_subsets.json", "analysis_subsets_sha256")
    vocabulary = read_hashed_json(output / "descriptor_vocabulary.json", "vocabulary_sha256")
    descriptors = pq.read_table(output / "question_descriptors.parquet").to_pandas()
    descriptors = descriptors.set_index("question_id", drop=False)
    if descriptors.index.duplicated().any() or descriptors.part.eq("testdev").any():
        errors.append("Descriptor IDs duplicate or testdev included")
    metadata = pq.read_table(output / "registry_questions.parquet").to_pandas()
    sealed = metadata[metadata.part.eq("testdev")]
    if sealed[["imageId", "answer", "program_length", "depth", "n_relate"]].notna().any().any():
        errors.append("Testdev registry metadata must omit labels/features/image IDs")
    expected_ids = set(descriptors.index)
    raw_details, token_sets, raw_tokens, expected_vocabulary = {}, {}, {}, set()
    dev_images = set(json.loads((root / "gqa_audit/outputs/stage2/dev_images.json").read_text())["image_ids"])
    subset_expected = {name: {variant: {task: {part: set() for part in parts}
                           for task, parts in tasks.items()} for variant, tasks in variants.items()}
                       for name, variants in subsets["subsets"].items()}
    checked = 0
    for split in ("train", "val"):
        path = questions / f"{split}_balanced_questions.json"
        if file_hash(path) != registry["input_hashes"][split]:
            errors.append(f"Raw hash mismatch: {split}")
        for qid, record in iter_records(path):
            if qid not in expected_ids:
                continue
            part = ("dev" if record["imageId"] in dev_images else "train_core") if split == "train" else "val"
            detailed, program = record["types"]["detailed"], record["semantic"]
            task = frozen["task_rules"]["type_mappings"][detailed]["task"]
            family = frozen["family_of"][detailed]
            answer = record["answer"].strip().lower()
            r = descriptors.loc[qid]
            raw_details[qid] = (part, task, family, answer)
            tokens = []
            for step in program:
                operation = step["operation"].strip()
                tokens.append(operation)
                if step["argument"].startswith("not("):
                    tokens.append(operation + " [neg]")
            raw_tokens[qid] = tokens
            if part == "train_core" and r.in_program_strict:
                expected_vocabulary.update(tokens)
            mapped = [token if token in vocabulary["tokens"] else "UNSEEN" for token in tokens]
            without_select = [token for token in mapped if token != "select"]
            if list(r.with_select) != mapped or list(r.token_multiset) != without_select:
                errors.append(f"Raw descriptor mismatch: {qid}")
            token_sets[qid] = set(without_select)
            if (r.part, r.task, r.family, r.answer) != (part, task, family, answer):
                errors.append(f"Raw descriptor metadata mismatch: {qid}")
            for variant in registry["variants"]:
                if not r[f"in_{variant}"]:
                    continue
                for name, definition in plan["subsets"].items():
                    if name == "text_hard" or definition["task"] != task:
                        continue
                    keep = True
                    if "detailed_types" in definition:
                        keep = detailed in definition["detailed_types"]
                    else:
                        rule = definition["exclude_if"]
                        keep = not (family == rule["family"] and re.search(rule["question_regex"], record["question"]))
                    if keep:
                        subset_expected[name][variant][task][part].add(qid)
            checked += 1
    if checked != len(descriptors):
        errors.append("Raw assigned descriptor coverage mismatch")
    if sorted(expected_vocabulary) != vocabulary["tokens"]:
        errors.append("Vocabulary was not fitted on strict train_core only")
    predictions = pd.read_csv(root / "gqa_audit/outputs/stage2/blind_predictions.csv", dtype={"question_id": str}, keep_default_na=False)
    for r in predictions.itertuples():
        if r.prediction != r.answer:
            subset_expected["text_hard"][r.variant][r.task][r.analysis_split].add(r.question_id)
    subset_lists = 0
    for name, variants in subset_expected.items():
        for variant, tasks in variants.items():
            for task, parts in tasks.items():
                for part, ids in parts.items():
                    actual = subsets["subsets"][name][variant][task][part]
                    if actual != sorted(ids):
                        errors.append(f"Independent subset mismatch: {name}/{variant}/{task}/{part}")
                    subset_lists += 1
    for variant, tasks in registry["variants"].items():
        for task, parts in tasks.items():
            for part, ids in parts.items():
                selected = metadata[metadata[f"in_{variant}"] & metadata.task.eq(task) & metadata.part.eq(part)]
                if sorted(selected.question_id) != ids:
                    errors.append(f"Registry export membership mismatch: {variant}/{task}/{part}")
    frequencies = {}
    for task in registry["variants"]["program_strict"]:
        ids = registry["variants"]["program_strict"][task]["train_core"]
        frequencies[task] = Counter(token for qid in ids for token in token_sets[qid])
    counts = pd.read_csv(output / "question_overlap_counts.csv")
    for r in counts.itertuples():
        ids = registry["variants"]["program_strict"][r.target][r.part]
        n = sum(bool(token_sets[qid] & frequencies[r.source].keys()) for qid in ids)
        if n != r.n_sharing or len(ids) != r.n_target:
            errors.append(f"Independent overlap count mismatch: {r.source}->{r.target}/{r.part}")
    values = pq.read_table(output / "question_overlap.parquet").to_pandas()
    for r in values.itertuples():
        frequency = frequencies[r.source]
        expected_continuous = sum(frequency[token] for token in token_sets[r.question_id])
        if r.shared_continuous != expected_continuous or r.shared_binary != (expected_continuous > 0):
            errors.append(f"Independent overlap feature mismatch: {r.question_id}/{r.source}")
    # Rescore all demo units from the original question-only outputs, independently.
    rescored = 0
    pred_index = {(r.variant, r.question_id): r.prediction for r in predictions.itertuples()}
    majority = {}
    for variant, tasks in registry["variants"].items():
        for task, parts in tasks.items():
            counter = Counter(raw_details[qid][3] for qid in parts["train_core"])
            majority[(variant, task)] = sorted(counter, key=lambda label: (-counter[label], label))[0]
    for name in ("blind", "majority"):
        scores = pd.read_csv(output / f"demo_eval_{name}.csv", keep_default_na=False)
        for r in scores.itertuples():
            ids = registry["variants"][r.variant][r.task][r.part]
            if r.level == "family":
                ids = [qid for qid in ids if raw_details[qid][2] == r.unit]
            elif r.level == "stratum":
                ids = [qid for qid in ids if descriptors.loc[qid, "stratum"] == r.unit]
            elif r.level == "subset":
                ids = subsets["subsets"][r.unit][r.variant][r.task][r.part]
            labels = [raw_details[qid][3] for qid in ids]
            pred = [pred_index[(r.variant, qid)] if name == "blind" else majority[(r.variant, r.task)] for qid in ids]
            n = len(ids)
            expected_accuracy = sum(a == p for a, p in zip(labels, pred)) / n if n else np.nan
            recalls = [np.mean([p == label for a, p in zip(labels, pred) if a == label]) if label in labels else np.nan for label in ("yes", "no")]
            balanced = sum(recalls) / 2
            if n != r.n or not np.isclose(expected_accuracy, float(r.accuracy) if r.accuracy != "" else np.nan, equal_nan=True):
                errors.append(f"Demo accuracy mismatch: {name}/{r.variant}/{r.part}/{r.unit}")
            if not np.isclose(balanced, float(r.balanced_accuracy) if r.balanced_accuracy != "" else np.nan, equal_nan=True):
                errors.append(f"Demo balanced accuracy mismatch: {name}/{r.variant}/{r.part}/{r.unit}")
            primary_ids = ids
            if r.task == "verifyRel" and r.unit != "verifyRel_Co":
                relation = set(subsets["subsets"]["verifyRel_relation"][r.variant][r.task][r.part])
                primary_ids = [qid for qid in ids if qid in relation]
            actual_primary = []
            for label in ("yes", "no"):
                selected = [qid for qid in primary_ids if raw_details[qid][3] == label]
                actual_primary.append(np.mean([(pred_index[(r.variant, qid)] if name == "blind" else majority[(r.variant, r.task)]) == label for qid in selected]) if selected else np.nan)
            value = sum(actual_primary) / 2 if r.primary_metric == "balanced_accuracy" else expected_accuracy
            if len(primary_ids) != r.primary_n or not np.isclose(value, float(r.primary_value) if r.primary_value != "" else np.nan, equal_nan=True):
                errors.append(f"Demo primary metric mismatch: {name}/{r.variant}/{r.part}/{r.unit}")
            rescored += 1
    regression = pd.read_csv(output / "regression_checks.csv")
    if not regression.status.eq("PASS").all():
        errors.append("Some frozen regression targets failed")
    report = (output / "pytest_report.txt").read_text()
    if "passed" not in report or " failed" in report:
        errors.append("Pytest success report missing")
    from .notebook import _cache_execution
    notebook = json.loads((root / "notebooks/gqa_stage2b_analysis.ipynb").read_text())
    _cache_execution(notebook["cells"], root)
    plots = sum("image/png" in entry.get("data", {}) for cell in notebook["cells"] for entry in cell.get("outputs", []))
    if plots != 4:
        errors.append("Notebook figure replay count differs")
    result = {"status": "PASS" if not errors else "FAIL", "errors": errors,
              "raw_train_val_descriptor_rows_checked": checked, "subset_lists_checked": subset_lists,
              "overlap_question_rows_checked": len(values), "demo_metric_rows_rescored": rescored,
              "regression_checks": len(regression), "notebook_plots_replayed": plots,
              "accepted_stage1_stage2_files_unchanged": len(manifest["accepted_stage1_stage2_snapshot"]),
              "testdev_text_program_prediction_processing": 0,
              "method": "Fresh train/val JSON tokens/subsets, independent document frequencies, registry membership, demo rescoring, hashes and notebook replay"}
    (output / "independent_verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(verify(ROOT, args.questions))
