"""Resumable, validated prediction shards. No scoring on testdev."""

import json
from pathlib import Path
import time

import pandas as pd

from .data import file_hash, save_json, validate_predictions


def run_predictions(model, questions, image_lookup, template, condition, destination,
                    fingerprint, batch_size=8, shard_size=2000):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if questions.part.eq("testdev").any() or not questions.part.isin(["dev", "val"]).all():
        raise ValueError("testdev is sealed; only dev/val predictions are allowed")
    if questions.question_id.map(type).ne(str).any() or questions.question_id.duplicated().any():
        raise ValueError("Question IDs must be unique strings")
    spec = {"fingerprint": fingerprint, "template": template, "condition": condition,
            "batch_size": batch_size, "shard_size": shard_size, "question_ids": questions.question_id.tolist()}
    spec_path = destination / "spec.json"
    if spec_path.exists():
        if json.loads(spec_path.read_text()) != spec:
            raise ValueError(f"Cannot resume a different run: {destination}")
    else:
        if list(destination.glob("*.parquet")):
            raise ValueError("Shards without a run specification")
        save_json(spec_path, spec)
    frames = []
    expected_files = set()
    for start in range(0, len(questions), shard_size):
        subset = questions.iloc[start:start + shard_size]
        path = destination / f"{start // shard_size:05d}.parquet"
        expected_files.add(path.name)
        hash_path = path.with_suffix(".json")
        if path.exists() and hash_path.exists():
            if json.loads(hash_path.read_text())["sha256"] != file_hash(path):
                raise ValueError(f"Shard hash mismatch: {path}")
            predictions = pd.read_parquet(path)
        else:
            rows = []
            before = time.perf_counter()
            for offset in range(0, len(subset), batch_size):
                batch = subset.iloc[offset:offset + batch_size]
                images = [image_lookup[x] for x in batch.imageId] if condition == "image" else None
                scores = model.score(batch.question.tolist(), images, template)
                rows.append(pd.DataFrame({"question_id": batch.question_id.tolist(), "part": batch.part.tolist(), **scores}))
            predictions = pd.concat(rows, ignore_index=True)
            validate_predictions(predictions, subset.question_id)
            temporary = path.with_suffix(".parquet.tmp")
            predictions.to_parquet(temporary, index=False)
            temporary.replace(path)
            save_json(hash_path, {"sha256": file_hash(path), "n": len(predictions)})
            rate = len(subset) / (time.perf_counter() - before)
            print(f"{destination.name}: {start + len(subset):,}/{len(questions):,}; {rate:.2f} questions/s", flush=True)
        validate_predictions(predictions, subset.question_id)
        if predictions.part.tolist() != subset.part.tolist():
            raise ValueError("Shard part labels differ from frozen metadata")
        if condition == "image" and not predictions.n_image_tokens.gt(0).all():
            raise ValueError("Missing image tokens")
        if condition == "no_image" and not predictions.n_image_tokens.eq(0).all():
            raise ValueError("Unexpected image tokens in no-image condition")
        frames.append(predictions)
    if {p.name for p in destination.glob("*.parquet")} != expected_files:
        raise ValueError("Unexpected leftover prediction shards")
    result = pd.concat(frames, ignore_index=True)
    validate_predictions(result, questions.question_id)
    return result
