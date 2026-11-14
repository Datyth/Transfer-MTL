"""Measure inference batching on a fixed dev sample without changing a run."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import gc
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import numpy as np
import pandas as pd
import torch

from .attention import enable_grouped_attention
from .data import ROOT, file_hash, load_protocol, load_questions, save_json
from .experiment import environment, model_checkpoint
from .model import YesNoModel
from .validation import score_batches


def verify_pause_target(pid):
    process = Path(f"/proc/{pid}")
    args = process.joinpath("cmdline").read_bytes().split(b"\0")
    if b"scripts/run_experiment.py" not in args or process.joinpath("cwd").resolve() != ROOT:
        raise ValueError("Pause target must be this project's experiment runner")
    state = next(line for line in process.joinpath("status").read_text().splitlines() if line.startswith("State:"))
    if state.split()[1] in ("T", "t"):
        raise ValueError("Target was already paused; refusing to take ownership of resuming it")


@contextmanager
def paused_process(pid):
    if pid is None:
        yield
        return
    verify_pause_target(pid)
    stopped = False
    try:
        os.kill(pid, signal.SIGSTOP)
        stopped = True
        print(f"Temporarily paused experiment PID {pid}", flush=True)
        yield
    finally:
        if stopped:
            try:
                os.kill(pid, signal.SIGCONT)
                print(f"Resumed experiment PID {pid}", flush=True)
            except ProcessLookupError:
                print(f"Experiment PID {pid} already exited", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare inference throughput and score stability for several batch sizes")
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--pause-pid", type=int)
    args = parser.parse_args(argv)
    if args.repeats < 1 or any(size < 1 for size in args.batch_sizes) or 1 not in args.batch_sizes:
        parser.error("Positive repeats/batch sizes and a batch-1 reference are required")
    sizes = sorted(set(args.batch_sizes))
    output = ROOT / "gqa_audit/outputs/stage3/diagnostics/batch_benchmark"
    output.mkdir(parents=True, exist_ok=True)
    # SIGTERM also unwinds the pause context, so an ordinary interruption resumes
    # the user's existing experiment rather than leaving it stopped.
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    protocol, evaluator = load_protocol(ROOT / "configs/stage3_protocol.FROZEN.yaml")
    questions = load_questions(evaluator)
    ids = pd.read_csv(ROOT / "gqa_audit/outputs/stage3/optimization_sample_ids.csv", dtype={"question_id": str}).question_id
    chosen = questions.set_index("question_id").loc[ids].reset_index()
    if len(chosen) != 256 or not chosen.part.eq("dev").all() or chosen.question_id.duplicated().any():
        raise ValueError("Benchmark must use the fixed 256-question dev sample")
    images = pd.read_csv(ROOT / "gqa_audit/outputs/stage3/image_manifest.csv", dtype={"imageId": str})
    lookup = {row.imageId: ROOT / row.relative_path for row in images.itertuples()}
    path, manifest = model_checkpoint("3b")
    chosen[["question_id", "part", "task"]].to_csv(output / "sample_ids.csv", index=False)
    rows = []
    with paused_process(args.pause_pid):
        # Wait for already-submitted kernels from the paused process to finish.
        time.sleep(2)
        memory_before = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True).strip()
        env = environment(output)  # Writes only inside the benchmark directory.
        model = YesNoModel(path, protocol)
        enable_grouped_attention(model.model)
        references = {}
        try:
            for size in sizes:
                for condition in ("image", "no_image"):
                    group = chosen.iloc[:size]
                    paths = [lookup[x] for x in group.imageId] if condition == "image" else None
                    model.score(group.question.tolist(), paths, protocol["templates"]["A"])
                    for repeat in range(args.repeats):
                        torch.cuda.reset_peak_memory_stats()
                        predictions, rate = score_batches(model, chosen, lookup, protocol["templates"]["A"], condition, size)
                        if size == 1 and repeat == 0:
                            references[condition] = predictions
                        baseline = references[condition]
                        if predictions.question_id.tolist() != baseline.question_id.tolist():
                            raise ValueError("Benchmark reference IDs differ")
                        delta = abs(predictions.score.to_numpy() - baseline.score.to_numpy())
                        flipped = int(predictions.pred.ne(baseline.pred).sum())
                        row = {"batch_size": size, "condition": condition, "repeat": repeat + 1,
                               "n": len(chosen), "questions_per_second": rate,
                               "estimated_main_seconds": 71334 / rate,
                               "max_score_difference": float(delta.max()), "mean_score_difference": float(delta.mean()),
                               "changed_predictions": flipped,
                               "max_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
                               "max_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2,
                               "status": "PASS" if delta.max() <= .05 else "FLAG"}
                        rows.append(row)
                        predictions.to_parquet(output / f"predictions_bs{size}_{condition}_repeat{repeat+1}.parquet", index=False)
                        pd.DataFrame(rows).to_csv(output / "timings.csv", index=False)
                        print(json.dumps(row), flush=True)
        finally:
            del model
            gc.collect()
            torch.cuda.empty_cache()
    frame = pd.DataFrame(rows)
    summary = frame.groupby(["batch_size", "condition"], as_index=False).agg(
        questions_per_second=("questions_per_second", "mean"),
        max_score_difference=("max_score_difference", "max"),
        changed_predictions=("changed_predictions", "max"),
        max_allocated_mib=("max_allocated_mib", "max"))
    summary["estimated_main_minutes"] = 71334 / summary.questions_per_second / 60
    summary["status"] = np.where(summary.max_score_difference <= .05, "PASS", "FLAG")
    summary.to_csv(output / "summary.csv", index=False)
    save_json(output / "manifest.json", {"created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_revision": manifest["revision"], "protocol_sha256": file_hash(ROOT / "configs/stage3_protocol.FROZEN.yaml"),
        "environment": env, "batch_sizes": sizes, "repeats": args.repeats, "pause_pid": args.pause_pid,
        "other_process_gpu_memory_mib_before_loading_benchmark": memory_before,
        "sample_sha256": file_hash(output / "sample_ids.csv"),
        "source_sha256": file_hash(Path(__file__)),
        "note": "Template A, fixed dev sample, warmed per batch/condition; no full-run settings or frozen rules changed"})
    print(summary.to_string(index=False), flush=True)
    return 0
