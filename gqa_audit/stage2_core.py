"""Frozen rules, graph primitives and question-only baseline interfaces."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
import yaml


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                    allow_nan=False).encode("utf-8")).hexdigest()


def load_frozen(config_dir: Path) -> dict:
    manifest = json.loads((config_dir / "FROZEN_MANIFEST.json").read_text())
    if manifest.get("status") != "FROZEN":
        raise ValueError("A FROZEN manifest is required")
    configs, hashes = {}, {}
    for stem in ("task_rules", "op_family_map", "answer_families"):
        path = config_dir / f"{stem}.yaml"
        digest = file_hash(path)
        if digest != manifest["frozen_files_sha256"][f"{stem}.FROZEN.yaml"]:
            raise ValueError(f"FROZEN hash mismatch: {path}")
        configs[stem] = yaml.safe_load(path.read_text())
        hashes[stem] = digest
        if configs[stem].get("status") != "FROZEN":
            raise ValueError(f"{stem} is not FROZEN")
    rules = configs["task_rules"]
    if rules["eligibility"]["binary_answers"] != ["yes", "no"]:
        raise ValueError("Frozen eligibility must contain string yes/no, not YAML booleans")
    if rules["eligibility"]["require_nonempty_semantic"] is not True:
        raise ValueError("Nonempty list programs are required")
    if not 0 < rules["splits"]["dev_fraction_of_train_images"] < 1:
        raise ValueError("Invalid dev image fraction")
    if rules["splits"]["testdev"] != "sealed_counts_only":
        raise ValueError("This implementation requires sealed count-only testdev")
    tasks = set(rules["pilot_tasks"])
    if any(m["task"] not in tasks | {rules["unmatched_task"]} for m in rules["type_mappings"].values()):
        raise ValueError("Unknown task in frozen mapping")
    family_of = {}
    for name, family in configs["answer_families"]["families"].items():
        for typ in family["detailed_types"]:
            if typ in family_of or rules["type_mappings"][typ]["task"] != family["task"]:
                raise ValueError(f"Duplicate or inconsistent frozen family: {typ}")
            family_of[typ] = name
    pilot = {t for t, m in rules["type_mappings"].items() if m["task"] in tasks}
    if not pilot <= set(family_of):
        raise ValueError("Incomplete pilot family coverage")
    strata = {}
    for task, definitions in rules["strata"].items():
        members = []
        for name, types in definitions.items():
            for typ in types:
                if rules["type_mappings"][typ]["task"] != task or typ in strata:
                    raise ValueError("Invalid stratum membership")
                strata[typ] = name
                members.append(typ)
        if set(members) != {t for t in pilot if rules["type_mappings"][t]["task"] == task}:
            raise ValueError(f"Strata do not cover {task}")
    allowed = set(configs["op_family_map"]["allowed_families"])
    if any(not v["families"] or not set(v["families"]) <= allowed
           for v in configs["op_family_map"]["operations"].values()):
        raise ValueError("Invalid frozen operation family")
    runtime_path = config_dir / "audit_runtime.yaml"
    runtime = yaml.safe_load(runtime_path.read_text())
    hashes["audit_runtime"] = file_hash(runtime_path)
    hashes["frozen_manifest"] = file_hash(config_dir / "FROZEN_MANIFEST.json")
    return {
        **configs, "manifest": manifest, "runtime": runtime, "hashes": hashes,
        "bundle": canonical_hash(hashes), "family_of": family_of, "stratum_of": strata,
    }


def graph_depth(program: list) -> tuple[float, str]:
    """Longest number of dependency edges; invalid DAGs have NaN depth."""
    if not isinstance(program, list) or not program:
        return math.nan, "empty_or_nonlist_program"
    n = len(program)
    for step in program:
        deps = step.get("dependencies") if isinstance(step, dict) else None
        if not isinstance(deps, list) or any(type(d) is not int or d < 0 or d >= n for d in deps):
            return math.nan, "missing_or_invalid_dependencies"
    state, memo = [0] * n, {}

    def visit(index):
        if state[index] == 1:
            raise ValueError("cycle")
        if state[index] == 2:
            return memo[index]
        state[index] = 1
        deps = program[index]["dependencies"]
        value = 0 if not deps else 1 + max(visit(d) for d in deps)
        state[index], memo[index] = 2, value
        return value

    try:
        return float(max(visit(i) for i in range(n))), ""
    except ValueError:
        return math.nan, "dependency_cycle"


def trace_operand(program: list, index: int) -> list[int]:
    depth, reason = graph_depth(program)
    if math.isnan(depth) or type(index) is not int or not 0 <= index < len(program):
        raise ValueError(reason or "invalid_operand_index")
    seen, pending = set(), [index]
    while pending:
        node = pending.pop()
        if node not in seen:
            seen.add(node)
            pending.extend(program[node]["dependencies"])
    return sorted(seen)


def decompose_logic(program: list, context: dict) -> dict:
    try:
        root = program[-1]
        operation = root["operation"]
        if context["op_family_map"]["operations"][operation]["families"] != ["logic"]:
            raise ValueError("terminal_step_is_not_logic")
        deps = root.get("dependencies")
        if not isinstance(deps, list) or len(deps) != 2:
            raise ValueError("logic_requires_two_operands")
        result = {"operator": operation, "parse_status": "ok"}
        labels = []
        for number, terminal in enumerate(deps, 1):
            nodes = trace_operand(program, terminal)
            op = program[terminal]["operation"]
            label = context["runtime"]["operand_default"]
            for rule in context["runtime"]["operand_rules"]:
                if re.search(rule["regex"], op):
                    label = rule["label"]
                    break
            relation = any(program[i]["operation"].split()[0] in
                           context["task_rules"]["relation_definitions"]["R_strict"]["operation_heads"] for i in nodes)
            result.update({
                f"operand{number}_family": label, f"operand{number}_relation": relation,
                f"operand{number}_indices": nodes,
            })
            labels.append(label)
        result["operand_pair"] = " + ".join(sorted(labels))
        return result
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return {"parse_status": str(exc), "operator": "", "operand_pair": "UNPARSEABLE"}


def choose_dev_images(images, fraction: float, seed: int) -> list[str]:
    ordered = np.array(sorted(set(images)), dtype=object)
    n = math.ceil(len(ordered) * fraction)
    return sorted(np.random.default_rng(seed).choice(ordered, size=n, replace=False).tolist())


def fit_question_baseline(questions: list[str], labels, settings: dict, seed: int):
    """The only feature input is a list of question strings; metadata cannot enter."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    if not isinstance(questions, list) or any(type(q) is not str for q in questions):
        raise TypeError("Baseline features must be a list of question strings")
    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=tuple(settings["ngram_range"]), min_df=settings["min_df"])),
        ("classifier", LogisticRegression(C=settings["C"], max_iter=settings["max_iter"],
                                          solver=settings["solver"], random_state=seed)),
    ])
    model.fit(questions, labels)
    return model
