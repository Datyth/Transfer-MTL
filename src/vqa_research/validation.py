"""Compare a small real-model run to official attention before a long job."""

import argparse
from datetime import datetime, timezone
import json
import time

import numpy as np
import pandas as pd
import torch

from .attention import enable_grouped_attention, restore_attention
from .data import ROOT, file_hash, load_protocol, load_questions, save_json
from .experiment import environment, model_checkpoint
from .model import YesNoModel


def score_batches(model, frame, lookup, template, condition, batch_size):
    rows = []
    start = time.perf_counter()
    for offset in range(0, len(frame), batch_size):
        group = frame.iloc[offset:offset + batch_size]
        images = [lookup[x] for x in group.imageId] if condition == "image" else None
        values = model.score(group.question.tolist(), images, template)
        rows.append(pd.DataFrame({"question_id": group.question_id.tolist(), **values}))
    return pd.concat(rows, ignore_index=True), len(frame) / (time.perf_counter() - start)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate equivalent grouped SDPA against the official model")
    parser.add_argument("--batch-size", type=int, default=1)
    args = parser.parse_args(argv)
    output = ROOT / "gqa_audit/outputs/stage3"
    environment(output)
    protocol, evaluator = load_protocol(ROOT / "configs/stage3_protocol.FROZEN.yaml")
    questions = load_questions(evaluator)
    dev = questions[questions.part.eq("dev")]
    rng = np.random.default_rng(0)
    chosen = dev.iloc[rng.choice(len(dev), 256, replace=False)].sort_values("question_id").reset_index(drop=True)
    chosen[["question_id", "part", "task"]].to_csv(output / "optimization_sample_ids.csv", index=False)
    images = pd.read_csv(output / "image_manifest.csv", dtype={"imageId": str})
    lookup = {row.imageId: ROOT / row.relative_path for row in images.itertuples()}
    path, manifest = model_checkpoint("3b")
    model = YesNoModel(path, protocol)
    # Warm up on the same inputs before either measured implementation.
    score_batches(model, chosen.iloc[:args.batch_size], lookup, protocol["templates"]["A"], "image", args.batch_size)
    cases = [("A", "image", chosen), ("A", "no_image", chosen), ("B", "image", chosen.iloc[:64]),
             ("B", "no_image", chosen.iloc[:64])]
    references, rates, kernel_counts = {}, {}, {}
    for implementation in ("official", "grouped"):
        if implementation == "grouped":
            originals = enable_grouped_attention(model.model)
        for template, condition, frame in cases:
            key = f"{template}_{condition}"
            result, rate = score_batches(model, frame, lookup, protocol["templates"][template], condition, args.batch_size)
            references[(implementation, key)] = result
            rates[f"{implementation}_{key}"] = rate
            print(f"{implementation} {key}: {len(frame)} questions, {rate:.2f}/s", flush=True)
        group = chosen.iloc[:args.batch_size]
        with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU]) as profile:
            score_batches(model, group, lookup, protocol["templates"]["A"], "image", args.batch_size)
        events = profile.key_averages()
        (output / f"profile_{implementation}.txt").write_text(events.table(sort_by="self_cpu_time_total", row_limit=25))
        kernel_counts[implementation] = {item.key: item.count for item in events if item.key == "aten::scaled_dot_product_attention"}
    rows = []
    for template, condition, frame in cases:
        key = f"{template}_{condition}"
        first, second = references[("official", key)], references[("grouped", key)]
        assert first.question_id.tolist() == second.question_id.tolist()
        delta = np.abs(first.score.to_numpy() - second.score.to_numpy())
        agreement = float(first.pred.eq(second.pred).mean())
        rows.append({"template": template, "condition": condition, "n": len(frame),
                     "max_score_difference": float(delta.max()), "prediction_agreement": agreement})
        print("equivalence", rows[-1], flush=True)
        first.add_prefix("official_").join(second.add_prefix("grouped_")).to_parquet(
            output / f"optimization_equivalence_{key}.parquet", index=False)
        if delta.max() > .05 or agreement != 1:
            raise ValueError("Grouped SDPA did not preserve the reference scores/predictions")
    batch_rows = []
    for condition in ("image", "no_image"):
        single, rate = score_batches(model, chosen, lookup, protocol["templates"]["A"], condition, 1)
        batched = references[("grouped", f"A_{condition}")]
        differences = abs(single.score.to_numpy() - batched.score.to_numpy())
        batch_rows.append({"condition": condition, "n": len(chosen), "max_score_difference": float(differences.max()),
                           "status": "FLAG" if differences.max() > .05 else "PASS"})
        rates[f"grouped_A_{condition}_batch1"] = rate
        print("batch invariance", batch_rows[-1], flush=True)
    # Short greedy-generation comparison, independent of the registered 500-question run.
    small = chosen.iloc[:8]
    paths = [lookup[x] for x in small.imageId]
    optimized_generation = model.generate(small.question.tolist(), paths, protocol["templates"]["A"])
    restore_attention(originals)
    official_generation = model.generate(small.question.tolist(), paths, protocol["templates"]["A"])
    if official_generation != optimized_generation:
        raise ValueError("Grouped SDPA changed the generation smoke test")
    result = {"validated_at_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS",
              "model_revision": manifest["revision"], "batch_size": args.batch_size,
              "equivalence": rows, "batch_invariance": batch_rows, "questions_per_second": rates,
              "sdpa_call_counts_per_batch": kernel_counts, "generation_smoke_agreement": 1.0,
              "generation_smoke_n": len(small),
              "attention_source_sha256": file_hash(ROOT / "src/vqa_research/attention.py"),
              "model_source_sha256": file_hash(ROOT / "src/vqa_research/model.py")}
    result["environment_sha256"] = file_hash(output / "environment.json")
    save_json(output / "optimization_validation.json", result)
    return 0
