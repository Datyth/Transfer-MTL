"""Stage 1: streaming inspection and reviewable mapping proposals."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Iterator

import ijson
import yaml


SPLITS = ("train", "val", "testdev")
EXPECTED_FIELDS = (
    "imageId", "question", "answer", "fullAnswer", "isBalanced", "types",
    "semantic", "groups", "entailed", "equivalent", "annotations",
)
EXPECTED_STEP_FIELDS = ("operation", "argument", "dependencies")
ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "gqa_audit" / "config"
OUTPUT = ROOT / "gqa_audit" / "outputs" / "stage1"


def operation_head(operation: str) -> str:
    """The first whitespace-delimited token of a full operation string."""
    return operation.strip().split(maxsplit=1)[0] if operation.strip() else ""


def relation_flags(operation: str, argument: str, rules: dict[str, Any]) -> tuple[bool, bool]:
    """Evaluate the two relation definitions from the proposed config."""
    head = operation_head(operation)
    strict = head in rules["R_strict"]["operation_heads"]
    broad = strict or any(
        re.search(pattern, operation, flags=re.IGNORECASE)
        for pattern in rules["R_broad"]["operation_regexes"]
    ) or any(
        re.search(pattern, argument, flags=re.IGNORECASE)
        for pattern in rules["R_broad"]["argument_regexes"]
    )
    return strict, broad


def iter_records(path: Path) -> Iterator[tuple[str, Any]]:
    """Iterate question-id/record pairs without loading the top-level JSON dict."""
    with path.open("rb") as stream:
        yield from ijson.kvitems(stream, "")


def propose_type_mapping(raw_type: str, rules: dict[str, Any]) -> dict[str, Any]:
    matches = [p for p in rules["proposal_patterns"] if re.fullmatch(p["regex"], raw_type)]
    if not matches:
        return {
            "task": rules["unmatched_task"],
            "reason": rules["unmatched_reason"],
            "flag": "UNMATCHED",
        }
    tasks = {p["task"] for p in matches}
    if len(tasks) != 1:
        return {"task": "secondary", "reason": "Multiple proposal patterns matched", "flag": "AMBIGUOUS"}
    item = {"task": matches[0]["task"], "reason": matches[0]["reason"]}
    if any(p.get("ambiguous") for p in matches):
        item["flag"] = "AMBIGUOUS"
    return item


def propose_op_mapping(operation: str, rules: dict[str, Any]) -> dict[str, Any]:
    for pattern in rules["proposal_patterns"]:
        if re.search(pattern["regex"], operation):
            families = pattern["families"]
            if not set(families).issubset(rules["allowed_families"]):
                raise ValueError(f"Invalid family in config for {operation!r}")
            return {"families": families, "reason": f"Matched {pattern['regex']}"}
    return {"families": [], "flag": "UNMAPPED", "reason": "No proposal pattern fits; human review required"}


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _short_record(question_id: str, record: dict[str, Any]) -> dict[str, Any]:
    semantic = record.get("semantic")
    steps = semantic[:3] if isinstance(semantic, list) else []
    return {
        "question_id": question_id,
        "imageId": record.get("imageId"),
        "question": str(record.get("question", ""))[:180],
        "answer": record.get("answer"),
        "types": record.get("types"),
        "semantic_first_3": [
            {"operation": s.get("operation"), "argument": str(s.get("argument", ""))[:100]}
            for s in steps if isinstance(s, dict)
        ],
        "semantic_length": len(semantic) if isinstance(semantic, list) else None,
    }


def _record_issue(issues: Counter, examples: list[str], key: str, detail: str) -> None:
    issues[key] += 1
    if len(examples) < 30:
        examples.append(detail)


def _schema_report(
    split_sizes: Counter, key_counts: Counter, missing: Counter,
    examples: dict[str, list[dict[str, Any]]], issues: Counter, issue_examples: list[str],
) -> str:
    lines = ["# Stage 1 schema report", "", "| Split | Questions |", "|---|---:|"]
    lines.extend(f"| {split} | {split_sizes[split]:,} |" for split in SPLITS)
    lines += ["", "## Top-level field frequencies", "", "| Split | Field | Records |", "|---|---|---:|"]
    lines.extend(
        f"| {split} | `{field}` | {count:,} |"
        for (split, field), count in sorted(key_counts.items())
    )
    lines += ["", "## Missing expected fields", "", "| Split | Field | Missing |", "|---|---|---:|"]
    lines.extend(
        f"| {split} | `{field}` | {missing[(split, field)]:,} |"
        for split in SPLITS for field in EXPECTED_FIELDS
    )
    lines += ["", "## Other schema issues", "", "| Issue | Count |", "|---|---:|"]
    lines.extend(f"| {key} | {count:,} |" for key, count in sorted(issues.items()))
    lines += ["", "### Example issues", ""]
    lines.extend(f"- {detail}" for detail in issue_examples)
    for split in SPLITS:
        lines += ["", f"## Three abbreviated examples: {split}", ""]
        for item in examples[split]:
            lines += ["```json", json.dumps(item, ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines) + "\n"


def _manifest(question_paths: dict[str, Path], seed: int) -> dict[str, Any]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = None
    packages: dict[str, str | None] = {}
    for package in ("ijson", "pandas", "matplotlib", "PyYAML", "pytest", "numpy"):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
    return {
        "stage": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "seed": seed,
        "python": sys.version.split()[0],
        "packages": packages,
        "inputs": {
            split: {"path": str(path.resolve()), "size_bytes": path.stat().st_size, "sha256": _hash_file(path)}
            for split, path in question_paths.items()
        },
    }


def run_stage1(questions_dir: Path) -> int:
    """Write all Stage 1 artifacts and return nonzero when human intervention is required."""
    question_paths = {
        split: questions_dir / f"{split}_balanced_questions.json" for split in SPLITS
    }
    absent = [str(path) for path in question_paths.values() if not path.is_file()]
    if absent:
        print(f"Missing GQA question files: {', '.join(absent)}. No download attempted.", file=sys.stderr)
        return 2

    task_path = CONFIG / "task_rules.PROPOSED.yaml"
    op_path = CONFIG / "op_family_map.PROPOSED.yaml"
    with task_path.open(encoding="utf-8") as stream:
        task_rules = yaml.safe_load(stream)
    with op_path.open(encoding="utf-8") as stream:
        op_rules = yaml.safe_load(stream)
    if task_rules.get("status") != "PROPOSED" or op_rules.get("status") != "PROPOSED":
        raise ValueError("Stage 1 requires PROPOSED config files")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    split_sizes: Counter = Counter()
    key_counts: Counter = Counter()
    missing: Counter = Counter()
    issues: Counter = Counter()
    issue_examples: list[str] = []
    examples: dict[str, list[dict[str, Any]]] = {split: [] for split in SPLITS}
    inventory: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"answers": Counter(), "structural": Counter(), "semantic": Counter(), "count": 0}
    )
    operations: Counter = Counter()
    heads: Counter = Counter()
    arguments: dict[tuple[str, str], list[str]] = defaultdict(list)
    candidate: dict[tuple[str, str], Counter] = defaultdict(Counter)

    relation_path = OUTPUT / "relation_matches.csv"
    with relation_path.open("w", newline="", encoding="utf-8") as relation_stream:
        relation_writer = csv.writer(relation_stream)
        relation_writer.writerow(["split", "question_id", "step_index", "operation", "argument", "R_strict", "R_broad"])
        for split, path in question_paths.items():
            print(f"Scanning {split}: {path}", flush=True)
            try:
                for question_id, record in iter_records(path):
                    split_sizes[split] += 1
                    if not isinstance(record, dict):
                        _record_issue(issues, issue_examples, "record_not_object", f"{split}/{question_id}: record is not an object")
                        continue
                    for field in record:
                        key_counts[(split, field)] += 1
                    for field in EXPECTED_FIELDS:
                        if field not in record:
                            missing[(split, field)] += 1
                            _record_issue(issues, issue_examples, "missing_expected_field", f"{split}/{question_id}: missing {field}")
                    if len(examples[split]) < 3:
                        short = _short_record(question_id, record)
                        examples[split].append(short)
                        print(json.dumps({"split": split, **short}, ensure_ascii=False), flush=True)

                    types = record.get("types")
                    if not isinstance(types, dict):
                        _record_issue(issues, issue_examples, "invalid_types", f"{split}/{question_id}: types is not an object")
                        types = {}
                    for field in ("detailed", "structural", "semantic"):
                        if not isinstance(types.get(field), str):
                            _record_issue(issues, issue_examples, "missing_type_subfield", f"{split}/{question_id}: invalid types.{field}")
                    detailed = types.get("detailed") if isinstance(types.get("detailed"), str) else "__MISSING__"
                    item = inventory[(split, detailed)]
                    item["count"] += 1
                    item["structural"][str(types.get("structural", "__MISSING__"))] += 1
                    item["semantic"][str(types.get("semantic", "__MISSING__"))] += 1
                    answer = record.get("answer")
                    normalized = answer.strip().lower() if isinstance(answer, str) else ""
                    answer_class = normalized if normalized in {"yes", "no"} else "other"
                    item["answers"][answer_class] += 1

                    semantic = record.get("semantic")
                    if not isinstance(semantic, list):
                        _record_issue(issues, issue_examples, "invalid_semantic", f"{split}/{question_id}: semantic is not a list")
                        semantic = []
                    question_strict = question_broad = False
                    for index, step in enumerate(semantic):
                        if not isinstance(step, dict):
                            _record_issue(issues, issue_examples, "invalid_step", f"{split}/{question_id}/{index}: step is not an object")
                            continue
                        for field in EXPECTED_STEP_FIELDS:
                            if field not in step:
                                _record_issue(issues, issue_examples, "missing_step_field", f"{split}/{question_id}/{index}: missing {field}")
                        operation = step.get("operation")
                        argument = step.get("argument")
                        if not isinstance(operation, str) or not operation.strip():
                            _record_issue(issues, issue_examples, "invalid_operation", f"{split}/{question_id}/{index}: invalid operation")
                            continue
                        if not isinstance(argument, str):
                            _record_issue(issues, issue_examples, "invalid_argument", f"{split}/{question_id}/{index}: invalid argument")
                            argument = ""
                        if not isinstance(step.get("dependencies"), list):
                            _record_issue(issues, issue_examples, "invalid_dependencies", f"{split}/{question_id}/{index}: dependencies is not a list")
                        operations[(split, operation)] += 1
                        head = operation_head(operation)
                        heads[(split, head)] += 1
                        if argument not in arguments[(split, operation)] and len(arguments[(split, operation)]) < 3:
                            arguments[(split, operation)].append(argument)
                        strict, broad = relation_flags(operation, argument, task_rules["relation_definitions"])
                        question_strict |= strict
                        question_broad |= broad
                        if strict or broad:
                            relation_writer.writerow([split, question_id, index, operation, argument, int(strict), int(broad)])
                    count = candidate[(split, detailed)]
                    count["raw"] += 1
                    if answer_class in {"yes", "no"} and semantic:
                        count["eligible"] += 1
                        count["strict_removed"] += int(question_strict)
                        count["broad_removed"] += int(question_broad)
            except Exception as exc:
                _record_issue(issues, issue_examples, "parse_error", f"{split}: {type(exc).__name__}: {exc}")
                print(f"ERROR parsing {split}: {exc}", file=sys.stderr, flush=True)

    type_values = sorted({detailed for _, detailed in inventory})
    task_rules["type_mappings"] = {
        raw: propose_type_mapping(raw, task_rules) for raw in type_values
    }
    op_values = sorted({operation for _, operation in operations})
    op_rules["operations"] = {
        operation: propose_op_mapping(operation, op_rules) for operation in op_values
    }
    with task_path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(task_rules, stream, sort_keys=False, allow_unicode=True, width=120)
    with op_path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(op_rules, stream, sort_keys=False, allow_unicode=True, width=120)

    inventory_rows = []
    for (split, detailed), item in sorted(inventory.items()):
        n = item["count"]
        inventory_rows.append({
            "split": split, "types_detailed": detailed, "count": n,
            "structural_counts": json.dumps(item["structural"], sort_keys=True),
            "semantic_counts": json.dumps(item["semantic"], sort_keys=True),
            "yes_count": item["answers"]["yes"], "no_count": item["answers"]["no"],
            "other_count": item["answers"]["other"],
            "yes_fraction": item["answers"]["yes"] / n,
            "no_fraction": item["answers"]["no"] / n,
            "other_fraction": item["answers"]["other"] / n,
        })
    _write_csv(OUTPUT / "detailed_type_inventory.csv", [
        "split", "types_detailed", "count", "structural_counts", "semantic_counts",
        "yes_count", "no_count", "other_count", "yes_fraction", "no_fraction", "other_fraction",
    ], inventory_rows)
    operation_rows = [
        {"split": split, "operation": operation, "head": operation_head(operation),
         "operation_count": count, "head_count": heads[(split, operation_head(operation))],
         "example_arguments": json.dumps(arguments[(split, operation)], ensure_ascii=False)}
        for (split, operation), count in sorted(operations.items())
    ]
    _write_csv(OUTPUT / "operation_catalogue.csv", [
        "split", "operation", "head", "operation_count", "head_count", "example_arguments"
    ], operation_rows)

    candidate_rows = []
    for (split, detailed), counts in sorted(candidate.items()):
        mapping = task_rules["type_mappings"][detailed]
        if mapping["task"] == "secondary":
            continue
        candidate_rows.append({
            "split": split, "task": mapping["task"], "types_detailed": detailed,
            "raw_count": counts["raw"], "eligible_yesno_nonempty": counts["eligible"],
            "R_strict_removed": counts["strict_removed"] if task_rules["pilot_tasks"][mapping["task"]]["exclude_relation"] else 0,
            "R_broad_removed": counts["broad_removed"] if task_rules["pilot_tasks"][mapping["task"]]["exclude_relation"] else 0,
        })
    _write_csv(OUTPUT / "candidate_counts.csv", [
        "split", "task", "types_detailed", "raw_count", "eligible_yesno_nonempty",
        "R_strict_removed", "R_broad_removed",
    ], candidate_rows)

    (OUTPUT / "schema_report.md").write_text(
        _schema_report(split_sizes, key_counts, missing, examples, issues, issue_examples), encoding="utf-8"
    )
    summary = [
        "# Stage 1 summary — proposal only", "",
        "No task rules have been frozen. Review both `.PROPOSED.yaml` files before Stage 2.", "",
        "## Intended detailed-type families", "",
        "| Task | Detailed type | Train | Val | Testdev | Total | Flag |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    by_type = {(row["split"], row["types_detailed"]): row["count"] for row in inventory_rows}
    for detailed, mapping in task_rules["type_mappings"].items():
        if mapping["task"] == "secondary":
            continue
        nums = [by_type.get((split, detailed), 0) for split in SPLITS]
        summary.append(f"| {mapping['task']} | `{detailed}` | {nums[0]:,} | {nums[1]:,} | {nums[2]:,} | {sum(nums):,} | {mapping.get('flag', '')} |")
    summary += ["", "## Unmatched or ambiguous detailed types", ""]
    for detailed, mapping in task_rules["type_mappings"].items():
        if mapping["task"] == "secondary" or mapping.get("flag"):
            summary.append(f"- `{detailed}` → `{mapping['task']}` ({mapping.get('flag', 'review')}): {mapping['reason']}")
    summary += ["", "## Operation catalogue", "",
                f"- Unique full operation strings: **{len(op_values):,}**",
                f"- Unique heads: **{len({operation_head(op) for op in op_values}):,}**", ""]
    unmapped = [op for op, mapping in op_rules["operations"].items() if mapping.get("flag") == "UNMAPPED"]
    summary += [f"- Unmapped operation strings: **{len(unmapped):,}**", ""]
    summary.extend(f"  - `{op}`" for op in unmapped)
    summary += ["", "## Relation filter impact on eligible yes/no questions with nonempty programs", "",
                "| Task | Split | Eligible | R_strict removed | R_broad removed |",
                "|---|---|---:|---:|---:|"]
    task_order = list(task_rules["pilot_tasks"])
    for task in task_order:
        if not task_rules["pilot_tasks"][task]["exclude_relation"]:
            continue
        for split in SPLITS:
            rows = [row for row in candidate_rows if row["task"] == task and row["split"] == split]
            values = [sum(row[field] for row in rows) for field in ("eligible_yesno_nonempty", "R_strict_removed", "R_broad_removed")]
            summary.append(f"| {task} | {split} | {values[0]:,} | {values[1]:,} | {values[2]:,} |")
    summary += ["", "Exact matching operation and argument strings are in `relation_matches.csv`.", ""]
    (OUTPUT / "STAGE1_SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
    manifest = _manifest(question_paths, task_rules["seed"])
    manifest["schema_issue_counts"] = dict(issues)
    manifest["unmapped_operations"] = unmapped
    (OUTPUT / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    from .notebook import create_stage1_notebook
    create_stage1_notebook(OUTPUT, ROOT / "notebooks" / "gqa_stage1_audit.ipynb")

    assert sum(split_sizes.values()) == sum(row["count"] for row in inventory_rows), "Inventory total mismatch"
    assert set(op_values) == set(op_rules["operations"]), "Operation proposal coverage mismatch"
    print(f"Stage 1 artifacts: {OUTPUT}")
    if issues or unmapped or manifest["git_commit"] is None:
        print(f"Stage 1 needs review: {sum(issues.values())} schema issues, {len(unmapped)} unmapped operations, git commit={manifest['git_commit']}", file=sys.stderr)
        return 1
    print("Stage 1 inspection complete. STOP for human review; do not run Stage 2.")
    return 0
