"""Frozen H-L parsing, subset definitions, clean descriptors and overlap guards."""

import copy
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from gqa_audit.stage2_core import canonical_hash, load_frozen
from gqa_audit.stage2b_data import (PLAN_SHA256, ROOT, load_plan, make_subsets, map_tokens,
                                   operation_tokens, read_hashed_json, regression_checks)


def test_frozen_plan_hash_and_boolean_schema(tmp_path):
    plan = load_plan(ROOT)
    assert plan["status"] == "FROZEN"
    regex = plan["subsets"]["logic_no_not_cue"]["exclude_if"]["question_regex"]
    assert isinstance(regex, str)
    assert plan["subsets"]["verifyRel_relation"]["detailed_types"] == ["relVerify", "relVerifyCr"]
    assert plan["metrics"]["per_task_primary"]["verifyRel"] == "balanced_accuracy@verifyRel_relation"
    config = tmp_path / "gqa_audit/config"
    config.mkdir(parents=True)
    content = (ROOT / "gqa_audit/config/analysis_plan.FROZEN.yaml").read_bytes()
    (config / "analysis_plan.FROZEN.yaml").write_bytes(content + b"\n")
    with pytest.raises(ValueError, match="SHA-256"):
        load_plan(tmp_path)


@pytest.mark.parametrize("question,excluded", [
    ("not blue", True), ("NOT red?", True), ("isn't blue?", True),
    ("a knot?", False), ("nothing else?", False), ("notable colors", False),
])
def test_logic_cue_word_boundaries(question, excluded):
    pattern = load_plan(ROOT)["subsets"]["logic_no_not_cue"]["exclude_if"]["question_regex"]
    assert bool(re.search(pattern, question)) is excluded


def test_descriptor_tokenizer_cannot_emit_arguments_or_ids():
    program = [{"operation": " select ", "argument": "car (-)", "dependencies": []},
               {"operation": "filter color", "argument": "not(red) (12345)", "dependencies": [0]},
               {"operation": "verify color", "argument": "red", "dependencies": [1]}]
    tokens = operation_tokens(program)
    assert tokens == ["select", "filter color", "filter color [neg]", "verify color"]
    assert not any(value in " ".join(tokens) for value in ["car", "red", "12345", "(-)"])
    assert operation_tokens([{"operation": "filter color", "argument": " not(red)"}]) == ["filter color"]
    assert map_tokens(tokens, {"select", "verify color"}) == ["select", "UNSEEN", "UNSEEN", "verify color"]


def test_canonical_subset_hash_is_stable_and_detects_same_size_replacement(tmp_path):
    value = {"subsets": {"text_hard": ["001", "002"]}, "analysis_plan_sha256": PLAN_SHA256}
    value["analysis_subsets_sha256"] = canonical_hash(value)
    path = tmp_path / "subsets.json"
    path.write_text(json.dumps(value, indent=4))
    assert read_hashed_json(path, "analysis_subsets_sha256") == value
    changed = copy.deepcopy(value)
    changed["subsets"]["text_hard"][1] = "003"
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="hash mismatch"):
        read_hashed_json(path, "analysis_subsets_sha256")


def test_subset_membership_combines_family_regex_and_frozen_model_errors():
    context = load_frozen(ROOT / "gqa_audit/config")
    context["analysis_plan"] = load_plan(ROOT)
    context["input_hashes_stage2b"] = {}
    records = [
        ("001", "logic", "existThatOr", "existThatOrC", "not blue?", "no"),
        ("002", "logic", "existThatOr", "existThatOr", "knot blue?", "yes"),
        ("003", "exist", "existThatNot", "existThatNot", "not red?", "yes"),
        ("004", "verifyRel", "relVerify", "relVerify", "on top?", "yes"),
        ("005", "verifyRel", "relVerify", "relVerifyCr", "under?", "no"),
        ("006", "verifyRel", "relVerify", "relVerifyCo", "near?", "no"),
    ]
    frame = pd.DataFrame(records, columns=["question_id", "task", "family", "detailed", "question", "answer"])
    frame["part"] = "val"
    frame["in_program_strict"] = frame["in_unfiltered"] = True
    predictions = pd.concat([frame[["question_id", "task", "answer"]].assign(
        variant=variant, analysis_split="val", prediction=["no", "no", "yes", "yes", "yes", "no"])
        for variant in ("program_strict", "unfiltered")], ignore_index=True)
    subsets, _ = make_subsets(frame, predictions, context)
    result = subsets["subsets"]
    assert result["logic_no_not_cue"]["program_strict"]["logic"]["val"] == ["002"]
    assert result["text_hard"]["program_strict"]["logic"]["val"] == ["002"]
    assert result["verifyRel_relation"]["program_strict"]["verifyRel"]["val"] == ["004", "005"]
    assert result["verifyRel_Co"]["program_strict"]["verifyRel"]["val"] == ["004", "006"]
    reordered, _ = make_subsets(frame.iloc[::-1], predictions.iloc[::-1], context)
    assert subsets["analysis_subsets_sha256"] == reordered["analysis_subsets_sha256"]


def test_overlap_uses_source_train_only_and_excludes_select():
    from gqa_audit.stage2b_analysis import question_overlap
    context = {"task_rules": {"pilot_tasks": {"source": {}, "target": {}}},
               "analysis_runtime": {"overlap_contrast_bounds": [.05, .95]}}
    records = [
        ("01", "train_core", "source", ["filter color"]),
        ("02", "val", "source", ["secret val token"]),
        ("03", "train_core", "target", ["exist"]),
        ("04", "val", "target", ["filter color", "filter color"]),
        ("05", "val", "target", ["secret val token"]),
        ("06", "dev", "target", ["filter color"]),
        ("07", "dev", "source", ["filter color"]),
    ]
    data = pd.DataFrame(records, columns=["question_id", "part", "task", "token_multiset"])
    data["with_select"] = data.token_multiset.map(lambda tokens: ["select"] + tokens)
    data["in_program_strict"] = True
    data["answer"], data["family"], data["stratum"] = "yes", "family", ""
    data["program_length"], data["depth"] = 2, 1
    pred = data[["question_id"]].assign(variant="program_strict", prediction="yes")
    counts, viability, confounds, _, values = question_overlap(data, pred, context)
    row = counts[(counts.source == "source") & (counts.target == "target") & (counts.part == "val")].iloc[0]
    assert row.n_sharing == 1 and row.share == .5
    q = values[(values.source == "source") & values.question_id.eq("04")].iloc[0]
    assert q.shared_continuous == 1  # distinct target tokens, not two occurrences
    assert not values[(values.source == "source") & values.question_id.eq("05")].iloc[0].shared_binary


def test_shortcut_table_joins_actual_text_hard_scores_and_flags_missing():
    from gqa_audit.evaluation import shortcut_control_table
    edges = [
        {"source": "exist", "target": "logic", "condition": "transfer", "metric": "accuracy", "value": .7, "subset": "main"},
        {"source": "exist", "target": "logic", "condition": "transfer", "metric": "accuracy", "value": .6, "subset": "text_hard"},
    ]
    table = shortcut_control_table(edges, ROOT)
    assert len(table) == 1 and table.iloc[0].value_on_text_hard == .6
    assert table.iloc[0].text_hard_status == "OK"
    assert table.target_no_image_gain.isna().all()
    missing = shortcut_control_table([edges[0]], ROOT)
    assert missing.iloc[0].text_hard_status == "MISSING"
