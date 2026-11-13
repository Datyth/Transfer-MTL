"""Independent raw-data verification of the frozen Stage 2 registry and audit."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import re
from collections import Counter, defaultdict, deque
from pathlib import Path

import ijson
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .stage2_core import load_frozen


def independent_depth(program):
    """Kahn traversal, independent of the production DFS implementation."""
    n = len(program)
    remaining, children = [], [[] for _ in program]
    for i, step in enumerate(program):
        deps = step.get("dependencies")
        if not isinstance(deps, list) or any(type(d) is not int or not 0 <= d < n for d in deps):
            return math.nan
        remaining.append(len(deps))
        for d in deps:
            children[d].append(i)
    queue = deque(i for i, count in enumerate(remaining) if count == 0)
    depth, seen = [0] * n, 0
    while queue:
        node = queue.popleft()
        seen += 1
        for child in children[node]:
            depth[child] = max(depth[child], depth[node] + 1)
            remaining[child] -= 1
            if remaining[child] == 0:
                queue.append(child)
    return float(max(depth)) if seen == n and n else math.nan


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_stage2(questions: Path, root: Path) -> int:
    output = root / "gqa_audit/outputs/stage2"
    context = load_frozen(root / "gqa_audit/config")
    manifest = json.loads((output / "run_manifest.json").read_text())
    registry = json.loads((output / "task_registry.json").read_text())
    dev = json.loads((output / "dev_images.json").read_text())["image_ids"]
    rules = context["task_rules"]
    dev_set, errors = set(dev), []
    recorded_hash = registry.pop("registry_sha256")
    computed = hashlib.sha256(json.dumps(registry, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    if recorded_hash != computed or recorded_hash != manifest["registry_sha256"]:
        errors.append("Canonical registry hash mismatch")
    expected_registry = {
        variant: {task: {split: [] for split in ("train_core", "dev", "val", "testdev")}
                  for task in rules["pilot_tasks"]} for variant in rules["audit_variants"]
    }
    counts, images, raw_counts = defaultdict(Counter), defaultdict(set), Counter()
    answers, features, image_sets = {}, {}, {}
    frozen_ops = context["op_family_map"]["operations"]
    strict_heads = rules["relation_definitions"]["R_strict"]["operation_heads"]
    for split in ("train", "val", "testdev"):
        path = questions / f"{split}_balanced_questions.json"
        if digest(path) != context["manifest"]["input_sha256"][split]:
            errors.append(f"{split}: raw file SHA differs")
        image_sets[split] = set()
        with path.open("rb") as stream:
            for qid, record in ijson.kvitems(stream, ""):
                raw_counts[split] += 1
                image_sets[split].add(record["imageId"])
                detailed = record["types"]["detailed"]
                task = rules["type_mappings"][detailed]["task"]
                if task not in rules["pilot_tasks"]:
                    continue
                answer, program = record["answer"].strip().lower(), record["semantic"]
                eligible = answer in ("yes", "no") and isinstance(program, list) and len(program) > 0
                if not eligible:
                    continue
                assigned_split = ("dev" if record["imageId"] in dev_set else "train_core") if split == "train" else split
                family = context["family_of"][detailed]
                stratum = context["stratum_of"].get(detailed, "")
                strict_count = sum(step["operation"].split()[0] in strict_heads for step in program)
                answers[qid] = (assigned_split, task, family, stratum, detailed, answer)
                if split != "testdev":
                    op_profile = sorted({f for step in program for f in frozen_ops[step["operation"]]["families"]})
                    features[qid] = (len(program), strict_count, independent_depth(program), op_profile)
                for variant, filters in rules["audit_variants"].items():
                    if task in filters and strict_count > 0:
                        continue
                    expected_registry[variant][task][assigned_split].append(qid)
                    units = [("task", "", ""), ("family", family, "")]
                    if stratum:
                        units.append(("stratum", "", stratum))
                    for level, family_key, stratum_key in units:
                        key = (variant, assigned_split, level, task, family_key, stratum_key)
                        counts[key]["questions"] += 1
                        counts[key][answer] += 1
                        images[key].add(record["imageId"])
    for variant, task_map in expected_registry.items():
        for task, split_map in task_map.items():
            for split, ids in split_map.items():
                if sorted(ids) != registry["variants"][variant][task][split]:
                    errors.append(f"Raw registry membership mismatch: {variant}/{task}/{split}")
    sorted_images = np.array(sorted(image_sets["train"]), dtype=object)
    expected_dev = sorted(np.random.default_rng(rules["splits"]["dev_seed"]).choice(
        sorted_images, size=math.ceil(len(sorted_images) * rules["splits"]["dev_fraction_of_train_images"]),
        replace=False).tolist())
    if dev != expected_dev:
        errors.append("Image-based dev selection differs from frozen seed/fraction")
    if dict(raw_counts) != context["manifest"]["raw_question_counts"]:
        errors.append("Raw question counts differ")
    stats = pd.read_csv(output / "task_stats.csv", keep_default_na=False)
    for r in stats.to_dict("records"):
        key = (r["variant"], r["split"], r["level"], r["task"], r["family"], r["stratum"])
        expected = counts[key]
        if r["questions"] != expected["questions"] or r["images"] != len(images[key]):
            errors.append(f"Statistics count mismatch: {key}")
        if r["split"] != "testdev":
            if int(float(r["yes"])) != expected["yes"] or int(float(r["no"])) != expected["no"]:
                errors.append(f"Answer count mismatch: {key}")
        elif any(r.get(field, "") != "" for field in ("yes", "no", "yes_ratio", "depth_mean", "program_length_mean")):
            errors.append("Testdev contains non-count statistics")
    feature_checks = 0
    for split in ("train", "val"):
        cached = pq.read_table(output / "cache" / f"questions_{split}.parquet",
                               filters=[("eligible", "=", True), ("task", "in", list(rules["pilot_tasks"]))],
                               columns=["question_id", "program_length", "relation_steps", "depth", "op_families"]).to_pylist()
        for row in cached:
            length, relation, depth, families = features[row["question_id"]]
            depth_equal = (math.isnan(depth) and math.isnan(row["depth"])) or depth == row["depth"]
            if (length != row["program_length"] or relation != row["relation_steps"]
                    or families != row["op_families"] or not depth_equal):
                errors.append(f"Independent program feature mismatch: {row['question_id']}")
            feature_checks += 1
    sealed = pq.read_table(output / "cache/questions_testdev.parquet",
                           columns=["question", "program_json", "program_length", "depth", "op_families", "logic_json"]).to_pylist()
    if any(r["question"] is not None or r["program_json"] is not None or r["program_length"] is not None
           or not math.isnan(r["depth"]) or r["op_families"] or r["logic_json"] is not None for r in sealed):
        errors.append("Testdev feature cache is not sealed")
    prediction = pd.read_csv(output / "blind_predictions.csv", dtype={"question_id": str}, keep_default_na=False)
    if prediction.duplicated(["variant", "question_id"]).any() or not set(prediction.analysis_split) <= {"dev", "val"}:
        errors.append("Duplicate or sealed baseline predictions")
    for r in prediction.itertuples():
        expected = answers[r.question_id]
        if (r.analysis_split, r.task, r.family, r.stratum, r.answer) != (expected[0], expected[1], expected[2], expected[3], expected[5]):
            errors.append(f"Prediction metadata mismatch: {r.question_id}")
    for variant, task_map in expected_registry.items():
        for task, split_map in task_map.items():
            for split in ("dev", "val"):
                ids = set(prediction.loc[(prediction.variant == variant) & (prediction.task == task)
                                         & (prediction.analysis_split == split), "question_id"])
                if ids != set(split_map[split]):
                    errors.append(f"Prediction coverage differs: {variant}/{task}/{split}")
    baseline_rows = pd.read_csv(output / "blind_baseline.csv", keep_default_na=False)
    for row in baseline_rows.to_dict("records"):
        frame = prediction[(prediction.variant == row["variant"]) & (prediction.task == row["task"])
                           & (prediction.analysis_split == row["split"])]
        train_ids = expected_registry[row["variant"]][row["task"]]["train_core"]
        level, unit = row["level"], row["unit"]
        if level == "family":
            frame = frame[frame.family == unit]
            train_ids = [qid for qid in train_ids if answers[qid][2] == unit]
        elif level == "stratum":
            frame = frame[frame.stratum == unit]
            train_ids = [qid for qid in train_ids if answers[qid][3] == unit]
        elif level == "metric_subset":
            spec = rules["metric_subsets"][unit]
            types = spec["yes"] + spec["no"]
            frame = frame[frame.question_id.map(lambda qid: answers[qid][4] in types)]
            train_ids = [qid for qid in train_ids if answers[qid][4] in types]
        labels = Counter(answers[qid][5] for qid in train_ids)
        majority = sorted(labels, key=lambda label: (-labels[label], label))[0]
        accuracy, majority_accuracy = frame.prediction.eq(frame.answer).mean(), frame.answer.eq(majority).mean()
        if (len(frame) != row["questions"] or abs(accuracy - row["accuracy"]) > 1e-12
                or abs(majority_accuracy - row["majority_accuracy"]) > 1e-12):
            errors.append(f"Baseline metric mismatch: {row['variant']}/{row['task']}/{row['split']}/{unit}")
    for relative, expected in manifest["artifacts"].items():
        if digest(output / relative) != expected:
            errors.append(f"Artifact hash mismatch: {relative}")
    for relative, expected in manifest["source_sha256"].items():
        if digest(root / relative) != expected:
            errors.append(f"Source hash mismatch: {relative}")
    notebook = root / "notebooks/gqa_stage2_audit.ipynb"
    if digest(notebook) != manifest["notebook_sha256"]:
        errors.append("Notebook hash mismatch")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    nb, namespace, plots = json.loads(notebook.read_text()), {"_AUDIT_ROOT": root, "__name__": "__main__"}, 0
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        stdout, show = io.StringIO(), plt.show
        plt.close("all")
        plt.show = lambda *args, **kwargs: None
        try:
            with contextlib.redirect_stdout(stdout):
                exec("".join(cell["source"]), namespace)
            saved = "".join("".join(o["text"]) for o in cell["outputs"] if o["output_type"] == "stream")
            images_saved = sum("image/png" in o.get("data", {}) for o in cell["outputs"])
            if saved != stdout.getvalue() or images_saved != len(plt.get_fignums()):
                errors.append(f"Stale notebook cell: {cell['id']}")
            plots += images_saved
        finally:
            plt.show = show
            plt.close("all")
    report = {
        "status": "PASS" if not errors else "FAIL", "config_bundle_sha256": context["bundle"],
        "raw_question_counts": dict(raw_counts), "program_feature_rows_checked": feature_checks,
        "baseline_metrics_rescored": len(baseline_rows), "prediction_rows_checked": len(prediction),
        "notebook_plots_replayed": plots, "registry_sha256": recorded_hash, "errors": errors,
        "method": "Fresh raw-data recount, exact registry membership, independent Kahn DAG depths, prediction rescoring, source/artifact hashes and notebook replay",
    }
    (output / "independent_verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(verify_stage2(args.questions, Path(__file__).resolve().parent.parent))
