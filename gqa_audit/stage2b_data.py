"""Read-only inputs, frozen analysis subsets and answer-free operation tokens."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml

from .stage2_core import canonical_hash, file_hash, load_frozen
from .stage2_data import load_tables, retained_mask


ROOT = Path(__file__).resolve().parent.parent
PLAN_SHA256 = "0d23283638bbfa254994156fe30650ef5db6254f50c943f27c7233452b99520b"
REGISTRY_SHA256 = "c122aac0bbb9ed8ad6eaa93843d95df664ba75c767946003e90ff2469c27b451"
PREDICTIONS_SHA256 = "9cbd7f95fed1aa49301cdd6c86b4ff5cc35af26ccc3bf732554098dd66413c00"


def read_hashed_json(path: Path, field: str, expected: str | None = None) -> dict:
    value = json.loads(path.read_text())
    recorded = value.pop(field)
    if canonical_hash(value) != recorded or expected is not None and recorded != expected:
        raise ValueError(f"Canonical hash mismatch: {path}")
    value[field] = recorded
    return value


def load_plan(root: Path = ROOT) -> dict:
    path = root / "gqa_audit/config/analysis_plan.FROZEN.yaml"
    if file_hash(path) != PLAN_SHA256:
        raise ValueError("Frozen H-L analysis plan SHA-256 mismatch")
    plan = yaml.safe_load(path.read_text())
    if plan.get("status") != "FROZEN":
        raise ValueError("Analysis plan must be FROZEN")
    regex = plan["subsets"]["logic_no_not_cue"]["exclude_if"]["question_regex"]
    if type(regex) is not str or not re.search(regex, "not blue") or re.search(regex, "nothing"):
        raise ValueError("Invalid frozen logic cue regex")
    return plan


def preflight(root: Path, questions: Path) -> tuple[dict, dict, dict]:
    plan, context = load_plan(root), load_frozen(root / "gqa_audit/config")
    output = root / "gqa_audit/outputs/stage2"
    registry = read_hashed_json(output / "task_registry.json", "registry_sha256", REGISTRY_SHA256)
    if registry["registry_sha256"] != plan["applies_to_registry_sha256"]:
        raise ValueError("Plan applies to a different registry")
    if file_hash(output / "blind_predictions.csv") != PREDICTIONS_SHA256:
        raise ValueError("Frozen blind predictions SHA-256 mismatch")
    manifest = json.loads((output / "run_manifest.json").read_text())
    inputs = {}
    def input_name(path):
        try:
            return str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            return str(path.resolve())
    for split, digest in registry["input_hashes"].items():
        path = questions / f"{split}_balanced_questions.json"
        actual = file_hash(path)
        if actual != digest:
            raise ValueError(f"Raw input hash mismatch: {split}")
        inputs[input_name(path)] = actual
        cache = output / f"cache/questions_{split}.parquet"
        fingerprint = canonical_hash({
            "config_bundle": context["bundle"], "input": digest,
            "data_code": file_hash(root / "gqa_audit/stage2_data.py"),
            "core_code": file_hash(root / "gqa_audit/stage2_core.py"),
        })
        if pq.read_metadata(cache).metadata.get(b"fingerprint") != fingerprint.encode():
            raise ValueError(f"Stage 2 cache fingerprint mismatch: {split}")
        inputs[input_name(cache)] = file_hash(cache)
    for name, digest in manifest["artifacts"].items():
        if file_hash(output / name) != digest:
            raise ValueError(f"Stage 2 artifact changed: {name}")
    for name in ("task_registry.json", "blind_predictions.csv", "dev_images.json", "run_manifest.json"):
        inputs[input_name(output / name)] = file_hash(output / name)
    config_dir = root / "gqa_audit/config"
    for path in sorted(config_dir.glob("*.yaml")):
        inputs[input_name(path)] = file_hash(path)
    for path in (config_dir / "FROZEN_MANIFEST.json", root / "codex_prompt_gqa_stage2b_analysis.md"):
        inputs[input_name(path)] = file_hash(path)
    context["analysis_plan"] = plan
    context["analysis_runtime"] = yaml.safe_load((config_dir / "stage2b_runtime.yaml").read_text())
    context["input_hashes_stage2b"] = inputs
    context["root"] = root
    return context, registry, {"status": "PASS", "analysis_plan_sha256": PLAN_SHA256,
                              "registry_sha256": REGISTRY_SHA256,
                              "blind_predictions_sha256": PREDICTIONS_SHA256,
                              "stage2_artifacts_checked": len(manifest["artifacts"])}


def load_analysis_tables(root: Path, context: dict, registry: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    # Reuse the existing loader. Its testdev branch reads basic assignment metadata
    # only; no text, programs or predictions are loaded or processed for testdev.
    basic, pilot = load_tables(root / "gqa_audit/outputs/stage2/cache", context)
    dev = set(json.loads((root / "gqa_audit/outputs/stage2/dev_images.json").read_text())["image_ids"])
    frames = []
    for split in ("train", "val"):
        frame = pilot[split].copy()
        frame["part"] = np.where(frame.image_id.isin(dev), "dev", "train_core") if split == "train" else split
        frame["in_unfiltered"] = retained_mask(frame, "unfiltered", context)
        frame["in_program_strict"] = retained_mask(frame, "program_strict", context)
        frames.append(frame)
    # Preserve Stage 2 cache row order so a future frozen baseline refit receives
    # exactly the original training sequence. Published ID lists are sorted.
    raw = pd.concat(frames, ignore_index=True)
    if raw.question_id.duplicated().any():
        raise ValueError("Duplicate question IDs across analysis parts")
    for variant, tasks in registry["variants"].items():
        for task, parts in tasks.items():
            for part in ("train_core", "dev", "val"):
                ids = raw.loc[raw[f"in_{variant}"] & raw.task.eq(task) & raw.part.eq(part), "question_id"]
                if sorted(ids) != parts[part]:
                    raise ValueError(f"Cache/registry mismatch: {variant}/{task}/{part}")
    sealed = basic["testdev"]
    sealed = sealed.loc[sealed.eligible & sealed.task.isin(context["task_rules"]["pilot_tasks"])].copy()
    sealed["part"] = "testdev"
    for variant in registry["variants"]:
        ids = {qid for parts in registry["variants"][variant].values() for qid in parts["testdev"]}
        sealed[f"in_{variant}"] = sealed.question_id.isin(ids)
    sealed = sealed[["question_id", "part", "task", "family", "stratum", "in_program_strict", "in_unfiltered"]]
    return raw, sealed, basic


def checked_predictions(path: Path, raw: pd.DataFrame, registry: dict) -> pd.DataFrame:
    pred = pd.read_csv(path, dtype={"question_id": str}, keep_default_na=False)
    if pred.duplicated(["variant", "question_id"]).any():
        raise ValueError("Duplicate frozen baseline predictions")
    if not set(pred.analysis_split) <= {"dev", "val"}:
        raise ValueError("Baseline predictions must exclude testdev")
    metadata = raw.set_index("question_id")
    for variant, tasks in registry["variants"].items():
        expected = {qid for parts in tasks.values() for part in ("dev", "val") for qid in parts[part]}
        selected = pred[pred.variant.eq(variant)]
        if set(selected.question_id) != expected:
            raise ValueError(f"Baseline prediction IDs differ: {variant}")
        target = metadata.loc[selected.question_id]
        for column in ("answer", "task", "family", "stratum"):
            if selected[column].tolist() != target[column].tolist():
                raise ValueError(f"Baseline metadata mismatch: {variant}/{column}")
        if selected.analysis_split.tolist() != target.part.tolist() or not set(selected.prediction) <= {"yes", "no"}:
            raise ValueError("Baseline part/prediction mismatch")
    return pred


def make_subsets(raw: pd.DataFrame, predictions: pd.DataFrame, context: dict) -> tuple[dict, pd.DataFrame]:
    plan = context["analysis_plan"]
    result = {"schema_version": 1, "registry_sha256": REGISTRY_SHA256,
              "analysis_plan_sha256": PLAN_SHA256, "input_hashes": context["input_hashes_stage2b"], "subsets": {}}
    counts = []
    for name, definition in plan["subsets"].items():
        result["subsets"][name] = {}
        for variant in context["task_rules"]["audit_variants"]:
            result["subsets"][name][variant] = {}
            selected = raw[raw[f"in_{variant}"]]
            tasks = list(context["task_rules"]["pilot_tasks"]) if name == "text_hard" else [definition["task"]]
            for task in tasks:
                result["subsets"][name][variant][task] = {}
                parts = ("dev", "val") if name == "text_hard" else ("train_core", "dev", "val")
                for part in parts:
                    frame = selected[selected.task.eq(task) & selected.part.eq(part)]
                    if "detailed_types" in definition:
                        frame = frame[frame.detailed.isin(definition["detailed_types"])]
                    elif "exclude_if" in definition:
                        rule = definition["exclude_if"]
                        frame = frame[~(frame.family.eq(rule["family"]) & frame.question.str.contains(rule["question_regex"], regex=True))]
                    elif name == "text_hard":
                        errors = predictions.loc[predictions.variant.eq(variant) & predictions.task.eq(task)
                                                 & predictions.analysis_split.eq(part)
                                                 & predictions.prediction.ne(predictions.answer), "question_id"]
                        frame = frame[frame.question_id.isin(errors)]
                    result["subsets"][name][variant][task][part] = sorted(frame.question_id)
                    counts.append({"subset": name, "variant": variant, "task": task, "part": part,
                                   "n": len(frame), "yes": int(frame.answer.eq("yes").sum()),
                                   "yes_ratio": float(frame.answer.eq("yes").mean()) if len(frame) else np.nan})
    result["analysis_subsets_sha256"] = canonical_hash(result)
    return result, pd.DataFrame(counts)


def operation_tokens(program: list) -> list[str]:
    """Only operations and the explicitly approved negation indicator may escape."""
    tokens = []
    for step in program:
        operation = step["operation"].strip()
        if not operation or "(-)" in operation or any(c.isdigit() for c in operation):
            raise ValueError("Malformed operation token")
        tokens.append(operation)
        if step["argument"].startswith("not("):
            tokens.append(f"{operation} [neg]")
    return tokens


def map_tokens(tokens: list[str], vocabulary: set[str]) -> list[str]:
    return [token if token in vocabulary else "UNSEEN" for token in tokens]


def make_descriptors(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    tokens = raw.program_json.map(lambda value: operation_tokens(json.loads(value)))
    train = raw.in_program_strict & raw.part.eq("train_core")
    vocabulary = sorted({token for row in tokens[train] for token in row})
    allowed = set(vocabulary)
    mapped = tokens.map(lambda row: map_tokens(row, allowed))
    columns = ["question_id", "image_id", "part", "in_program_strict", "in_unfiltered", "task", "family", "stratum",
               "answer", "program_length", "depth", "relation_steps"]
    descriptors = raw[columns].copy().rename(columns={"image_id": "imageId", "relation_steps": "n_relate"})
    descriptors["with_select"] = mapped
    descriptors["token_multiset"] = mapped.map(lambda row: [token for token in row if token != "select"])
    unseen = []
    for (part, task), frame in raw.groupby(["part", "task"], sort=True):
        for variant in ("program_strict", "unfiltered"):
            chosen = frame[frame[f"in_{variant}"]]
            values = mapped.loc[chosen.index]
            unseen.append({"part": part, "task": task, "variant": variant, "n": len(chosen),
                           "unseen_tokens": sum(row.count("UNSEEN") for row in values),
                           "questions_with_unseen": sum("UNSEEN" in row for row in values)})
    vocab = {"tokens": vocabulary, "unknown_token": "UNSEEN", "fit_variant": "program_strict", "fit_part": "train_core",
             "analysis_plan_sha256": PLAN_SHA256, "registry_sha256": REGISTRY_SHA256}
    vocab["vocabulary_sha256"] = canonical_hash(vocab)
    return descriptors, vocab, pd.DataFrame(unseen)


def regression_checks(raw, subsets, vocabulary, overlap, context) -> pd.DataFrame:
    rows = []
    targets = context["analysis_plan"]["regression_targets"]
    def add(kind, key, field, expected, actual):
        rows.append({"kind": kind, "key": key, "field": field, "expected": expected, "actual": actual,
                     "status": "PASS" if expected == actual else "FAIL"})
    def subset(name, variant, task, part):
        return set(subsets["subsets"][name][variant][task][part])
    for target in targets["text_hard"]:
        variant, part, task = (target[k] for k in ("variant", "part", "task"))
        frame = raw[raw[f"in_{variant}"] & raw.part.eq(part) & raw.task.eq(task)]
        chosen = frame[frame.question_id.isin(subset("text_hard", variant, task, part))]
        for key, actual in (("n", len(frame)), ("text_hard", len(chosen)), ("text_hard_yes", int(chosen.answer.eq("yes").sum()))):
            add("text_hard", f"{variant}/{part}/{task}", key, target[key], actual)
    for target in targets["logic_no_not_cue"]:
        for variant in context["task_rules"]["audit_variants"]:
            frame = raw[raw[f"in_{variant}"] & raw.part.eq(target["part"]) & raw.task.eq("logic")]
            n = len(subset("logic_no_not_cue", variant, "logic", target["part"]))
            for key, actual in (("logic", len(frame)), ("not_cue", len(frame) - n), ("logic_no_not_cue", n)):
                add("logic_no_not_cue", f"{variant}/{target['part']}", key, target[key], actual)
    relation = context["analysis_plan"]["subsets"]["verifyRel_relation"]["detailed_types"]
    for target in targets["verifyRel_subsets"]:
        frame = raw[raw.part.eq(target["part"]) & raw.task.eq("verifyRel") & raw.in_program_strict]
        for typ in relation:
            add("verifyRel", target["part"], typ, target[typ], int(frame.detailed.eq(typ).sum()))
        add("verifyRel", target["part"], "Co_n", target["verifyRel_Co_subset"],
            len(subset("verifyRel_Co", "program_strict", "verifyRel", target["part"])))
    for target in targets["question_level_sharing_binary"]:
        chosen = overlap[(overlap.part == target["part"]) & (overlap.source == target["source"]) & (overlap.target == target["target"])]
        if len(chosen) != 1:
            raise ValueError("Missing/duplicate question-overlap regression row")
        for field in ("n_target", "n_sharing"):
            add("overlap", f"{target['source']}->{target['target']}/{target['part']}", field, target[field], int(chosen.iloc[0][field]))
    add("vocabulary", "program_strict/train_core", "tokens",
        targets["descriptor_vocabulary_size_train_core_including_select_and_neg"], len(vocabulary["tokens"]))
    logic_ids = set(raw.loc[raw.task.eq("logic") & raw.part.eq("val") & raw.in_program_strict, "question_id"])
    excluded = logic_ids - subset("logic_no_not_cue", "program_strict", "logic", "val")
    add("subset_intersection", "val", "not_cue_in_text_hard", 0,
        len(excluded & subset("text_hard", "program_strict", "logic", "val")))
    return pd.DataFrame(rows)
