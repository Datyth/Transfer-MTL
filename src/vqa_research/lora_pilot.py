"""Dev-only Qwen pilot: official SDPA, first-assistant-token CE, unmerged LoRA."""
import gc
import json
import math
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from peft import LoraConfig, get_peft_model
from transformers import get_cosine_schedule_with_warmup

from .model import YesNoModel
from .probe.data import PilotData, rng
from .probe.features import ROOT, assert_gpu_exclusive
from .probe.train import run_id, complete, _atomic_json, _seed_number


def wrapper(root):
    protocol = yaml.safe_load((root / "configs/stage3_protocol.FROZEN.yaml").read_text())
    return YesNoModel(root / "checkpoints/Qwen2.5-VL-3B-Instruct", protocol)


def paths(data, ids):
    return [data.root / "data/gqa/images/images" / f"{image}.jpg" for image in data.by_id.loc[ids, "image_id"]]


def evaluate_qwen(model, data, ids):
    if not data.by_id.loc[ids, "part"].eq("dev").all():
        raise ValueError("Qwen pilot evaluation is dev-only")
    rows = []
    model.model.eval()
    for position, (qid, image) in enumerate(zip(ids, paths(data, ids)), start=1):
        result = model.score([data.by_id.loc[qid, "question"]], [image], model.protocol["templates"]["A"])
        rows.append({"question_id": qid, **{key: result[key][0] for key in ("score", "p_yes", "pred")}})
        if position % 32 == 0:
            print(f"Qwen dev: {position}/{len(ids)}", flush=True)
    return pd.DataFrame(rows)


def regression(model, data):
    ids = data.membership["compare"]["dev"]
    chosen = [ids[i] for i in rng(1000, 1).choice(len(ids), 128, replace=False)]
    fresh = evaluate_qwen(model, data, chosen)
    old = pd.read_parquet(data.root / "gqa_audit/outputs/stage3/predictions_3b_image.parquet")
    merged = fresh.merge(old[["question_id", "score"]], on="question_id", validate="one_to_one")
    if len(merged) != 128:
        raise ValueError("STOP: missing Stage 3 regression reference IDs")
    difference = float(np.abs(merged.score_x - merged.score_y).max())
    report = {"n": 128, "max_score_difference": difference, "status": "PASS" if difference <= .001 else "STOP"}
    _atomic_json(data.root / "gqa_audit/outputs/stage3_5/qwen_regression.json", report)
    if difference > .001:
        raise ValueError(f"STOP: Qwen base regression difference {difference} > 0.001")
    return report


def configure_lora(model):
    names = [name for name, layer in model.named_modules() if isinstance(layer, torch.nn.Linear)
             and ".language_model." in name and name.rsplit(".", 1)[-1] in
             {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}]
    if not names:
        raise ValueError("No language-only LoRA projections found")
    model.requires_grad_(False)
    adapted = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=.05,
                                               target_modules=names, bias="none", task_type="CAUSAL_LM"))
    for name, parameter in adapted.named_parameters():
        if parameter.requires_grad:
            if "lora_" not in name or "visual" in name:
                raise ValueError(f"Unexpected trainable parameter: {name}")
            parameter.data = parameter.data.float()
    adapted.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    adapted.enable_input_require_grads()
    adapted.config.use_cache = False
    return adapted


def first_token_loss(logits, targets):
    if logits.ndim != 3 or logits.shape[0] != len(targets):
        raise ValueError("Expected batched first-assistant-position logits")
    return torch.nn.functional.cross_entropy(logits[:, -1, :].float(), targets, reduction="sum")


def run_qwen(root=ROOT, *, benchmark=False):
    assert_gpu_exclusive()
    data = PilotData(root)
    output = root / "gqa_audit/outputs/stage3_5"
    # Recheck official base scoring each invocation before adapters are attached.
    base = wrapper(root)
    regression(base, data)
    del base
    gc.collect()
    torch.cuda.empty_cache()
    for budget in ([1000] if benchmark else [1000, 4000]):
        for seed in ([1000] if benchmark else [1000, 1001]):
            config = {"model": "Qwen2.5-VL-3B-Instruct", "revision": "66285546d2b821cf421d4f5eb2576359d3770cd3",
                      "task": "compare", "budget": budget, "seed": seed, "epochs": 2,
                      "lora_r": 16, "alpha": 32, "dropout": .05, "lr": .0001,
                      "micro_batch": 4, "accumulation": 4, "attention": "sdpa", "eval_batch": 1,
                      "scope": "language_model", "loss": "first_token_ce", "benchmark": benchmark}
            destination = output / ("qwen_benchmark" if benchmark else "qwen_runs") / run_id(config)
            dev_ids = data.membership["compare"]["dev"]
            if not benchmark and complete(destination, config, dev_ids):
                continue
            assert_gpu_exclusive()
            destination.mkdir(parents=True, exist_ok=True)
            torch.manual_seed(_seed_number(seed, 3))
            model = wrapper(root)
            model.model = configure_lora(model.model)
            ids = data.target_ids("compare", budget, seed)
            optimizer = torch.optim.AdamW([p for p in model.model.parameters() if p.requires_grad], lr=1e-4,
                                         betas=(.9, .999), eps=1e-8, weight_decay=0)
            total_steps = 2 * math.ceil(budget / 16)
            schedule = get_cosine_schedule_with_warmup(optimizer, math.ceil(.05 * total_steps), total_steps)
            torch.manual_seed(_seed_number(seed, 6))
            torch.use_deterministic_algorithms(True, warn_only=True)
            order_rng = rng(seed, 4)
            torch.cuda.reset_peak_memory_stats()
            start, seen, completed = time.perf_counter(), 0, 0
            model.model.train()
            warning_context = warnings.catch_warnings(record=True)
            captured_warnings = warning_context.__enter__()
            warnings.simplefilter("once")
            for epoch in range(2):
                order = [ids[i] for i in order_rng.permutation(len(ids))]
                for offset in range(0, len(order), 16):
                    effective = order[offset:offset + 16]
                    optimizer.zero_grad(set_to_none=True)
                    for micro_offset in range(0, len(effective), 4):
                        batch_ids = effective[micro_offset:micro_offset + 4]
                        inputs = model.inputs(data.by_id.loc[batch_ids, "question"].tolist(), paths(data, batch_ids),
                                              model.protocol["templates"]["A"])
                        labels = torch.tensor([model.token_ids[data.by_id.loc[qid, "answer"]] for qid in batch_ids],
                                              device=model.model.device)
                        with torch.autocast("cuda", dtype=torch.bfloat16):
                            logits = model.model(**inputs, use_cache=False, logits_to_keep=1).logits
                            loss = first_token_loss(logits, labels) / len(effective)
                        loss.backward()
                        seen += len(batch_ids)
                    optimizer.step()
                    schedule.step()
                    completed += 1
                    if benchmark and completed == 8:
                        break
                if benchmark:
                    break
            torch.cuda.synchronize()
            seconds = time.perf_counter() - start
            evaluation_start = time.perf_counter()
            predictions = evaluate_qwen(model, data, dev_ids[:32] if benchmark else dev_ids)
            warning_context.__exit__(None, None, None)
            evaluation_seconds = time.perf_counter() - evaluation_start
            if not benchmark:
                predictions.to_parquet(destination / "predictions.parquet", index=False)
            record = {"config": config, "run_id": run_id(config), "status": "benchmark" if benchmark else "complete",
                      "examples_seen": seen, "optimizer_steps": completed, "training_seconds": seconds,
                      "examples_per_second": seen / seconds, "evaluation_seconds": evaluation_seconds,
                      "evaluation_questions_per_second": len(predictions) / evaluation_seconds,
                      "peak_gpu_bytes": torch.cuda.max_memory_allocated()}
            record["determinism_warnings"] = sorted({str(item.message) for item in captured_warnings})
            _atomic_json(destination / "run.json", record)
            if benchmark:
                _atomic_json(output / "qwen_cost_benchmark.json", record)
            del model, optimizer, schedule, logits, loss, inputs
            gc.collect()
            torch.cuda.empty_cache()
