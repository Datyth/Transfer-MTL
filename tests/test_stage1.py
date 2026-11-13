import csv
import json
from pathlib import Path

import yaml
import pytest

from gqa_audit import stage1
from gqa_audit.checks import is_eligible, validate_configs
from gqa_audit.diagnostics import accepts, build_variant_rows, propose_families
from gqa_audit.verify_stage1 import verify_stage1


def _configs():
    with (stage1.CONFIG / "task_rules.PROPOSED.yaml").open(encoding="utf-8") as stream:
        task = yaml.safe_load(stream)
    with (stage1.CONFIG / "op_family_map.PROPOSED.yaml").open(encoding="utf-8") as stream:
        operations = yaml.safe_load(stream)
    return task, operations


def test_streaming_records_and_operation_head(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps({"q1": {"answer": "yes"}, "q2": {"answer": "no"}}), encoding="utf-8")
    assert list(stage1.iter_records(path)) == [("q1", {"answer": "yes"}), ("q2", {"answer": "no"})]
    assert stage1.operation_head("  verify color ") == "verify"
    assert stage1.operation_head("choose rel") == "choose"
    path.write_text('{"02930152": {"answer": "yes"}}', encoding="utf-8")
    assert list(stage1.iter_records(path))[0][0] == "02930152"
    path.write_text('[{"answer": "yes"}]', encoding="utf-8")
    with pytest.raises(stage1.ijson.JSONError, match="JSON object"):
        list(stage1.iter_records(path))


def test_yaml_boolean_coercion_is_rejected():
    task, operations = _configs()
    families = yaml.safe_load((stage1.CONFIG / "answer_families.PROPOSED.yaml").read_text())
    validate_configs(task, operations, families)
    broken = yaml.safe_load("binary_answers: [yes, no]")
    assert broken["binary_answers"] == [True, False]
    task["eligibility"] = {**task["eligibility"], **broken}
    with pytest.raises(ValueError, match="Quote yes/no"):
        validate_configs(task, operations, families)


@pytest.mark.parametrize("answer,program,expected", [
    ("yes", [{"operation": "exist"}], True),
    (" NO  ", [{"operation": "exist"}], True),
    ("yes", [], False),
    ("red", [{"operation": "query"}], False),
    (True, [{"operation": "exist"}], False),
    ("yes", '[{"operation": "exist"}]', False),
])
def test_eligibility_regression(answer, program, expected):
    task, _ = _configs()
    assert is_eligible(answer, program, task["eligibility"]) is expected


def test_family_pairing_and_filter_membership():
    task, _ = _configs()
    family_rules = yaml.safe_load((stage1.CONFIG / "answer_families.PROPOSED.yaml").read_text())
    mappings = {t: stage1.propose_type_mapping(t, task) for t in ["exist", "existC", "relVerify", "relVerifyCo"]}
    families = propose_families(mappings, family_rules, task["unmatched_task"])
    assert families["exist"]["detailed_types"] == ["exist", "existC"]
    assert families["relVerify"]["detailed_types"] == ["relVerify", "relVerifyCo"]
    assert not accepts(("yes", False, False, "rel"), "exist", {"exist": {"types_semantic": "obj"}})
    signatures = {("train", "exist"): {
        ("yes", True, True, "obj"): 1,
        ("no", False, False, "rel"): 1,
    }}
    comparison_rules = {
        "pilot_tasks": {"exist": {}},
        "audit_variants": {
            "program": {"exist": {"relation": "R_strict"}},
            "semantic": {"exist": {"types_semantic": "obj"}},
        },
    }
    variants, equivalence = build_variant_rows(
        signatures, mappings, comparison_rules, {"exist": families["exist"]}, ("train",)
    )
    # Equal retained counts must not be mistaken for equal question membership.
    assert {r["questions"] for r in variants} == {1}
    assert equivalence[0]["different_questions"] == 2


def test_relation_definitions_cover_operation_and_argument():
    task, _ = _configs()
    rules = task["relation_definitions"]
    assert stage1.relation_flags("relate", "_,on,s (123)", rules) == (True, True)
    assert stage1.relation_flags("verify rel", "food,to the left of,o (321)", rules) == (False, True)
    assert stage1.relation_flags("choose rel", "woman,left|right,s (9)", rules) == (False, True)
    assert stage1.relation_flags("select", "food,to the left of,o (321)", rules) == (False, True)
    assert stage1.relation_flags("select", "animal (1,2,3)", rules) == (False, False)


def test_proposals_assign_at_most_one_task_and_cover_operations():
    task, operations = _configs()
    types = (
        "exist", "verifyAttr", "relVerify", "twoSameColor", "twoDifferent",
        "existAnd", "verifyAttrs", "weatherVerifyC",
    )
    mapped = {raw: stage1.propose_type_mapping(raw, task) for raw in types}
    assert [mapped[t]["task"] for t in types] == [
        "exist", "verifyAttr", "verifyRel", "compare", "compare", "logic", "logic", "secondary"
    ]
    assert mapped["existAnd"]["flag"] == "AMBIGUOUS"
    assert all(isinstance(value["task"], str) for value in mapped.values())
    assert stage1.propose_op_mapping("verify rel", operations)["families"] == ["relation"]
    assert stage1.propose_op_mapping("choose rel", operations)["families"] == ["choose", "relation"]
    assert stage1.propose_op_mapping("unknown action", operations)["flag"] == "UNMAPPED"


def test_small_stage1_reports_schema_and_is_deterministic(tmp_path, monkeypatch):
    original_task = stage1.CONFIG / "task_rules.PROPOSED.yaml"
    original_op = stage1.CONFIG / "op_family_map.PROPOSED.yaml"
    config = tmp_path / "gqa_audit" / "config"
    output = tmp_path / "gqa_audit" / "outputs" / "stage1"
    config.mkdir(parents=True)
    (tmp_path / "notebooks").mkdir()
    (config / original_task.name).write_bytes(original_task.read_bytes())
    (config / original_op.name).write_bytes(original_op.read_bytes())
    family_path = stage1.CONFIG / "answer_families.PROPOSED.yaml"
    (config / family_path.name).write_bytes(family_path.read_bytes())
    questions = tmp_path / "questions"
    questions.mkdir()

    def record(detailed, answer, operation, argument):
        return {
            "imageId": "1", "question": "Is it there?", "answer": answer,
            "fullAnswer": answer, "isBalanced": True,
            "types": {
                "detailed": detailed, "structural": "verify",
                "semantic": "rel" if operation == "verify rel" else ("obj" if detailed.startswith("exist") else "attr"),
            },
            "semantic": [
                {"operation": "select", "argument": "object (1)", "dependencies": []},
                {"operation": operation, "argument": argument, "dependencies": [0]},
            ],
            "groups": {"global": None, "local": None}, "entailed": [], "equivalent": [], "annotations": {},
        }

    samples = {
        "train": {
            "02930152": record("exist", "yes", "exist", "object"),
            "00002": record("existC", "no", "relate", "food,on,o (2)"),
        },
        "val": {"q2": record("verifyAttr", "no", "verify color", "red")},
        "testdev": {"q3": record("verifyRel", "yes", "verify rel", "food,on,o (2)")},
    }
    for split, data in samples.items():
        (questions / f"{split}_balanced_questions.json").write_text(json.dumps(data), encoding="utf-8")
    (questions / "val_all_questions.json").write_text("not parsed", encoding="utf-8")
    monkeypatch.setattr(stage1, "ROOT", tmp_path)
    monkeypatch.setattr(stage1, "CONFIG", config)
    monkeypatch.setattr(stage1, "OUTPUT", output)
    monkeypatch.setattr(stage1, "_git_commit", lambda: "fixture-source")
    assert stage1.run_stage1(questions) == 0
    first_summary = (output / "STAGE1_SUMMARY.md").read_bytes()
    with (output / "detailed_type_inventory.csv").open(newline="", encoding="utf-8") as stream:
        inventory = list(csv.DictReader(stream))
    assert sum(int(row["count"]) for row in inventory) == 4
    with (output / "candidate_counts.csv").open(newline="", encoding="utf-8") as stream:
        candidates = list(csv.DictReader(stream))
    assert sum(int(row["eligible"]) for row in candidates) == 4
    assert all(int(row["eligible"]) == int(row["raw_count"]) for row in candidates)
    assert sum(int(row["R_strict_removed"]) for row in candidates) == 1
    assert sum(int(row["R_broad_removed"]) for row in candidates) == 1
    with (output / "relation_matches.csv").open(newline="", encoding="utf-8") as stream:
        relation_ids = {row["question_id"] for row in csv.DictReader(stream)}
    assert "00002" in relation_ids
    assert all(row["status"] == "PASS" for row in csv.DictReader(
        (output / "validation_checks.csv").open(newline="", encoding="utf-8")
    ))
    assert "02930152" in (output / "suffix_examples.md").read_text()
    assert "missing_expected_field |" not in (output / "schema_report.md").read_text(encoding="utf-8")
    notebook = json.loads((tmp_path / "notebooks" / "gqa_stage1_audit.ipynb").read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    assert any("image/png" in output_data.get("data", {}) for cell in notebook["cells"] for output_data in cell.get("outputs", []))
    assert verify_stage1(questions, output, tmp_path / "notebooks/gqa_stage1_audit.ipynb") == 0
    candidates[0]["eligible"] = "0"
    with (output / "candidate_counts.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(candidates[0]))
        writer.writeheader()
        writer.writerows(candidates)
    assert verify_stage1(questions, output, tmp_path / "notebooks/gqa_stage1_audit.ipynb") == 1
    assert stage1.run_stage1(questions) == 0
    assert (output / "STAGE1_SUMMARY.md").read_bytes() == first_summary
    del samples["train"]["02930152"]["annotations"]
    (questions / "train_balanced_questions.json").write_text(
        json.dumps(samples["train"]), encoding="utf-8"
    )
    assert stage1.run_stage1(questions) == 1
    schema = (output / "schema_report.md").read_text(encoding="utf-8")
    assert "val_all_questions.json" in schema
    assert "| train | `annotations` | 1 |" in schema
