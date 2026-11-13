"""Validate study rules before scanning data and share eligibility semantics."""

from __future__ import annotations

import re
from typing import Any


def validate_configs(task: dict, operations: dict, families: dict) -> None:
    """Reject ambiguous YAML types and invalid rules before any outputs change."""
    for label, config in (("task_rules", task), ("op_family_map", operations), ("answer_families", families)):
        if not isinstance(config, dict) or config.get("status") != "PROPOSED":
            raise ValueError(f"{label}: Stage 1 requires a PROPOSED mapping")
    eligibility = task["eligibility"]
    answers = eligibility["binary_answers"]
    if not isinstance(answers, list) or any(type(a) is not str for a in answers):
        raise ValueError(
            "eligibility.binary_answers must contain strings: ['yes', 'no']. "
            "Quote yes/no in YAML; PyYAML converts unquoted values to booleans."
        )
    if len(answers) != 2 or set(answers) != {"yes", "no"}:
        raise ValueError("This audit requires exactly the string answers 'yes' and 'no'")
    if eligibility.get("require_nonempty_semantic") is not True:
        raise ValueError("The study requires require_nonempty_semantic: true")
    if type(task.get("seed")) is not int or task["seed"] < 0:
        raise ValueError("seed must be a nonnegative integer")
    tasks = set(task["pilot_tasks"])
    if task["unmatched_task"] in tasks:
        raise ValueError("The secondary task must be separate from pilot tasks")
    for name, rule in task["pilot_tasks"].items():
        if type(rule.get("exclude_relation")) is not bool:
            raise ValueError(f"{name}.exclude_relation must be a boolean")
    for rule in task["proposal_patterns"]:
        re.compile(rule["regex"])
        if rule["task"] not in tasks:
            raise ValueError(f"Unknown pilot task: {rule['task']}")
    for rule in operations["proposal_patterns"]:
        re.compile(rule["regex"])
        if not rule["families"] or not set(rule["families"]) <= set(operations["allowed_families"]):
            raise ValueError("Invalid operation-family proposal")
    relations = task["relation_definitions"]
    heads = relations["R_strict"]["operation_heads"]
    if not heads or any(type(head) is not str for head in heads):
        raise ValueError("R_strict operation heads must be strings")
    for field in ("operation_regexes", "argument_regexes"):
        for pattern in relations["R_broad"][field]:
            re.compile(pattern)
    for variant, filters in task["audit_variants"].items():
        if not isinstance(filters, dict) or not set(filters) <= tasks:
            raise ValueError(f"Invalid tasks in variant {variant}")
        for task_filter in filters.values():
            if not set(task_filter) <= {"relation", "types_semantic"}:
                raise ValueError(f"Unknown filter in variant {variant}")
            if "relation" in task_filter and task_filter["relation"] not in relations:
                raise ValueError(f"Unknown relation definition in variant {variant}")
            if "types_semantic" in task_filter and type(task_filter["types_semantic"]) is not str:
                raise ValueError("types_semantic filters must be strings")
    if type(task["diagnostics"]["samples_per_type"]) is not int or task["diagnostics"]["samples_per_type"] < 1:
        raise ValueError("samples_per_type must be positive")
    if not set(task["diagnostics"]["exhaustive_taxonomy_tasks"]) <= set(task["diagnostics"]["taxonomy_checks"]):
        raise ValueError("Exhaustive taxonomy tasks require expected labels")
    if any(type(suffix) is not str or not suffix for suffix in families["pairing_suffixes"]):
        raise ValueError("Family pairing suffixes must be nonempty strings")
    for name, members in families["overrides"].items():
        if type(name) is not str or not members or any(type(t) is not str for t in members):
            raise ValueError("Family overrides must list detailed-type strings")
    flat = [member for members in families["overrides"].values() for member in members]
    if len(flat) != len(set(flat)):
        raise ValueError("A detailed type occurs in multiple family overrides")


def is_eligible(answer: Any, semantic: Any, rules: dict) -> bool:
    """Accept only a binary string answer and an actual, nonempty program list."""
    return (
        isinstance(answer, str)
        and answer.strip().lower() in rules["binary_answers"]
        and isinstance(semantic, list)
        and (len(semantic) > 0 or not rules["require_nonempty_semantic"])
    )
