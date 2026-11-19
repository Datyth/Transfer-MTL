"""Deterministic, resumable phase training for the Stage 3.5 probe."""

from __future__ import annotations

import json
import math
import os
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader

from gqa_audit.stage2_core import canonical_hash
from .data import PilotData, rng
from .features import ROOT, assert_gpu_exclusive, sha256
from .model import ProbeModel, parameter_counts


def run_id(config: dict) -> str:
    return canonical_hash(config)


def complete(path: Path, config: dict, expected_ids: list[str]) -> bool:
    record, predictions = path / "run.json", path / "predictions.parquet"
    if not record.exists() or not predictions.exists():
        return False
    try:
        status = json.loads(record.read_text())
        frame = pd.read_parquet(predictions)
        return (status.get("status") == "complete" and status.get("run_id") == run_id(config) and
                status.get("config") == config and set(frame.question_id) == set(expected_ids) and
                len(frame) == len(expected_ids) and
                list(frame.columns) == ["question_id", "score", "p_yes", "pred"] and
                frame.question_id.map(type).eq(str).all() and
                np.isfinite(frame.score).all() and frame.p_yes.between(0, 1).all() and
                frame.pred.eq(np.where(frame.score > 0, "yes", "no")).all() and
                ("predictions_sha256" not in status or status["predictions_sha256"] == sha256(predictions)))
    except (OSError, ValueError, KeyError):
        return False


def _atomic_json(path: Path, obj: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _seed_number(seed: int, component: int) -> int:
    return int(rng(seed, component).integers(0, 2**31))


def _optimizer(model: nn.Module, lr_fusion: float, train_text: bool):
    groups = {}
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        lr = 1e-5 if name.startswith("text_encoder.") and train_text else lr_fusion
        decay = 0.0 if name.endswith("bias") or "norm" in name.lower() or "layernorm" in name.lower() else 0.01
        groups.setdefault((lr, decay), []).append(parameter)
    return torch.optim.AdamW([{"params": params, "lr": lr, "weight_decay": decay}
                              for (lr, decay), params in groups.items()], betas=(0.9, 0.999), eps=1e-8)


def _schedule(optimizer, steps: int):
    warmup = max(1, math.ceil(0.05 * steps))
    def factor(step):
        if step < warmup:
            return (step + 1) / warmup
        return 0.5 * (1 + math.cos(math.pi * min(1.0, (step - warmup) / max(1, steps - warmup))))
    return torch.optim.lr_scheduler.LambdaLR(optimizer, factor)


def train_run(config: dict, data: PilotData | None = None, root: Path = ROOT, *,
              training_ids=None, evaluation_ids=None, labels=None, initial_checkpoint=None,
              save_checkpoint=False) -> Path:
    """Run one target-only P1/P2/P3 cell; return its hash directory."""
    root = Path(root)
    data = data or PilotData(root)
    task, seed, budget = config["task"], config["seed"], config["budget"]
    target_ids = data.target_ids(task, budget, seed) if training_ids is None else list(training_ids)
    dev_ids = data.membership[task]["dev"] if evaluation_ids is None else list(evaluation_ids)
    allowed_dev = {qid for task_parts in data.membership.values() for qid in task_parts["dev"]}
    if not set(dev_ids) <= allowed_dev:
        raise ValueError("Stage 3.5 evaluation is dev-only")
    if len(set(target_ids)) != len(target_ids):
        raise ValueError("Duplicate training IDs")
    if not data.by_id.loc[target_ids, "part"].eq("train_core").all():
        raise ValueError("Training requires train_core only")
    path = root / "gqa_audit/outputs/stage3_5/runs" / run_id(config)
    checkpoint = root / "checkpoints/probe_pilot" / f"{run_id(config)}.pt"
    if complete(path, config, dev_ids):
        record = json.loads((path / "run.json").read_text())
        if not save_checkpoint or (checkpoint.exists() and record.get("checkpoint_sha256") == sha256(checkpoint)):
            print(f"SKIP complete {task} budget={budget} seed={seed} {config.get('arm', '')} {path.name[:12]}", flush=True)
            return path
    assert_gpu_exclusive()
    print(f"TRAIN {task} budget={budget} seed={seed} n={len(target_ids)} epochs={config['epochs']} "
          f"{config.get('arm', '')} {path.name[:12]}", flush=True)
    path.mkdir(parents=True, exist_ok=True)
    if budget == "full" and config["epochs"] != 10:
        raise ValueError("Full budget must train exactly 10 epochs")
    train_set = data.dataset(target_ids, blank=config.get("blank", False), labels=labels)
    dev_set = data.dataset(dev_ids, blank=config.get("blank", False))
    torch.manual_seed(_seed_number(seed, 3))
    torch.cuda.manual_seed_all(_seed_number(seed, 3))
    model = ProbeModel(root / "checkpoints/clip-vit-base-patch16",
                       train_text=config["train_text"], max_text_tokens=32).to("cuda")
    counts = parameter_counts(model)
    if initial_checkpoint is not None:
        model.load_state_dict(torch.load(initial_checkpoint, map_location="cpu", weights_only=True))
    torch.manual_seed(_seed_number(seed, 6))
    torch.cuda.manual_seed_all(_seed_number(seed, 6))
    torch.use_deterministic_algorithms(True, warn_only=True)
    generator = torch.Generator().manual_seed(_seed_number(seed, 4))
    loader = DataLoader(train_set, batch_size=64, shuffle=True, generator=generator,
                        num_workers=0, drop_last=False, pin_memory=True)
    optimizer = _optimizer(model, config["lr_fusion"], config["train_text"])
    steps = len(loader) * config["epochs"]
    scheduler = _schedule(optimizer, steps)
    observed_warnings = []
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    model.train()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        for _ in range(config["epochs"]):
            for batch in loader:
                batch = {key: value.to("cuda", non_blocking=True) for key, value in batch.items()}
                batch_labels = batch.pop("labels")
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    scores = model(**batch)
                    loss = nn.functional.binary_cross_entropy_with_logits(scores.float(), batch_labels)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
        observed_warnings = sorted({str(item.message) for item in captured})
    torch.cuda.synchronize()
    training_seconds = time.perf_counter() - start
    model.eval()
    start = time.perf_counter()
    scores = []
    for batch in DataLoader(dev_set, batch_size=64, shuffle=False, num_workers=0, pin_memory=True):
        batch.pop("labels")
        batch = {key: value.to("cuda", non_blocking=True) for key, value in batch.items()}
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            scores.extend(model(**batch).float().cpu().numpy().tolist())
    torch.cuda.synchronize()
    evaluation_seconds = time.perf_counter() - start
    scores = np.asarray(scores, dtype=np.float32)
    probabilities = 1.0 / (1.0 + np.exp(-scores))
    predictions = pd.DataFrame({"question_id": dev_ids, "score": scores, "p_yes": probabilities,
                                "pred": np.where(scores > 0, "yes", "no")})
    temporary = path / "predictions.tmp.parquet"
    predictions.to_parquet(temporary, index=False)
    os.replace(temporary, path / "predictions.parquet")
    if save_checkpoint:
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), checkpoint.with_suffix(".tmp"))
        os.replace(checkpoint.with_suffix(".tmp"), checkpoint)
    _atomic_json(path / "run.json", {"status": "complete", "config": config, "run_id": run_id(config),
                                     "seed_components": {str(i): _seed_number(seed, i) for i in range(1, 7)},
                                     "predictions_sha256": sha256(path / "predictions.parquet"),
                                     "checkpoint_sha256": sha256(checkpoint) if save_checkpoint else None,
                                     "sample_composition": data.composition(target_ids),
                                     "training_ids_hash": canonical_hash(target_ids),
                                     "label_changed_share": (float(np.mean([labels[q] != data.by_id.loc[q, "answer"]
                                                                            for q in labels])) if labels else None),
                                     "parameters": counts, "examples_seen": len(train_set) * config["epochs"],
                                     "optimizer_steps": steps, "training_seconds": training_seconds,
                                     "evaluation_seconds": evaluation_seconds,
                                     "examples_per_second": len(train_set) * config["epochs"] / training_seconds,
                                     "peak_gpu_bytes": torch.cuda.max_memory_allocated(),
                                     "determinism_warnings": observed_warnings})
    print(f"DONE {path.name[:12]} train={training_seconds:.1f}s eval={evaluation_seconds:.1f}s", flush=True)
    return path
