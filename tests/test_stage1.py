import csv
import json
from pathlib import Path

import yaml

from gqa_audit import stage1


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
    questions = tmp_path / "questions"
    questions.mkdir()

    def record(detailed, answer, operation, argument):
        return {
            "imageId": "1", "question": "Is it there?", "answer": answer,
            "fullAnswer": answer, "isBalanced": True,
            "types": {"detailed": detailed, "structural": "verify", "semantic": "attr"},
            "semantic": [
                {"operation": "select", "argument": "object (1)", "dependencies": []},
                {"operation": operation, "argument": argument, "dependencies": [0]},
            ],
            "groups": {"global": None, "local": None}, "entailed": [], "equivalent": [], "annotations": {},
        }

    samples = {
        "train": {"q1": record("exist", "yes", "exist", "object")},
        "val": {"q2": record("verifyAttr", "no", "verify color", "red")},
        "testdev": {"q3": record("verifyRel", "yes", "verify rel", "food,on,o (2)")},
    }
    for split, data in samples.items():
        (questions / f"{split}_balanced_questions.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(stage1, "ROOT", tmp_path)
    monkeypatch.setattr(stage1, "CONFIG", config)
    monkeypatch.setattr(stage1, "OUTPUT", output)
    assert stage1.run_stage1(questions) == 1  # Temporary directory has no git commit.
    first_summary = (output / "STAGE1_SUMMARY.md").read_bytes()
    with (output / "detailed_type_inventory.csv").open(newline="", encoding="utf-8") as stream:
        inventory = list(csv.DictReader(stream))
    assert sum(int(row["count"]) for row in inventory) == 3
    assert "missing_expected_field |" not in (output / "schema_report.md").read_text(encoding="utf-8")
    notebook = json.loads((tmp_path / "notebooks" / "gqa_stage1_audit.ipynb").read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    assert any("image/png" in output_data.get("data", {}) for cell in notebook["cells"] for output_data in cell.get("outputs", []))
    assert stage1.run_stage1(questions) == 1
    assert (output / "STAGE1_SUMMARY.md").read_bytes() == first_summary
    del samples["train"]["q1"]["annotations"]
    (questions / "train_balanced_questions.json").write_text(
        json.dumps(samples["train"]), encoding="utf-8"
    )
    assert stage1.run_stage1(questions) == 1
    schema = (output / "schema_report.md").read_text(encoding="utf-8")
    assert "| train | `annotations` | 1 |" in schema
