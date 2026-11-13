"""Independently recount Stage 1 results from raw JSON and check saved notebook cells."""

from __future__ import annotations

import argparse
import base64
import contextlib
import csv
import hashlib
import io
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import ijson
import yaml


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_stage1(questions: Path, output: Path, notebook: Path) -> int:
    """Recount without using the production eligibility, relation or rollup functions."""
    manifest = json.loads((output / "run_manifest.json").read_text())
    task = yaml.safe_load((output / "task_rules.PROPOSED.yaml").read_text())
    family = yaml.safe_load((output / "answer_families.PROPOSED.yaml").read_text())["families"]
    candidate_rows = list(csv.DictReader((output / "candidate_counts.csv").open(newline="")))
    variant_rows = list(csv.DictReader((output / "variant_counts.csv").open(newline="")))
    actual_candidates = {(r["split"], r["types_detailed"]): r for r in candidate_rows}
    reference: dict = defaultdict(Counter)
    retained: dict = defaultdict(Counter)
    before: Counter = Counter()
    differences: Counter = Counter()
    totals: Counter = Counter()
    errors = []
    family_of = {t: name for name, f in family.items() for t in f["detailed_types"]}
    pilot = {t for t, m in task["type_mappings"].items() if m["task"] != task["unmatched_task"]}
    if set(family_of) != pilot or sum(len(f["detailed_types"]) for f in family.values()) != len(pilot):
        errors.append("Family coverage is not unique and complete")
    broad = task["relation_definitions"]["R_broad"]
    op_patterns = [re.compile(p, re.IGNORECASE) for p in broad["operation_regexes"]]
    arg_patterns = [re.compile(p, re.IGNORECASE) for p in broad["argument_regexes"]]
    splits = tuple(manifest["inputs"])
    for split in splits:
        path = questions / f"{split}_balanced_questions.json"
        if _sha(path) != manifest["inputs"][split]["sha256"]:
            errors.append(f"{split}: input SHA-256 differs")
        with path.open("rb") as stream:
            for question_id, record in ijson.kvitems(stream, ""):
                if type(question_id) is not str:
                    errors.append(f"{split}: question ID is not a string")
                totals[split] += 1
                detailed = record["types"]["detailed"]
                if detailed not in pilot:
                    continue
                assigned = task["type_mappings"][detailed]["task"]
                answer = record["answer"].strip().lower()
                program = record["semantic"]
                c = reference[(split, detailed)]
                c["raw_count"] += 1
                c[answer if answer in ("yes", "no") else "nonbinary"] += 1
                c["n_empty_program"] += int(len(program) == 0)
                c["n_binary_empty_program"] += int(not program and answer in ("yes", "no"))
                if answer not in ("yes", "no") or not isinstance(program, list) or len(program) == 0:
                    continue
                c["eligible"] += 1
                c["eligible_yesno_nonempty"] += 1
                c[f"eligible_{answer}"] += 1
                strict = any(s["operation"].strip().split()[0] in task["relation_definitions"]["R_strict"]["operation_heads"]
                             for s in program)
                broad_flag = strict or any(
                    any(p.search(s["operation"]) for p in op_patterns)
                    or any(p.search(s["argument"]) for p in arg_patterns) for s in program
                )
                c["R_strict_detected"] += strict
                c["R_broad_detected"] += broad_flag
                if task["pilot_tasks"][assigned]["exclude_relation"]:
                    c["R_strict_removed"] += strict
                    c["R_broad_removed"] += broad_flag
                if assigned == task["diagnostics"]["semantic_filter_task"]:
                    c["semantic_filter_removed"] += record["types"]["semantic"] != task["diagnostics"]["semantic_filter_value"]
                membership = {}
                for name, filters in task["audit_variants"].items():
                    f = filters.get(assigned, {})
                    keep = not (
                        (f.get("relation") == "R_strict" and strict)
                        or (f.get("relation") == "R_broad" and broad_flag)
                        or ("types_semantic" in f and record["types"]["semantic"] != f["types_semantic"])
                    )
                    membership[name] = keep
                    for level, unit in (("task", ""), ("family", family_of[detailed])):
                        key = (level, name, split, assigned, unit)
                        before[key] += 1
                        if keep:
                            retained[key][answer] += 1
                for left, right in itertools.combinations(membership, 2):
                    differences[(left, right, split, assigned)] += membership[left] != membership[right]
    expected_keys = {(split, t) for split in splits for t in pilot}
    if set(actual_candidates) != expected_keys or len(candidate_rows) != len(expected_keys):
        errors.append("Candidate rows are missing or duplicated")
    fields = [
        "raw_count", "eligible", "eligible_yesno_nonempty", "n_empty_program",
        "n_binary_empty_program", "yes", "no", "nonbinary", "eligible_yes", "eligible_no",
        "R_strict_detected", "R_broad_detected", "R_strict_removed", "R_broad_removed", "semantic_filter_removed",
    ]
    for key, row in actual_candidates.items():
        for field in fields:
            expected = reference[key][field]
            if int(row[field]) != expected:
                errors.append(f"{key}/{field}: saved={row[field]}, raw={expected}")
    seen = set()
    for row in variant_rows:
        key = (row["level"], row["variant"], row["split"], row["task"], row["family"])
        if key in seen:
            errors.append(f"Duplicate variant row {key}")
        seen.add(key)
        expected = retained[key]
        n = expected["yes"] + expected["no"]
        for field, value in (("questions", n), ("yes", expected["yes"]), ("no", expected["no"]),
                             ("eligible_before_filter", before[key]), ("excluded", before[key] - n)):
            if int(row[field]) != value:
                errors.append(f"{key}/{field}: saved={row[field]}, raw={value}")
        if n and abs(float(row["yes_ratio"]) - expected["yes"] / n) > 1e-12:
            errors.append(f"{key}: wrong yes ratio")
    expected_variants = {
        (level, variant, split, task_name, name)
        for variant in task["audit_variants"] for split in splits
        for level, task_name, name in (
            [("task", t, "") for t in task["pilot_tasks"]]
            + [("family", f["task"], name) for name, f in family.items()]
        )
    }
    if seen != expected_variants:
        errors.append("Variant row coverage differs")
    for row in csv.DictReader((output / "variant_equivalence.csv").open(newline="")):
        key = (row["left_variant"], row["right_variant"], row["split"], row["task"])
        if int(row["different_questions"]) != differences[key]:
            errors.append(f"Membership comparison mismatch: {key}")
    for name, record in manifest["configs"].items():
        if _sha(output / name) != record["sha256"]:
            errors.append(f"Config snapshot hash mismatch: {name}")
        if _sha(Path(record["path"])) != record["sha256"]:
            errors.append(f"Active config differs from snapshot: {name}")
    for relative, digest in manifest["source_sha256"].items():
        if _sha(output.parents[2] / relative) != digest:
            errors.append(f"Source hash mismatch: {relative}")
    if manifest["schema_issue_counts"] or manifest["unmapped_operations"] or manifest["validation"]["fail"]:
        errors.append("The production run reports failed integrity checks")
    inventory_totals: Counter = Counter()
    for row in csv.DictReader((output / "detailed_type_inventory.csv").open(newline="")):
        inventory_totals[row["split"]] += int(row["count"])
    if totals != inventory_totals:
        errors.append(f"Inventory differs from raw split totals: {totals} vs {inventory_totals}")
    # Execute the actual saved code and compare saved stdout/figure counts.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    nb = json.loads(notebook.read_text())
    namespace = {"__name__": "__main__", "_AUDIT_ROOT": output.parents[2]}
    images = 0
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        stdout = io.StringIO()
        original_show = plt.show
        plt.close("all")
        plt.show = lambda *args, **kwargs: None
        try:
            with contextlib.redirect_stdout(stdout):
                exec(compile("".join(cell["source"]), "<verify-notebook>", "exec"), namespace)
            saved_text = "".join("".join(o["text"]) for o in cell["outputs"] if o["output_type"] == "stream")
            if saved_text != stdout.getvalue():
                errors.append(f"Stale notebook stdout: {cell['id']}")
            saved_images = [o["data"]["image/png"] for o in cell["outputs"] if "image/png" in o.get("data", {})]
            if len(saved_images) != len(plt.get_fignums()):
                errors.append(f"Stale notebook figures: {cell['id']}")
            for png in saved_images:
                if not base64.b64decode(png).startswith(b"\x89PNG\r\n\x1a\n"):
                    errors.append(f"Invalid embedded PNG: {cell['id']}")
            images += len(saved_images)
        finally:
            plt.show = original_show
            plt.close("all")
    report = {
        "status": "PASS" if not errors else "FAIL",
        "raw_question_counts": dict(totals), "candidate_rows_checked": len(candidate_rows),
        "variant_rows_checked": len(variant_rows), "embedded_plots_checked": images,
        "errors": errors,
        "method": "Separate raw JSON recount; production eligibility, relation and rollup functions are not reused",
    }
    (output / "independent_verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    raise SystemExit(verify_stage1(
        args.questions, root / "gqa_audit/outputs/stage1", root / "notebooks/gqa_stage1_audit.ipynb",
    ))
