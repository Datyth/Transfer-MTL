"""Pre-registered phase cardinalities, shared sampling and paired-bootstrap tests."""
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
import torch

from gqa_audit.evaluation import paired_contrast
from src.vqa_research.probe.transfer import phase_plan, transfer_plan, source_spec, source_sample
from src.vqa_research.probe.train import complete, run_id
from src.vqa_research.lora_pilot import first_token_loss
from src.vqa_research.probe.gates import select_metric
from gqa_audit.evaluation import seed_primary_interval


RECIPE = {"lr_fusion": .0001, "train_text": False, "epochs": 30}


def test_exact_phase_plans_and_source_sharing():
    curves, blank = phase_plan("curves", RECIPE), phase_plan("blank", RECIPE)
    assert len(curves) == 85 and len(blank) == 25
    assert all(c["epochs"] == 10 for c in curves + blank if c["budget"] == "full")
    assert len({run_id(c) for c in curves}) == 85
    assert all(c["blank"] for c in blank)
    sources, targets = transfer_plan(RECIPE)
    assert len(sources) == 27 and len(targets) == 99
    assert len({run_id(c) for c in targets}) == 99
    assert source_spec("logic", "exist") == source_spec("verifyRel", "exist")
    assert source_spec("logic", "placebo_shuffled") == source_spec("verifyRel", "placebo_shuffled")
    assert source_spec("logic", "self") != source_spec("verifyRel", "self")


def frame(perfect=True):
    return pd.DataFrame({"question_id": list("abcd"), "imageId": ["x", "x", "y", "y"],
                         "answer": ["yes", "no", "yes", "no"], "part": "dev",
                         "pred": ["yes", "no", "yes", "no"] if perfect else ["no", "yes", "no", "yes"],
                         "score": [1., -1., 1., -1.] if perfect else [-1., 1., -1., 1.],
                         "p_yes": [.8, .2, .8, .2] if perfect else [.2, .8, .2, .8]})


def test_paired_contrast_known_answer_deterministic_and_direction():
    a, c = {1000: frame(), 1001: frame()}, {1000: frame(False), 1001: frame(False)}
    result = paired_contrast(a, c, [1000, 1001], resamples=20)
    assert result == paired_contrast(a, c, [1000, 1001], resamples=20)
    assert result["primary_gain"]["mean"] == 1
    assert result["auroc_gain"]["mean"] == 1
    assert result["log_loss_gain"]["mean"] == pytest.approx(np.log(4))
    assert paired_contrast(a, a, [1000, 1001], resamples=20)["primary_gain"]["z"] == 0
    c[1000].loc[0, "part"] = "val"
    with pytest.raises(ValueError, match="dev-only"):
        paired_contrast(a, c, [1000, 1001], resamples=20)


def test_seed_ci_and_frozen_metric_selection_boundary():
    assert seed_primary_interval([frame(), frame()], resamples=20) == {"ci_low": 1., "ci_high": 1.}
    result = select_metric([{"primary_gain": {"z": 2.}, "log_loss_gain": {"z": 2.5}}])
    assert result["selected"] == "log_loss_gain"
    assert select_metric([{"primary_gain": {"z": 2.}, "log_loss_gain": {"z": 2.49}}])["selected"] == "primary_gain"


def test_first_assistant_loss_uses_only_last_context_position():
    logits = torch.zeros((2, 3, 7), requires_grad=True)
    targets = torch.tensor([1, 5])
    loss = first_token_loss(logits, targets)
    assert loss.item() == pytest.approx(2 * np.log(7))
    loss.backward()
    assert logits.grad[:, :-1].count_nonzero() == 0
    assert logits.grad[:, -1].count_nonzero() > 0


def test_complete_run_requires_config_and_exact_prediction_ids(tmp_path):
    import json
    config = {"task": "compare", "seed": 1000}
    pd.DataFrame({"question_id": ["a"], "score": [0.], "p_yes": [.5], "pred": ["no"]}).to_parquet(
        tmp_path / "predictions.parquet", index=False)
    assert not complete(tmp_path, config, ["a"])
    (tmp_path / "run.json").write_text(json.dumps({"status": "complete", "config": config, "run_id": run_id(config)}))
    assert complete(tmp_path, config, ["a"])
    assert not complete(tmp_path, config, ["a", "b"])
    assert not complete(tmp_path, {**config, "seed": 1001}, ["a"])


@pytest.mark.skipif(__import__("os").environ.get("RUN_STAGE35_GPU_TESTS") != "1", reason="explicit GPU smoke test")
def test_source_checkpoint_seq_joint_gpu(tmp_path):
    import json
    from src.vqa_research.probe.features import ROOT
    from src.vqa_research.probe.data import PilotData
    from src.vqa_research.probe.train import train_run
    data = PilotData()
    (tmp_path / "checkpoints").mkdir()
    (tmp_path / "checkpoints/clip-vit-base-patch16").symlink_to(ROOT / "checkpoints/clip-vit-base-patch16", target_is_directory=True)
    source = data.target_ids("exist", 250, 1000)[:8]
    target = data.target_ids("compare", 250, 1000)[:8]
    dev = data.membership["compare"]["dev"][:4]
    config = {"task": "compare", "budget": 250, "seed": 1000, "epochs": 1,
              "lr_fusion": .0001, "train_text": False, "smoke_test": True}
    labels = data.shuffled_labels(source, 1000)
    source_path = train_run({**config, "arm": "source"}, data, tmp_path, training_ids=source,
                            evaluation_ids=dev, labels=labels, save_checkpoint=True)
    checkpoint = tmp_path / "checkpoints/probe_pilot" / f"{source_path.name}.pt"
    assert checkpoint.exists()
    assert json.loads((source_path / "run.json").read_text())["label_changed_share"] is not None
    sequential = train_run({**config, "arm": "Seq"}, data, tmp_path, training_ids=target,
                           evaluation_ids=dev, initial_checkpoint=checkpoint)
    joint = train_run({**config, "arm": "Joint"}, data, tmp_path, training_ids=source + target,
                     evaluation_ids=dev)
    assert json.loads((sequential / "run.json").read_text())["examples_seen"] == 8
    assert json.loads((joint / "run.json").read_text())["examples_seen"] == 16
    before = (joint / "run.json").stat().st_mtime_ns
    train_run({**config, "arm": "Joint"}, data, tmp_path, training_ids=source + target, evaluation_ids=dev)
    assert (joint / "run.json").stat().st_mtime_ns == before
