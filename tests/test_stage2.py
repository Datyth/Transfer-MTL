import copy
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from gqa_audit.stage2 import image_and_reference_checks, make_registry, majority_label, preregistered_checks, stratified_sample
from gqa_audit.verify_stage2 import independent_depth
from gqa_audit.stage2_core import (
    canonical_hash, choose_dev_images, decompose_logic, fit_question_baseline, graph_depth, load_frozen, trace_operand,
)
from gqa_audit.stage2_data import SCHEMA, cache_record, regression_rows, retained_mask

CONFIG = Path(__file__).resolve().parents[1] / "gqa_audit/config"


@pytest.fixture
def context():
    return load_frozen(CONFIG)


def step(op="select", deps=None, argument="object (1)"):
    return {"operation": op, "argument": argument, "dependencies": [] if deps is None else deps}


def record(detailed="exist", program=None, answer="yes"):
    return {
        "imageId": "img01", "question": "Is there an object?", "answer": answer,
        "types": {"detailed": detailed, "structural": "verify", "semantic": "obj"},
        "semantic": [step(), step("exist", [0])] if program is None else program,
        "entailed": ["00002"], "equivalent": ["02930152"],
    }


def test_frozen_integrity_and_explicit_decisions(context, tmp_path):
    assert context["task_rules"]["splits"]["dev_fraction_of_train_images"] == .1
    for typ in ("verifyAttrAnd", "verifyMaterialAnd", "twoSameMaterial", "twoSameMaterialC"):
        assert context["task_rules"]["type_mappings"][typ]["task"] == "secondary"
    for name in ("task_rules.yaml", "op_family_map.yaml", "answer_families.yaml", "audit_runtime.yaml", "FROZEN_MANIFEST.json"):
        (tmp_path / name).write_bytes((CONFIG / name).read_bytes())
    with (tmp_path / "task_rules.yaml").open("a") as stream:
        stream.write("\n# changed\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_frozen(tmp_path)


def test_dag_depth_and_shared_forward_dependencies():
    program = [step(), step("verify color", [0]), step("verify shape", [0]), step("and", [1, 2])]
    assert graph_depth(program) == (2., "")
    assert graph_depth([step("exist", [1]), step()]) == (1., "")
    for invalid in (
        [step("select", [9])], [step("select", [True])],
        [step("select", [1]), step("select", [0])], [{"operation": "select"}],
    ):
        assert math.isnan(graph_depth(invalid)[0])


def test_nested_logic_trace_preserves_shared_nodes_and_relations(context):
    program = [
        step(), step("relate", [0], "object,on,o (2)"), step("exist", [1]),
        step(), step("verify color", [3], "red"), step("and", [2, 4]),
        step("or", [5, 2]),
    ]
    result = decompose_logic(program, context)
    assert result["parse_status"] == "ok"
    assert result["operand1_family"] == "other"
    assert result["operand2_family"] == "exist"
    assert result["operand1_indices"] == [0, 1, 2, 3, 4, 5]
    assert result["operand2_relation"] is True
    assert trace_operand(program, 4) == [3, 4]
    assert decompose_logic([step("and", [0, 0])], context)["parse_status"] != "ok"


def test_string_ids_roundtrip_and_sealed_cache(context, tmp_path):
    source = record()
    train = cache_record("02930152", source, "train", context)
    sealed = cache_record("02930152", source, "testdev", context)
    assert train["depth"] == 1.
    for field in ("question", "program_json", "program_length", "relation_steps", "logic_json", "verify_rel_dash"):
        assert sealed[field] is None
    assert math.isnan(sealed["depth"]) and sealed["op_families"] == []
    path = tmp_path / "questions.parquet"
    pq.write_table(pa.Table.from_pylist([train], schema=SCHEMA), path)
    row = pq.read_table(path).to_pylist()[0]
    assert row["question_id"] == "02930152"
    assert row["entailed"] == ["00002"]
    assert not cache_record("q", record(program=[]), "train", context)["eligible"]
    assert not cache_record("q", record(answer="red"), "train", context)["eligible"]
    assert cache_record("q", record(answer=" YES "), "train", context)["eligible"]


def test_split_determinism_and_image_grouping():
    images = [f"image{i:03}" for i in range(37)]
    first = choose_dev_images(images, .1, 0)
    assert len(first) == 4
    assert first == choose_dev_images(images[::-1] + images, .1, 0)
    assert not set(first) & (set(images) - set(first))


def test_frozen_membership_and_regression_guard(context):
    frame = pd.DataFrame([
        {"eligible": True, "task": "exist", "strict": False, "semantic_type": "obj", "answer": "yes", "stratum": "bare"},
        {"eligible": True, "task": "exist", "strict": True, "semantic_type": "rel", "answer": "no", "stratum": "relational_unfiltered_only"},
        {"eligible": False, "task": "exist", "strict": False, "semantic_type": "obj", "answer": "yes", "stratum": "bare"},
    ])
    assert retained_mask(frame, "program_strict", context).tolist() == [True, False, False]
    toy = copy.deepcopy(context)
    toy["manifest"]["regression_targets"] = {
        "unfiltered_and_program_strict_by_task": [{
            "split": "train", "task": "exist", "unfiltered": 2, "unfiltered_yes": 1,
            "program_strict": 1, "program_strict_yes": 1,
        }], "strata": [],
    }
    assert all(r["status"] == "PASS" for r in regression_rows({"train": frame}, toy))
    toy["manifest"]["regression_targets"]["unfiltered_and_program_strict_by_task"][0]["program_strict"] = 0
    assert any(r["status"] == "FAIL" for r in regression_rows({"train": frame}, toy))


def test_registry_hash_is_stable_and_rejects_overlap(context):
    frame = pd.DataFrame([
        {"question_id": "00002", "task": "exist", "analysis_split": "train_core"},
        {"question_id": "02930152", "task": "exist", "analysis_split": "dev"},
    ])
    meta = {"git_commit": "fixture", "package_versions": {}}
    a = make_registry({"program_strict": frame}, meta, ["img02"], context)
    b = make_registry({"program_strict": frame.iloc[::-1]}, meta, ["img02"], context)
    assert a["registry_sha256"] == b["registry_sha256"]
    digest = a.pop("registry_sha256")
    assert digest == canonical_hash(a)
    with pytest.raises(ValueError, match="overlap"):
        make_registry({"program_strict": pd.concat([frame, frame])}, meta, [], context)


def test_baseline_interface_cannot_use_metadata(context):
    text = ["red round object", "red round ball", "blue square object", "blue square box"] * 2
    labels = np.array(["yes", "yes", "no", "no"] * 2)
    metadata = pd.DataFrame({"question": text, "detailed": ["ANSWER_LEAK_SECRET"] * len(text)})
    with pytest.raises(TypeError, match="question strings"):
        fit_question_baseline(metadata, labels, context["runtime"]["baseline"], 0)
    model = fit_question_baseline(metadata.question.tolist(), labels, context["runtime"]["baseline"], 0)
    assert "answer_leak_secret" not in model["tfidf"].vocabulary_
    assert model["classifier"].max_iter == 2000 and model["classifier"].C == 1.
    assert majority_label(["yes", "no"]) == "no"


def test_manual_samples_cover_families_without_duplicates():
    frame = pd.DataFrame({"question_id": [f"{i:05}" for i in range(60)], "family": ["a"] * 40 + ["b"] * 20})
    sample = stratified_sample(frame, 25, 0)
    assert len(sample) == 25 and not sample.question_id.duplicated().any()
    assert abs(sample.family.value_counts()["a"] - sample.family.value_counts()["b"]) <= 1
    assert set(sample.question_id) == set(stratified_sample(frame.iloc[::-1], 25, 0).question_id)


def test_independent_dag_implementation():
    for program in (
        [step(), step("exist", [0])],
        [step(), step("verify color", [0]), step("verify shape", [0]), step("and", [1, 2])],
        [step("select", [1]), step("select", [0])],
        [{"operation": "select"}],
    ):
        expected = graph_depth(program)[0]
        actual = independent_depth(program)
        assert (math.isnan(expected) and math.isnan(actual)) or expected == actual


def test_reference_boundaries_and_missing_targets(context):
    basic = {
        "train": pd.DataFrame([
            {"question_id": "0001", "image_id": "a", "entailed": ["0002", "v", "outside"], "equivalent": ["0001"]},
            {"question_id": "0002", "image_id": "b", "entailed": [], "equivalent": ["0002"]},
        ]),
        "val": pd.DataFrame([{"question_id": "v", "image_id": "c", "entailed": [], "equivalent": ["v"]}]),
    }
    images, references = image_and_reference_checks(basic, {"b"}, context)
    assert images[0]["overlap_images"] == 0
    assert sum(r["references"] for r in references if r["crosses_analysis_split"]) == 2
    external = next(r for r in references if r["to_split"] == "outside_balanced_files")
    assert not external["crosses_analysis_split"]
    assert sum(r["references"] for r in references if r["self_reference"]) == 3


def test_frozen_waiver_and_sealed_threshold_logic(context):
    stats = pd.DataFrame([
        {"variant": "program_strict", "split": "train_core", "level": "task", "task": "exist",
         "questions": 20000, "yes_ratio": .5, "filter_exclusion_rate": .72, "depth_nan_rate": 0.},
        {"variant": "program_strict", "split": "testdev", "level": "task", "task": "exist", "questions": 162},
    ])
    baseline = pd.DataFrame([{"level": "task", "split": "val", "variant": "program_strict",
                              "task": "exist", "gain_over_majority": .16}])
    checks = preregistered_checks(stats, baseline, [], context)
    exclusion = next(r for r in checks if r["check"] == "filter_exclusion_rate")
    assert exclusion["status"] == "FLAG" and exclusion["waived"] is True
    assert next(r for r in checks if r["check"] == "blind_accuracy_gain")["status"] == "FLAG"
    assert next(r for r in checks if r["split"] == "testdev")["status"] == "INFO"
