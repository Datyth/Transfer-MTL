"""Family, filter-sensitivity and consistency reports for the Stage 1 review."""

from __future__ import annotations

import itertools
import json
from collections import Counter, defaultdict
from typing import Any


def propose_families(mappings: dict, rules: dict, secondary: str) -> dict:
    pilot = {typ for typ, mapping in mappings.items() if mapping["task"] != secondary}
    overrides = {
        member: name for name, members in rules["overrides"].items() for member in members
    }
    families: dict[str, dict[str, Any]] = {}
    for typ in sorted(pilot):
        family = overrides.get(typ, typ)
        if typ not in overrides:
            for suffix in rules["pairing_suffixes"]:
                if typ.endswith(suffix) and typ[:-len(suffix)] in pilot:
                    family = typ[:-len(suffix)]
                    break
        entry = families.setdefault(family, {
            "task": mappings[typ]["task"], "detailed_types": [],
            "reason": "Provisional suffix pairing; meaning requires human review",
        })
        if entry["task"] != mappings[typ]["task"]:
            raise ValueError(f"Family {family} crosses tasks")
        entry["detailed_types"].append(typ)
    return families


def accepts(signature: tuple, task: str, filters: dict) -> bool:
    _, strict, broad, semantic_label = signature
    rule = filters.get(task, {})
    relation = rule.get("relation")
    if relation == "R_strict" and strict:
        return False
    if relation == "R_broad" and broad:
        return False
    return "types_semantic" not in rule or semantic_label == rule["types_semantic"]


def build_variant_rows(signatures: dict, mappings: dict, rules: dict, families: dict, splits: tuple) -> tuple[list, list]:
    family_of = {typ: name for name, family in families.items() for typ in family["detailed_types"]}
    rows = []
    for variant, filters in rules["audit_variants"].items():
        for split in splits:
            for level in ("task", "family"):
                units = (
                    [(task, "", [t for t in family_of if mappings[t]["task"] == task])
                     for task in rules["pilot_tasks"]]
                    if level == "task" else
                    [(family["task"], name, family["detailed_types"]) for name, family in families.items()]
                )
                for task, name, types in units:
                    retained: Counter = Counter()
                    eligible = 0
                    for typ in types:
                        for signature, count in signatures.get((split, typ), {}).items():
                            eligible += count
                            if accepts(signature, task, filters):
                                retained[signature[0]] += count
                    n = retained["yes"] + retained["no"]
                    flag = "EMPTY" if n == 0 else (
                        "SINGLE_CLASS" if not retained["yes"] or not retained["no"] else ""
                    )
                    rows.append({
                        "level": level, "variant": variant, "split": split, "task": task, "family": name,
                        "eligible_before_filter": eligible, "questions": n,
                        "yes": retained["yes"], "no": retained["no"],
                        "yes_ratio": retained["yes"] / n if n else "",
                        "excluded": eligible - n,
                        "exclusion_rate": (eligible - n) / eligible if eligible else "",
                        "flag": flag,
                    })
    equivalence = []
    for left, right in itertools.combinations(rules["audit_variants"], 2):
        for split in splits:
            for task in rules["pilot_tasks"]:
                differences = sum(
                    count
                    for typ in family_of if mappings[typ]["task"] == task
                    for signature, count in signatures.get((split, typ), {}).items()
                    if accepts(signature, task, rules["audit_variants"][left])
                    != accepts(signature, task, rules["audit_variants"][right])
                )
                equivalence.append({
                    "left_variant": left, "right_variant": right, "split": split,
                    "task": task, "different_questions": differences,
                    "identical_membership": int(differences == 0),
                })
    return rows, equivalence


def check_aggregates(inventory: list, candidates: list, operations: list, sizes: Counter, mappings: dict,
                     rules: dict, families: dict, variants: list, taxonomy_errors: Counter) -> list:
    """Use separate raw counters to catch eligibility and rollup regressions."""
    checks = []

    def check(name: str, scope: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "scope": scope, "status": "PASS" if ok else "FAIL", "detail": detail})

    inv = {(r["split"], r["types_detailed"]): r for r in inventory}
    for split, total in sizes.items():
        reported = sum(r["count"] for r in inventory if r["split"] == split)
        check("inventory_total", split, total == reported, f"stream={total}; inventory={reported}")
    for row in candidates:
        scope = f"{row['split']}/{row['types_detailed']}"
        item = inv.get((row["split"], row["types_detailed"]), {"count": 0, "yes_count": 0, "no_count": 0})
        expected = item["yes_count"] + item["no_count"] - row["n_binary_empty_program"]
        check("eligibility", scope,
              row["raw_count"] == item["count"] and row["eligible"] == expected,
              f"raw={row['raw_count']}; eligible={row['eligible']}; independently_expected={expected}")
        check("relation_bounds", scope,
              0 <= row["R_strict_detected"] <= row["R_broad_detected"] <= row["eligible"],
              f"strict={row['R_strict_detected']}; broad={row['R_broad_detected']}; eligible={row['eligible']}")
    head_groups: dict = defaultdict(list)
    for row in operations:
        head_groups[(row["split"], row["head"])].append(row)
    check("operation_head_totals", "all", all(
        sum(r["operation_count"] for r in rows) == rows[0]["head_count"] for rows in head_groups.values()
    ), "Each full operation contributes once to its head total")
    members = [typ for family in families.values() for typ in family["detailed_types"]]
    pilot = {typ for typ, m in mappings.items() if m["task"] != rules["unmatched_task"]}
    check("family_coverage", "all", len(members) == len(set(members)) and set(members) == pilot,
          f"{len(members)} memberships; {len(pilot)} pilot detailed types")
    for row in variants:
        if row["level"] != "task":
            continue
        child = [r for r in variants if r["level"] == "family" and
                 (r["variant"], r["split"], r["task"]) == (row["variant"], row["split"], row["task"])]
        check("family_task_rollup", f"{row['variant']}/{row['split']}/{row['task']}",
              all(sum(r[field] for r in child) == row[field] for field in ("questions", "yes", "no")),
              f"task_questions={row['questions']}")
    check("taxonomy_labels", "all", not taxonomy_errors, json.dumps(dict(taxonomy_errors), sort_keys=True))
    return checks


def suffix_report(samples: dict, inventory: list, mappings: dict, secondary: str, sample_size: int, seed: int) -> str:
    fence = chr(96) * 3
    lines = [
        "# Train examples for detailed-type review", "",
        f"Seed {seed} reservoir samples, at most {sample_size} per pilot detailed type. "
        "Suffix meanings are not interpreted. Counts and observations refer to train.", "",
    ]
    train = {row["types_detailed"]: row for row in inventory if row["split"] == "train"}
    for typ, mapping in mappings.items():
        if mapping["task"] == secondary:
            continue
        row = train.get(typ, {"count": 0, "yes_count": 0, "no_count": 0})
        terminals = sorted({
            record["semantic"][-1].get("operation", "MISSING")
            for record in samples.get(typ, [])
            if record["semantic"] and isinstance(record["semantic"][-1], dict)
        })
        lines += [
            f"## {typ} ({mapping['task']})", "",
            f"Observation: {row['count']} train questions; yes={row['yes_count']}, no={row['no_count']}; "
            f"{len(samples.get(typ, []))} examples shown; sampled terminal operations={terminals}. "
            "The suffix alone is not assigned a meaning.", "",
        ]
        for record in samples.get(typ, []):
            lines += [
                f"### Question {record['question_id']}", "",
                f"Question: {record['question']}", f"Answer: {record['answer']}", "",
                fence + "text",
            ]
            for index, step in enumerate(record["semantic"]):
                if not isinstance(step, dict):
                    lines.append(f"{index}: INVALID STEP {step!r}")
                    continue
                lines.append(
                    f"{index}: {step.get('operation')} | {step.get('argument')} | deps={step.get('dependencies')}"
                )
            lines += [fence, ""]
    return "\n".join(lines) + "\n"


def diagnostics_summary(variants: list, equivalence: list, checks: list, families: dict) -> str:
    lines = [
        "", "## Eligibility correction and validation", "",
        "The previous run was invalid for eligibility and filter impact: unquoted YAML yes/no values "
        "were loaded as booleans, so string answers never matched. The config now uses quoted strings "
        "and is type-checked before scanning. Raw answer counts independently check every pilot type's "
        "eligible count. No task definitions were changed for this correction.", "",
        f"Integrity checks: {sum(c['status'] == 'PASS' for c in checks)} PASS, "
        f"{sum(c['status'] == 'FAIL' for c in checks)} FAIL. See validation_checks.csv.", "",
        "## Task counts by proposed variant", "",
        "All variants are diagnostics, not a frozen primary rule. semantic_sensitivity replaces the exist "
        "program filter with the benchmark semantic label. See variant_equivalence.csv for exact membership comparisons.", "",
        "| Variant | Task | Split | Questions | Yes ratio | Filter exclusion rate |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in variants:
        if row["level"] == "task":
            ratio = f"{row['yes_ratio']:.4f}" if row["yes_ratio"] != "" else "N/A"
            excluded = f"{row['exclusion_rate']:.4f}" if row["exclusion_rate"] != "" else "N/A"
            lines.append(f"| {row['variant']} | {row['task']} | {row['split']} | {row['questions']:,} | {ratio} | {excluded} |")
    lines += ["", "## Answer-family pairing and flags", "",
              "| Task | Family | Detailed types | Train yes | Train no | Flag |",
              "|---|---|---|---:|---:|---|"]
    lookup = {row["family"]: row for row in variants if row["level"] == "family"
              and row["variant"] == "unfiltered" and row["split"] == "train"}
    for name, family in families.items():
        row = lookup[name]
        lines.append(f"| {family['task']} | {name} | {', '.join(family['detailed_types'])} | "
                     f"{row['yes']} | {row['no']} | {row['flag']} |")
    lines += [
        "", "Single-class and empty families are reported without rebalancing or changing assignments. "
        "Family flags per split and variant are in variant_counts.csv.", "",
        "## Suffix examples and open decisions", "",
        "See suffix_examples.md for up to five seeded train examples and a factual observation per detailed type. "
        "The meanings of Co, Cr, Cop, K, That and other suffixes remain for human review.", "",
        "Material/position verification and animal/gender comparison types remain secondary in this rerun. "
        "The previous task proposal is preserved so the bug correction is comparable. "
        "Their inclusion, family pooling, and a primary relation rule require human review.", "",
    ]
    return "\n".join(lines)
