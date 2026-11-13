"""Exercise the complete Stage 2 pipeline on small synthetic image groups."""

import copy
import hashlib
import json

import pandas as pd
import pyarrow.parquet as pq

from gqa_audit import stage2
from gqa_audit.stage2_core import load_frozen
from tests.test_stage2 import CONFIG, step


def test_stage2_end_to_end_before_real_run(tmp_path, monkeypatch):
    context = copy.deepcopy(load_frozen(CONFIG))
    questions = tmp_path / "questions"
    questions.mkdir()
    (tmp_path / "notebooks").mkdir()
    output = tmp_path / "gqa_audit/outputs/stage2"
    definitions = {
        "exist": ("exist", "existC", "obj", "verify"),
        "verifyAttr": ("verifyAttr", "verifyAttrC", "attr", "verify"),
        "verifyRel": ("relVerify", "relVerifyCr", "rel", "verify"),
        "compare": ("twoSame", "twoSameC", "attr", "compare"),
        "logic": ("existAnd", "existAndC", "obj", "logical"),
    }
    targets = []
    for split, image_count in (("train", 10), ("val", 2), ("testdev", 1)):
        records = {}
        for image in range(image_count):
            for task, (positive, negative, semantic, structural) in definitions.items():
                for yes, typ in ((True, positive), (False, negative)):
                    qid = f"00{split}{image:03}{task}{int(yes)}"
                    related = split == "train" and image == 0 and task in ("exist", "verifyAttr")
                    if task == "exist":
                        if related:
                            typ = "existRelS" if yes else "existRelSC"
                            semantic_value = "rel"
                            program = [step(), step("relate", [0], "object,on,o (2)"), step("exist", [1])]
                        else:
                            semantic_value, program = semantic, [step(), step("exist", [0])]
                    elif task == "verifyAttr":
                        semantic_value = semantic
                        program = ([step(), step("relate", [0], "object,on,o (2)"), step("verify color", [1], "red")]
                                   if related else [step(), step("verify color", [0], "red")])
                    elif task == "verifyRel":
                        semantic_value, program = semantic, [step(), step("verify rel", [0], "object,on,o (2)")]
                    elif task == "compare":
                        semantic_value, program = semantic, [step(), step(), step("same color", [0, 1], "color")]
                    else:
                        semantic_value = semantic
                        program = [step(), step("exist", [0]), step(), step("exist", [2]), step("and", [1, 3])]
                    records[qid] = {
                        "imageId": f"{split}-image{image:03}", "question": f"Is this {task} object red {'round' if yes else 'square'}?",
                        "answer": "yes" if yes else "no", "semantic": program,
                        "types": {"detailed": typ, "structural": structural, "semantic": semantic_value},
                        "entailed": [], "equivalent": [qid],
                    }
        path = questions / f"{split}_balanced_questions.json"
        path.write_text(json.dumps(records))
        context["manifest"]["input_sha256"][split] = hashlib.sha256(path.read_bytes()).hexdigest()
        context["manifest"]["raw_question_counts"][split] = len(records)
        for task in definitions:
            count = 2 * image_count
            strict = count - (2 if split == "train" and task in ("exist", "verifyAttr") else 0)
            targets.append({
                "split": split, "task": task, "unfiltered": count, "unfiltered_yes": count // 2,
                "program_strict": strict, "program_strict_yes": strict // 2,
            })
    context["manifest"]["regression_targets"] = {"unfiltered_and_program_strict_by_task": targets, "strata": []}
    monkeypatch.setattr(stage2, "ROOT", tmp_path)
    monkeypatch.setattr(stage2, "OUTPUT", output)
    monkeypatch.setattr(stage2, "load_frozen", lambda _: context)
    monkeypatch.setattr(stage2.subprocess, "check_output", lambda *args, **kwargs: "fixture\n")
    assert stage2.run_stage2(questions) == 0
    assert (output / "AUDIT_REPORT.md").is_file()
    assert (tmp_path / "notebooks/gqa_stage2_audit.ipynb").is_file()
    predictions = pd.read_csv(output / "blind_predictions.csv")
    assert set(predictions.analysis_split) == {"dev", "val"}
    sealed = pq.read_table(output / "cache/questions_testdev.parquet").to_pandas()
    assert sealed.question.isna().all() and sealed.program_json.isna().all()
    stats = pd.read_csv(output / "task_stats.csv")
    assert stats[stats.split == "testdev"].yes_ratio.isna().all()
    assert (pd.read_csv(output / "regression_checks.csv").status == "PASS").all()
    assert len(list((output / "figures").glob("*.png"))) == len(list((output / "figures").glob("*.pdf")))
