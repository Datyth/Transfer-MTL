"""A linear research experiment: verify, score, check, evaluate, report."""

import argparse
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import warnings

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import pandas as pd
import torch

from .data import (ROOT, accepted_snapshot, file_hash, load_protocol, load_questions,
                   prepare_images, save_json, stratified_sample)
from .inference import run_predictions
from .model import YesNoModel


def environment(output):
    random.seed(0)
    np.random.seed(0)
    torch.manual_seed(0)
    torch.cuda.manual_seed_all(0)
    torch.set_num_threads(8)
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    value = torch.ones((32, 32), device="cuda", dtype=torch.bfloat16)
    if float((value @ value)[0, 0]) != 32:
        raise RuntimeError("bf16 GPU smoke test failed")
    (output / "env_datpt_mtl.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True))
    result = {"python": sys.version, "executable": sys.executable,
              "packages": {p: importlib.metadata.version(p) for p in (
                  "torch", "torchvision", "transformers", "accelerate", "qwen-vl-utils", "pillow", "numpy",
                  "pandas", "pyarrow", "pyyaml", "ijson", "scikit-learn", "pytest")},
              "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0),
              "capability": list(torch.cuda.get_device_capability(0)),
              "driver": subprocess.check_output(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], text=True).strip(),
              "bf16_matmul": "PASS", "seed": 0, "deterministic_algorithms": "warn_only",
              "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
              "image_processor": "saved slow processor, use_fast=False",
              "environment_override": "Use existing datpt_mtl as explicitly requested by the human"}
    save_json(output / "environment.json", result)
    return result


def model_checkpoint(name):
    if name == "3b":
        source = ROOT / "gqa_audit/outputs/stage3_preparation/model_manifest.json"
        manifest = json.loads(source.read_text())
        path = ROOT / manifest["local_path"]
    else:
        from huggingface_hub import HfApi, snapshot_download
        path = ROOT / "checkpoints/Qwen2.5-VL-7B-Instruct"
        manifest_path = path / "download_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
        else:
            model_id = "Qwen/Qwen2.5-VL-7B-Instruct"
            info = HfApi().model_info(model_id, files_metadata=True)
            snapshot_download(model_id, revision=info.sha, local_dir=path)
            files = []
            for item in info.siblings:
                local = path / item.rfilename
                digest = file_hash(local)
                if local.stat().st_size != item.size or item.lfs and digest != item.lfs.sha256:
                    raise ValueError(f"Downloaded checkpoint mismatch: {local}")
                files.append({"path": item.rfilename, "size_bytes": item.size, "sha256": digest})
            manifest = {"model_id": model_id, "revision": info.sha,
                        "local_path": str(path.relative_to(ROOT)), "files": files}
            save_json(manifest_path, manifest)
    for record in manifest["files"]:
        file = path / record["path"]
        if file.stat().st_size != record["size_bytes"] or file_hash(file) != record["sha256"]:
            raise ValueError(f"Checkpoint hash mismatch: {file}")
    return path, manifest


def run_model(name, path, manifest, questions, images, protocol, evaluator, output, batch_size):
    from .analysis import evaluate_model
    from .attention import enable_grouped_attention
    from .report import diagnostic_checks
    if name == "3b":
        validation_path = output / "optimization_validation.json"
        if not validation_path.exists():
            raise ValueError("Run python scripts/check_inference.py before the full experiment")
        validation = json.loads(validation_path.read_text())
        if (validation["status"] != "PASS" or validation["model_revision"] != manifest["revision"]
                or validation["batch_size"] != batch_size
                or validation.get("environment_sha256") != file_hash(output / "environment.json")
                or validation["attention_source_sha256"] != file_hash(ROOT / "src/vqa_research/attention.py")
                or validation["model_source_sha256"] != file_hash(ROOT / "src/vqa_research/model.py")
                or any(row["status"] != "PASS" for row in validation["batch_invariance"])):
            raise ValueError("Runtime/batch validation differs or failed; run scripts/check_inference.py with the same batch size")
    model = YesNoModel(path, protocol)
    if name == "3b":
        enable_grouped_attention(model.model)
    save_json(output / f"tokens_{name}.json", model.token_ids)
    image_lookup = {row.imageId: ROOT / row.relative_path for row in images.itertuples()}
    inference_sources = {str(path.relative_to(ROOT)): file_hash(path) for path in (
        ROOT / "src/vqa_research/model.py", ROOT / "src/vqa_research/data.py", ROOT / "src/vqa_research/inference.py",
        ROOT / "src/vqa_research/attention.py")}
    fingerprint = {"revision": manifest["revision"], "model_files": manifest["files"],
        "protocol": file_hash(ROOT / "configs/stage3_protocol.FROZEN.yaml"),
        "images": file_hash(output / "image_manifest.csv"), "inference_sources": inference_sources,
        "environment": file_hash(output / "environment.json"),
        "question_text": sha256(questions[["question_id", "question"]].to_json(orient="records").encode()).hexdigest()}
    dev = questions[questions.part.eq("dev")]
    template_sample = stratified_sample(questions, 400)
    generation_sample = stratified_sample(questions, 100)
    batch_sample = dev.iloc[np.random.default_rng(0).choice(len(dev), 256, replace=False)].sort_values("question_id")
    for label, frame in (("template", template_sample), ("generation", generation_sample), ("batch", batch_sample)):
        frame[["question_id", "part", "task"]].to_csv(output / f"{label}_sample_ids.csv", index=False)
    # Warm up once, then time the same deterministic 64-question sample. No labels are used.
    warm = dev.iloc[:batch_size]
    model.score(warm.question.tolist(), [image_lookup[x] for x in warm.imageId], protocol["templates"]["A"])
    rates = {}
    for condition in ("image", "no_image"):
        start = time.perf_counter()
        for offset in range(0, 64, batch_size):
            group = dev.iloc[offset:min(offset + batch_size, 64)]
            paths = [image_lookup[x] for x in group.imageId] if condition == "image" else None
            model.score(group.question.tolist(), paths, protocol["templates"]["A"])
        seconds = time.perf_counter() - start
        rates[condition] = {"questions_per_second": 64 / seconds,
                            "estimated_full_seconds": len(questions) / (64 / seconds)}
    save_json(output / f"throughput_{name}.json", rates)
    print(f"{name} throughput and full-run estimate: {rates}", flush=True)
    predictions = {}
    sensitivity = {}
    for condition in ("image", "no_image"):
        predictions[condition] = run_predictions(model, questions, image_lookup, protocol["templates"]["A"],
            condition, output / "shards" / f"{name}_{condition}_A", fingerprint, batch_size)
        predictions[condition].to_parquet(output / f"predictions_{name}_{condition}.parquet", index=False)
        sensitivity[condition] = run_predictions(model, template_sample, image_lookup, protocol["templates"]["B"],
            condition, output / "shards" / f"{name}_{condition}_B", fingerprint, batch_size)
        sensitivity[condition].to_parquet(output / f"template_B_{name}_{condition}.parquet", index=False)
    batch_diffs = []
    for condition in ("image", "no_image"):
        singleton = run_predictions(model, batch_sample, image_lookup, protocol["templates"]["A"],
            condition, output / "shards" / f"{name}_{condition}_batch1", fingerprint, 1)
        comparison = singleton[["question_id", "score"]].merge(predictions[condition][["question_id", "score"]],
            on="question_id", suffixes=("_single", "_batch"), validate="one_to_one")
        comparison["abs_difference"] = abs(comparison.score_single - comparison.score_batch)
        comparison["condition"] = condition
        batch_diffs.append(comparison)
    batch_diffs = pd.concat(batch_diffs)
    batch_diffs.to_csv(output / f"batch_invariance_{name}.csv", index=False)
    generation_path = output / f"generation_sanity_{name}.csv"
    generations = []
    for offset in range(0, len(generation_sample), batch_size):
        group = generation_sample.iloc[offset:offset + batch_size]
        values = model.generate(group.question.tolist(), [image_lookup[x] for x in group.imageId], protocol["templates"]["A"])
        generations.append(pd.DataFrame({"question_id": group.question_id.tolist(), **{
            key: [row[key] for row in values] for key in ("generation", "first_word")}}))
    generations = pd.concat(generations, ignore_index=True).merge(predictions["image"][["question_id", "pred"]],
        on="question_id", validate="one_to_one")
    generations.to_csv(generation_path, index=False)
    del model
    torch.cuda.empty_cache()
    print(f"{name}: evaluating frozen units and paired image-cluster intervals ...", flush=True)
    metrics = evaluate_model(evaluator, questions, predictions["image"], predictions["no_image"], name, output)
    return diagnostic_checks(questions, predictions, sensitivity, generations, batch_diffs, metrics, name, output)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Frozen GQA zero-shot experiment; no training")
    parser.add_argument("--models", nargs="+", choices=["3b", "7b"], default=["3b"])
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--evaluate-only", action="store_true")
    args = parser.parse_args(argv)
    if args.batch_size < 1 or len(args.models) != len(set(args.models)):
        parser.error("Positive batch size and unique models required")
    if args.models not in (["3b"], ["3b", "7b"]):
        parser.error("Run 3b first; use --models 3b 7b to explicitly enable phase B")
    output = ROOT / "gqa_audit/outputs/stage3"
    output.mkdir(parents=True, exist_ok=True)
    run_lock = (output / "run.lock").open("a")
    try:
        fcntl.flock(run_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError("An experiment is already running in this output directory") from None
    protocol, evaluator = load_protocol(ROOT / "configs/stage3_protocol.FROZEN.yaml")
    snapshot_path = output / "accepted_outputs_snapshot.json"
    snapshot = accepted_snapshot()
    if snapshot_path.exists() and snapshot != json.loads(snapshot_path.read_text()):
        raise ValueError("Accepted audit outputs changed; STOP")
    save_json(snapshot_path, snapshot)
    env = environment(output)
    questions = load_questions(evaluator)
    manifest = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "status": "RUNNING",
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_hashes": {str(p.relative_to(ROOT)): file_hash(p) for folder in ("src", "scripts", "configs")
                          for p in sorted((ROOT / folder).rglob("*")) if p.is_file() and "__pycache__" not in p.parts},
        "protocol_sha256": file_hash(ROOT / "configs/stage3_protocol.FROZEN.yaml"),
        "registry_sha256": evaluator.registry["registry_sha256"], "environment": env,
        "question_counts": {str(k): int(v) for k, v in questions.groupby("part").size().items()},
        "models": args.models, "batch_size": args.batch_size}
    save_json(output / "run_manifest.json", manifest)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("default")
            images, image_report = prepare_images(evaluator, output)
            checkpoints = {name: model_checkpoint(name) for name in args.models}
            save_json(output / "model_manifest.json", {name: m for name, (_, m) in checkpoints.items()})
            if args.prepare_only:
                from transformers import AutoProcessor
                from .model import check_token_ids
                for name, (path, _) in checkpoints.items():
                    processor = AutoProcessor.from_pretrained(path, local_files_only=True, use_fast=False,
                                                              min_pixels=200704, max_pixels=802816)
                    save_json(output / f"tokens_{name}.json", check_token_ids(processor, protocol["templates"]))
            else:
                from .report import write_report
                checks = []
                for name in args.models:
                    if args.evaluate_only:
                        from .analysis import evaluate_model
                        from .report import checks_from_files
                        predictions = {condition: pd.read_parquet(output / f"predictions_{name}_{condition}.parquet")
                                       for condition in ("image", "no_image")}
                        metrics = evaluate_model(evaluator, questions, predictions["image"], predictions["no_image"], name, output)
                        checks.append(checks_from_files(questions, predictions, metrics, name, output))
                    else:
                        checks.append(run_model(name, *checkpoints[name], questions, images, protocol, evaluator, output, args.batch_size))
                checks = pd.concat(checks, ignore_index=True)
                checks.to_csv(output / "checks.csv", index=False)
                write_report(output, args.models, image_report, checks)
            save_json(output / "runtime_warnings.json", sorted(set(str(w.message) for w in caught)))
        if accepted_snapshot() != snapshot:
            raise ValueError("Accepted audit outputs changed during experiment")
        manifest["status"] = "PREPARED" if args.prepare_only else "COMPLETE"
    except KeyboardInterrupt:
        manifest["status"] = "INTERRUPTED"
        manifest["error"] = "Interrupted; completed prediction shards can be resumed"
        raise
    except BaseException as error:
        manifest["status"] = "FAILED"
        manifest["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["accepted_outputs_unchanged"] = accepted_snapshot() == snapshot
        manifest["input_hashes"] = {str(p.relative_to(ROOT)): file_hash(p) for p in (
            ROOT / "gqa_audit/evaluation.py", ROOT / "gqa_audit/outputs/stage2b/run_manifest.json",
            ROOT / "gqa_audit/outputs/stage2/task_registry.json", ROOT / "gqa_audit/outputs/stage2b/analysis_subsets.json",
            ROOT / "gqa_audit/config/analysis_plan.FROZEN.yaml")}
        manifest["input_hashes"].update(snapshot)
        image_report = output / "image_verification.json"
        if image_report.exists():
            manifest["input_hashes"]["data/gqa/images/images.zip"] = json.loads(image_report.read_text())["archive_sha256"]
        manifest["artifacts"] = {str(p.relative_to(output)): file_hash(p) for p in sorted(output.rglob("*"))
            if p.is_file() and p.name not in ("run_manifest.json", "run.log") and not p.name.endswith(".tmp")}
        save_json(output / "run_manifest.json", manifest)
    return 0
