"""Frozen prompts, scoring, paired uncertainty, resume and sealed-test contracts."""

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest
import torch
from transformers import AutoProcessor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gqa_audit.evaluation import Evaluator
from vqa_research.analysis import calibrate_thresholds, paired_difference
from vqa_research.data import ROOT, file_hash, load_protocol, load_questions, save_json
from vqa_research.inference import run_predictions
from vqa_research.model import build_messages, check_token_ids, yes_no_scores


@pytest.fixture(scope="module")
def processor():
    return AutoProcessor.from_pretrained(ROOT / "checkpoints/Qwen2.5-VL-3B-Instruct", local_files_only=True, use_fast=False)


def test_real_first_assistant_token_ids(processor):
    protocol, _ = load_protocol(ROOT / "configs/stage3_protocol.FROZEN.yaml")
    assert check_token_ids(processor, protocol["templates"]) == {"yes": 9693, "Yes": 9454, "no": 2152, "No": 2753}


def test_toy_yes_no_logits_use_both_cases():
    ids = {"yes": 0, "Yes": 1, "no": 2, "No": 3}
    result = yes_no_scores(torch.tensor([[2., 1., 0., -1.], [0., 0., 0., 0.]]), ids)
    assert torch.allclose(result, torch.tensor([2., 0.]))


def test_fifty_rendered_prompts_have_only_question_and_optional_image(processor):
    protocol, evaluator = load_protocol(ROOT / "configs/stage3_protocol.FROZEN.yaml")
    # Audit sentinels never enter the prompt builder, whose interface takes a string.
    rows = load_questions(evaluator).query("part == 'dev'").sample(50, random_state=0)
    for row in rows.itertuples():
        question = row.question
        for template in protocol["templates"].values():
            for with_image in (False, True):
                messages = build_messages(question, template, with_image)
                assert messages == [{"role": "user", "content": ([{"type": "image"}] if with_image else []) + [
                    {"type": "text", "text": template.format(question=question)}]}]
                rendered = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                assert template.format(question=question) in rendered
                assert all(word not in rendered for word in ("program_length", "fullAnswer", "in_program_strict", "detailed", "scene_graph"))
    with pytest.raises(ValueError):
        build_messages({"question": "yes", "answer": "yes"}, "{question}", False)


class ToyModel:
    def __init__(self, fail_call=None):
        self.calls = 0
        self.fail_call = fail_call

    def score(self, questions, images, template):
        self.calls += 1
        if self.calls == self.fail_call:
            raise RuntimeError("interrupted")
        size = len(questions)
        return {"score": np.ones(size), "pred": ["yes"] * size, "p_yes": [1 / (1 + np.exp(-1))] * size,
                "n_image_tokens": [0] * size, "seconds": [.1] * size}


def toy_questions():
    return pd.DataFrame({"question_id": [f"00{i}" for i in range(6)], "part": ["dev"] * 3 + ["val"] * 3,
                         "imageId": ["a"] * 6, "question": ["Is it visible?"] * 6})


def test_resume_an_interrupted_run_without_missing_or_duplicate_ids(tmp_path):
    questions = toy_questions()
    with pytest.raises(RuntimeError, match="interrupted"):
        run_predictions(ToyModel(fail_call=2), questions, {}, "{question}", "no_image", tmp_path, {"test": 1}, 2, 2)
    resumed = ToyModel()
    first = run_predictions(resumed, questions, {}, "{question}", "no_image", tmp_path, {"test": 1}, 2, 2)
    assert resumed.calls == 2
    assert first.question_id.tolist() == questions.question_id.tolist()
    complete = ToyModel()
    pd.testing.assert_frame_equal(first, run_predictions(complete, questions, {}, "{question}", "no_image", tmp_path, {"test": 1}, 2, 2))
    assert complete.calls == 0
    # A crash between the parquet rename and its checksum commit recomputes just
    # that incomplete shard instead of blocking the entire resumed experiment.
    (tmp_path / "00001.json").unlink()
    orphan = ToyModel()
    pd.testing.assert_frame_equal(first, run_predictions(orphan, questions, {}, "{question}", "no_image", tmp_path, {"test": 1}, 2, 2))
    assert orphan.calls == 1


def test_resume_rejects_modified_ids_even_if_shard_hash_is_updated(tmp_path):
    questions = toy_questions()
    run_predictions(ToyModel(), questions, {}, "{question}", "no_image", tmp_path, {}, 2, 2)
    shard = tmp_path / "00000.parquet"
    table = pd.read_parquet(shard)
    table.loc[0, "question_id"] = "999"
    table.to_parquet(shard, index=False)
    save_json(shard.with_suffix(".json"), {"sha256": file_hash(shard)})
    with pytest.raises(ValueError, match="IDs or ordering"):
        run_predictions(ToyModel(), questions, {}, "{question}", "no_image", tmp_path, {}, 2, 2)


def test_testdev_never_reaches_the_model(tmp_path):
    model = ToyModel()
    questions = toy_questions()
    questions.loc[0, "part"] = "testdev"
    with pytest.raises(ValueError, match="sealed"):
        run_predictions(model, questions, {}, "{question}", "no_image", tmp_path, {}, 2, 2)
    assert model.calls == 0 and not list(tmp_path.glob("*.parquet"))


def test_identical_paired_predictions_have_exact_zero_difference_ci():
    frame = pd.DataFrame({"imageId": ["a", "a", "b", "c"], "answer": ["yes", "no", "yes", "no"],
                          "pred_image": ["yes", "yes", "no", "no"], "pred_no_image": ["yes", "yes", "no", "no"]})
    for metric in ("accuracy", "balanced_accuracy"):
        value = paired_difference(frame, {"seed": 0, "resamples": 100, "level": .95}, metric)
        assert value["difference"] == value["ci_low"] == value["ci_high"] == 0


def test_calibration_uses_dev_only_and_exact_greater_than_threshold():
    questions = toy_questions()
    questions["task"] = "exist"
    questions["answer"] = ["no", "yes", "yes", "no", "yes", "no"]
    pred = questions[["question_id", "part"]].copy()
    pred["score"] = np.array([-1, 0.25, 1, -.5, 0.25, 2], dtype=np.float32)
    pred["pred"] = np.where(pred.score > 0, "yes", "no")
    first, choices = calibrate_thresholds(questions, pred)
    assert choices.iloc[0].dev_balanced_accuracy == 1
    changed = questions.copy()
    changed.loc[changed.part.eq("val"), "answer"] = "yes"
    second, other_choices = calibrate_thresholds(changed, pred)
    pd.testing.assert_frame_equal(choices, other_choices)
    pd.testing.assert_frame_equal(first, second)
    assert first.pred.iloc[:3].tolist() == ["no", "yes", "yes"]


def test_blind_predictions_reproduce_accepted_demo(tmp_path):
    evaluator = Evaluator(ROOT)
    pred = pd.read_csv(ROOT / "gqa_audit/outputs/stage2/blind_predictions.csv", dtype={"question_id": str})
    chosen = pred[pred.variant.eq("program_strict")][["question_id", "prediction"]].rename(columns={"prediction": "pred"})
    path = tmp_path / "blind.parquet"
    chosen.to_parquet(path, index=False)
    actual = evaluator.evaluate(pd.read_parquet(path), "program_strict", ["dev", "val"])
    expected = pd.read_csv(ROOT / "gqa_audit/outputs/stage2b/demo_eval_blind.csv")
    expected = expected[expected.variant.eq("program_strict")].reset_index(drop=True)
    keys = ["variant", "part", "level", "task", "unit"]
    actual = actual.sort_values(keys).reset_index(drop=True)
    expected = expected.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(actual[keys], expected[keys])
    for column in ("primary_value", "accuracy", "balanced_accuracy", "yes_prediction_rate", "ci_low", "ci_high"):
        assert np.allclose(actual[column], expected[column], atol=1e-12, equal_nan=True)
