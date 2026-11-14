"""Scoring, image-cluster uncertainty, complete-ID contracts and sealed testdev."""

import copy

import numpy as np
import pandas as pd
import pytest

from gqa_audit.evaluation import Evaluator, cluster_intervals, point_metrics
from gqa_audit.stage2b_data import ROOT, load_plan


@pytest.fixture
def evaluator():
    metadata = pd.DataFrame({
        "question_id": ["001", "002", "003", "004", "005", "006"],
        "imageId": ["a", "a", "b", "c", "d", "e"],
        "part": ["val"] * 5 + ["testdev"], "task": ["verifyRel"] * 6,
        "family": ["relVerify"] * 6, "stratum": [""] * 6,
        "answer": ["yes", "yes", "no", "no", "no", "yes"],
        "in_program_strict": [True] * 6, "in_unfiltered": [True] * 6,
    })
    registry = {"registry_sha256": "fixture", "variants": {"program_strict": {"verifyRel": {
        "train_core": [], "dev": [], "val": ["001", "002", "003", "004", "005"], "testdev": ["006"]}}}}
    subsets = {"analysis_subsets_sha256": "fixture", "subsets": {
        "verifyRel_relation": {"program_strict": {"verifyRel": {"val": ["001", "002", "003"], "testdev": ["006"]}}},
        "verifyRel_Co": {"program_strict": {"verifyRel": {"val": ["001", "002", "004", "005"]}}},
        "text_hard": {"program_strict": {"verifyRel": {"val": ["002", "003", "005"]}}}}}
    return Evaluator(ROOT, metadata=metadata, registry=registry, subsets=subsets, plan=load_plan(ROOT))


def predictions():
    return pd.DataFrame({"question_id": ["001", "002", "003", "004", "005"], "pred": ["yes", "no", "no", "no", "yes"]})


def test_accuracy_and_balanced_accuracy_are_different():
    metrics = point_metrics(pd.DataFrame({"answer": ["yes", "yes", "yes", "no"], "pred": ["yes"] * 4}))
    assert metrics["accuracy"] == .75
    assert metrics["balanced_accuracy"] == .5
    assert np.isnan(point_metrics(pd.DataFrame({"answer": ["yes"], "pred": ["yes"]}))["balanced_accuracy"])


def test_cluster_bootstrap_resamples_complete_images_and_is_deterministic():
    # Every question on A is correct and every question on B is wrong. Sampling
    # whole images gives four equally likely accuracy values: 1, 2/3, 2/3, 0.
    frame = pd.DataFrame({"imageId": ["A", "A", "B"], "answer": ["yes", "no", "no"], "pred": ["yes", "no", "yes"]})
    settings = {"seed": 0, "resamples": 1000, "level": .95}
    first = cluster_intervals(frame, settings)
    assert first == cluster_intervals(frame, settings)
    assert first["images"] == 2
    assert first["accuracy_ci_low"] == 0 and first["accuracy_ci_high"] == 1
    rng = np.random.default_rng(0)
    sample = rng.integers(0, 2, (1000, 2))
    correct = np.array([2, 0])[sample].sum(axis=1)
    total = np.array([2, 1])[sample].sum(axis=1)
    expected = np.quantile(correct / total, [.025, .975])
    assert np.allclose([first["accuracy_ci_low"], first["accuracy_ci_high"]], expected)


def test_verifyrel_primary_is_relation_intersection_not_pooled(evaluator):
    scores = evaluator.evaluate(predictions(), "program_strict", ["val"])
    task = scores[scores.level.eq("task")].iloc[0]
    assert task.accuracy == .6 and task.primary_n == 3
    assert task.primary_value == .75  # positive recall .5; Cr recall 1
    hard = scores[scores.unit.eq("text_hard")].iloc[0]
    assert hard.primary_n == 2 and hard.primary_value == .5
    co = scores[scores.unit.eq("verifyRel_Co")].iloc[0]
    assert co.role == "secondary" and co.primary_metric == "accuracy"
    assert scores.n.ge(scores.primary_n).all()


@pytest.mark.parametrize("kind", ["missing", "duplicate", "extra", "numeric", "bad_answer", "bad_probability"])
def test_invalid_prediction_contract_raises(evaluator, kind):
    pred = predictions()
    if kind == "missing":
        pred = pred.iloc[:-1]
    elif kind == "duplicate":
        pred = pd.concat([pred, pred.iloc[:1]])
    elif kind == "extra":
        pred = pd.concat([pred, pd.DataFrame({"question_id": ["999"], "pred": ["no"]})])
    elif kind == "numeric":
        pred["question_id"] = pred.question_id.astype(int)
    elif kind == "bad_answer":
        pred.loc[0, "pred"] = "maybe"
    else:
        pred["p_yes"] = 1.1
    with pytest.raises(ValueError):
        evaluator.evaluate(pred, "program_strict", ["val"])


def test_testdev_is_refused_before_any_unsealing(evaluator, monkeypatch):
    def forbidden(_):
        pytest.fail("Unsealing must never occur without final=True")
    monkeypatch.setattr(evaluator, "_unseal", forbidden)
    with pytest.raises(ValueError, match="sealed"):
        evaluator.evaluate(pd.DataFrame({"question_id": ["006"], "pred": ["yes"]}), "program_strict", ["testdev"])


def test_final_testdev_has_family_stratum_only_no_task_or_subset(evaluator, monkeypatch):
    rows = evaluator.metadata[evaluator.metadata.part.eq("testdev")]
    monkeypatch.setattr(evaluator, "_unseal", lambda _: (rows, {"verifyRel_relation": {"006"}}))
    scores = evaluator.evaluate(pd.DataFrame({"question_id": ["006"], "pred": ["yes"]}), "program_strict", ["testdev"], final=True)
    assert set(scores.level) == {"family"}
    assert scores.n.tolist() == [1]
    assert scores.primary_status.tolist() == ["UNDEFINED"]
