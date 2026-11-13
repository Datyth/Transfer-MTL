"""Stream frozen GQA data into compact, validated Parquet caches."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .stage1 import iter_records
from .stage2_core import canonical_hash, decompose_logic, file_hash, graph_depth


SCHEMA = pa.schema([
    (name, pa.string()) for name in (
        "question_id", "image_id", "detailed", "structural", "semantic_type", "task", "family", "stratum",
        "question", "answer", "program_json", "depth_reason", "logic_json",
    )
] + [
    ("eligible", pa.bool_()), ("binary", pa.bool_()), ("empty_program", pa.bool_()), ("strict", pa.bool_()),
    ("program_length", pa.int32()), ("relation_steps", pa.int32()), ("depth", pa.float64()),
    ("op_families", pa.list_(pa.string())), ("entailed", pa.list_(pa.string())),
    ("equivalent", pa.list_(pa.string())), ("verify_rel_dash", pa.bool_()), ("any_dash", pa.bool_()),
])


def cache_record(qid: str, record: dict, split: str, context: dict) -> dict:
    if type(qid) is not str or not isinstance(record, dict):
        raise ValueError("Question IDs must be strings and records must be objects")
    for key in ("imageId", "question", "answer"):
        if not isinstance(record.get(key), str):
            raise ValueError(f"{qid}: {key} must be a string")
    types = record["types"]
    detailed = types["detailed"]
    rules = context["task_rules"]
    if detailed not in rules["type_mappings"]:
        raise ValueError(f"{qid}: detailed type absent from frozen map: {detailed}")
    task = rules["type_mappings"][detailed]["task"]
    program = record["semantic"]
    if not isinstance(program, list):
        raise ValueError(f"{qid}: semantic must be a list")
    for step in program:
        if not isinstance(step, dict) or not isinstance(step.get("operation"), str) or not isinstance(step.get("argument"), str):
            raise ValueError(f"{qid}: malformed program step")
        if step["operation"] not in context["op_family_map"]["operations"]:
            raise ValueError(f"{qid}: unmapped frozen operation: {step['operation']}")
    for key in ("entailed", "equivalent"):
        if not isinstance(record.get(key), list) or any(type(x) is not str for x in record[key]):
            raise ValueError(f"{qid}: {key} references must remain strings")
    for field, expected in rules["diagnostics"]["taxonomy_checks"].get(task, {}).items():
        if types[field] != expected:
            raise ValueError(f"{qid}: taxonomy mismatch for {task}")
    for expected_task in rules["diagnostics"]["exhaustive_taxonomy_tasks"]:
        expected = rules["diagnostics"]["taxonomy_checks"][expected_task]
        exceptions = rules["diagnostics"]["exhaustive_taxonomy_exceptions"].get(expected_task, [])
        if all(types[k] == v for k, v in expected.items()) and task != expected_task and detailed not in exceptions:
            raise ValueError(f"{qid}: unapproved exhaustive taxonomy exception")
    answer = record["answer"].strip().lower()
    binary = answer in rules["eligibility"]["binary_answers"]
    eligible = binary and bool(program)
    strict_heads = rules["relation_definitions"]["R_strict"]["operation_heads"]
    relation_steps = sum(s["operation"].split()[0] in strict_heads for s in program)
    analyze = split != "testdev" and task in rules["pilot_tasks"] and eligible
    depth, reason = graph_depth(program) if analyze else (math.nan, "")
    families = sorted({
        f for s in program for f in context["op_family_map"]["operations"][s["operation"]]["families"]
    }) if analyze else []
    logic = decompose_logic(program, context) if analyze and task == "logic" else None
    return {
        "question_id": qid, "image_id": record["imageId"], "detailed": detailed,
        "structural": types["structural"], "semantic_type": types["semantic"],
        "task": task, "family": context["family_of"].get(detailed, ""),
        "stratum": context["stratum_of"].get(detailed, ""),
        "question": record["question"] if analyze else None, "answer": answer if binary else "other",
        "program_json": json.dumps(program, separators=(",", ":")) if analyze else None,
        "eligible": eligible, "binary": binary, "empty_program": not bool(program), "strict": bool(relation_steps),
        "program_length": len(program) if analyze else None, "relation_steps": relation_steps if analyze else None,
        "depth": depth, "depth_reason": reason, "op_families": families,
        "logic_json": json.dumps(logic, separators=(",", ":")) if logic else None,
        "entailed": record["entailed"], "equivalent": record["equivalent"],
        "verify_rel_dash": any(s["operation"] == "verify rel" and "(-)" in s["argument"] for s in program) if analyze else None,
        "any_dash": any("(-)" in s["argument"] for s in program) if analyze else None,
    }


def build_cache(path: Path, target: Path, split: str, context: dict) -> None:
    fingerprint = canonical_hash({
        "config_bundle": context["bundle"], "input": context["manifest"]["input_sha256"][split],
        "data_code": file_hash(Path(__file__)), "core_code": file_hash(Path(__file__).with_name("stage2_core.py")),
    })
    if target.exists() and pq.read_metadata(target).metadata.get(b"fingerprint") == fingerprint.encode():
        print(f"Validated cache reused: {split}", flush=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA.with_metadata({
        b"fingerprint": fingerprint.encode(), b"config_bundle_sha256": context["bundle"].encode(),
        b"frozen_config_hashes": json.dumps(context["hashes"], sort_keys=True).encode(),
        b"testdev_policy": b"counts_only_no_text_program_or_features",
    })
    temporary = target.with_suffix(".parquet.tmp")
    count, batch = 0, []
    try:
        with pq.ParquetWriter(temporary, schema, compression="zstd") as writer:
            for qid, record in iter_records(path):
                batch.append(cache_record(qid, record, split, context))
                count += 1
                if len(batch) >= context["runtime"]["cache_batch_size"]:
                    writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                    batch.clear()
                    if count % 100000 == 0:
                        print(f"Cached {split}: {count:,}", flush=True)
            if batch:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))
        if count != context["manifest"]["raw_question_counts"][split]:
            raise ValueError(f"{split}: raw record count differs from frozen manifest")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


BASIC_COLUMNS = [
    "question_id", "image_id", "detailed", "task", "family", "stratum", "answer", "eligible",
    "binary", "empty_program", "strict", "semantic_type", "entailed", "equivalent",
]


def load_tables(cache_dir: Path, context: dict) -> tuple[dict, dict]:
    basic, pilot = {}, {}
    tasks = list(context["task_rules"]["pilot_tasks"])
    for split in ("train", "val", "testdev"):
        path = cache_dir / f"questions_{split}.parquet"
        basic[split] = pq.read_table(path, columns=BASIC_COLUMNS).to_pandas()
        if basic[split]["question_id"].duplicated().any():
            raise ValueError(f"Duplicate question IDs within {split}")
        if split != "testdev":
            pilot[split] = pq.read_table(
                path, filters=[("eligible", "=", True), ("task", "in", tasks)]
            ).to_pandas()
        else:
            pilot[split] = basic[split][basic[split].eligible & basic[split].task.isin(tasks)].copy()
    return basic, pilot


def retained_mask(frame: pd.DataFrame, variant: str, context: dict):
    rules = context["task_rules"]
    mask = frame["eligible"] & frame["task"].isin(rules["pilot_tasks"])
    for task, rule in rules["audit_variants"][variant].items():
        if rule != {"relation": "R_strict"}:
            raise ValueError("Only the frozen strict relation filter is supported")
        mask &= ~(frame["task"].eq(task) & frame["strict"])
    return mask


def regression_rows(basic: dict, context: dict) -> list:
    rows = []
    for target in context["manifest"]["regression_targets"]["unfiltered_and_program_strict_by_task"]:
        split, task = target["split"], target["task"]
        frame = basic[split]
        for variant in context["task_rules"]["audit_variants"]:
            selected = frame[retained_mask(frame, variant, context) & frame["task"].eq(task)]
            n, yes = len(selected), int(selected["answer"].eq("yes").sum())
            expected, expected_yes = target[variant], target[f"{variant}_yes"]
            rows.append({
                "kind": "task", "split": split, "task": task, "stratum": "", "variant": variant,
                "expected": expected, "actual": n, "yes_count_matches": yes == expected_yes,
                "status": "PASS" if n == expected and yes == expected_yes else "FAIL",
            })
    for target in context["manifest"]["regression_targets"]["strata"]:
        frame = basic[target["split"]]
        for variant in context["task_rules"]["audit_variants"]:
            n = int((retained_mask(frame, variant, context) & frame["task"].eq(target["task"])
                     & frame["stratum"].eq(target["stratum"])).sum())
            rows.append({
                "kind": "stratum", "split": target["split"], "task": target["task"],
                "stratum": target["stratum"], "variant": variant, "expected": target[variant],
                "actual": n, "yes_count_matches": "", "status": "PASS" if n == target[variant] else "FAIL",
            })
    check = context["task_rules"]["diagnostics"]["crosschecks"]["exist_semantic_equals_program_strict"]
    for split, frame in basic.items():
        eligible = frame["eligible"] & frame["task"].eq(check["task"])
        differing = int((eligible & (frame["semantic_type"].eq(check["types_semantic"])
                                     != ~frame["strict"])).sum())
        rows.append({
            "kind": "membership_crosscheck", "split": split, "task": check["task"], "stratum": "",
            "variant": check["variant"], "expected": check["expected_differing_questions"],
            "actual": differing, "yes_count_matches": "",
            "status": "PASS" if differing == check["expected_differing_questions"] else "FAIL",
        })
    return rows
