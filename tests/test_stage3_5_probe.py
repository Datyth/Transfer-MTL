"""Pilot invariants that can be checked without a GPU run."""

import numpy as np
import pandas as pd
import pytest
from types import SimpleNamespace
from PIL import Image

from gqa_audit.evaluation import Evaluator, probabilistic_metrics
from src.vqa_research.probe.data import PilotData, rng
from src.vqa_research.probe.features import FILL, pad_and_resize
from src.vqa_research.probe.model import ALLOWED_BATCH_KEYS
from src.vqa_research.probe.train import run_id
from src.vqa_research.probe.recipe import dev_log_loss


def test_padding_retains_both_ends():
    image = Image.new("RGB", (80, 20), (255, 0, 0))
    image.putpixel((0, 10), (0, 255, 0))
    image.putpixel((79, 10), (0, 0, 255))
    resized = np.asarray(pad_and_resize(image))
    assert resized[112, 0, 1] > resized[112, 0, 0]
    assert resized[112, -1, 2] > resized[112, -1, 0]
    assert tuple(resized[0, 112]) == FILL


def test_pilot_seed_is_restricted_and_deterministic():
    assert rng(1000, 1).permutation(50).tolist() == rng(1000, 1).permutation(50).tolist()
    with pytest.raises(ValueError):
        rng(0, 1)


def test_batch_keys_and_run_hash():
    assert ALLOWED_BATCH_KEYS == {"image_tokens", "input_ids", "attention_mask", "labels"}
    assert run_id({"a": 1, "b": 2}) == run_id({"b": 2, "a": 1})


def test_logloss_and_auroc():
    frame = pd.DataFrame({"answer": ["yes", "yes", "no", "no"],
                          "p_yes": [0.9, 0.6, 0.4, 0.1], "score": [2.0, 0.4, -0.4, -2.0]})
    metrics = probabilistic_metrics(frame)
    assert metrics["auroc"] == 1.0
    assert metrics["log_loss"] == pytest.approx(-np.log([0.9, 0.6, 0.6, 0.9]).mean())
    assert probabilistic_metrics(frame.iloc[[0, 2, 3]], class_balanced=True)["log_loss"] == pytest.approx(
        (-np.log(0.9) - np.log([0.6, 0.9]).mean()) / 2)


def test_recipe_logloss_handles_question_id_index_and_column():
    frame = pd.DataFrame({"question_id": ["a", "b"], "answer": ["yes", "no"]}).set_index(
        "question_id", drop=False)
    data = SimpleNamespace(membership={"exist": {"dev": ["a", "b"]}}, by_id=frame)
    predictions = pd.DataFrame({"question_id": ["a", "b"], "score": [1.0, -1.0],
                                "p_yes": [0.8, 0.2], "pred": ["yes", "no"]})
    assert dev_log_loss(data, "exist", predictions) == pytest.approx(-np.log(0.8))


def test_dev_only_guard():
    evaluator = Evaluator(mode="stage3_5")
    for part in ("val", "testdev", "train_core"):
        with pytest.raises(ValueError, match="dev-only"):
            evaluator.evaluate([], "program_strict", part)


def test_frozen_pools_and_placebo_samples():
    data = PilotData()
    small = data.target_ids("compare", 250, 1000)
    medium = data.target_ids("compare", 1000, 1000)
    large = data.target_ids("compare", 4000, 1000)
    self_source = data.source_ids("compare", "self", 1000)
    placebo = data.source_ids("compare", "placebo_global", 1000)
    assert set(small) <= set(medium) <= set(large)
    assert len(set(large) & set(self_source)) == 0
    assert len(placebo) == 5371
    assert data.composition(placebo)["answer"] == {"yes": 2718, "no": 2653}
    real_source = data.source_ids("compare", "verifyAttr", 1000)
    shuffled = data.shuffled_labels(real_source, 1000)
    assert set(shuffled) == set(real_source)
    assert sorted(shuffled.values()) == sorted(data.by_id.loc[real_source, "answer"].tolist())
