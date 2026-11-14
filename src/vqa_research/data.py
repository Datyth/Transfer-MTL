"""Read accepted inputs, verify images, and freeze reproducible samples."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from PIL import Image
import yaml

from gqa_audit.evaluation import Evaluator

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_SHA256 = "a0201c1a0a163d81d102f8f1aca677812238c7328305d69774d7101e4ada7ab2"


def file_hash(path):
    digest = sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(16 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temporary.replace(path)


def load_protocol(path):
    if file_hash(path) != PROTOCOL_SHA256:
        raise ValueError("Frozen protocol changed; STOP")
    protocol = yaml.safe_load(Path(path).read_text())
    evaluator = Evaluator(ROOT)
    if protocol["applies_to"]["registry_sha256"] != evaluator.registry["registry_sha256"]:
        raise ValueError("Protocol references a different registry")
    return protocol, evaluator


def accepted_snapshot():
    return {str(p.relative_to(ROOT)): file_hash(p)
            for name in ("stage1", "stage2", "stage2b")
            for p in sorted((ROOT / "gqa_audit/outputs" / name).rglob("*"))
            if p.is_file()}


def load_questions(evaluator):
    """Membership comes exclusively from the accepted evaluator, never raw types."""
    frame = evaluator.metadata[evaluator.metadata.part.isin(["dev", "val"])].copy()
    expected = {qid for tasks in evaluator.registry["variants"].values()
                for parts in tasks.values() for part in ("dev", "val") for qid in parts[part]}
    if set(frame.question_id) != expected or frame.question_id.duplicated().any():
        raise ValueError("Frozen question union mismatch")
    manifest = json.loads((ROOT / "gqa_audit/outputs/stage2b/run_manifest.json").read_text())
    texts = []
    for split in ("train", "val"):
        relative = f"gqa_audit/outputs/stage2/cache/questions_{split}.parquet"
        if file_hash(ROOT / relative) != manifest["input_hashes"][relative]:
            raise ValueError(f"Question cache hash mismatch: {split}")
        data = pq.read_table(ROOT / relative, columns=["question_id", "question"]).to_pandas()
        texts.append(data[data.question_id.isin(expected)])
    frame = frame.merge(pd.concat(texts), on="question_id", validate="one_to_one")
    if set(frame.question_id) != expected or frame.question.isna().any():
        raise ValueError("Missing question text")
    if frame.groupby("part").size().to_dict() != {"dev": 29509, "val": 41825}:
        raise ValueError("Unexpected dev/val union counts")
    return frame.sort_values(["part", "question_id"]).reset_index(drop=True)


def stratified_sample(frame, per_task):
    rng = np.random.default_rng(0)
    return pd.concat([group.sort_values("question_id").iloc[
        rng.choice(len(group), per_task, replace=False)]
        for _, group in frame[frame.part.eq("dev")].groupby("task", sort=True)]
    ).sort_values("question_id").reset_index(drop=True)


def prepare_images(evaluator, output, workers=8):
    """Verify archive once, then every train/dev/val image; testdev counts only."""
    output = Path(output)
    archive = ROOT / "data/gqa/images/images.zip"
    report_path = output / "image_verification.json"
    archive_hash = file_hash(archive)
    previous = json.loads(report_path.read_text()) if report_path.exists() else {}
    if previous.get("archive_sha256") != archive_hash or not previous.get("archive_crc_verified"):
        print("Verifying image archive CRC ...", flush=True)
        with zipfile.ZipFile(archive) as bundle:
            bad = bundle.testzip()
            if bad is not None:
                raise ValueError(f"Corrupt archive member: {bad}")
            archive_images = sum(not i.is_dir() and Path(i.filename).suffix.lower() in {".jpg", ".jpeg", ".png"}
                                 for i in bundle.infolist())
        save_json(report_path, {"archive_sha256": archive_hash, "archive_crc_verified": True,
                                "archive_image_count": archive_images, "archive_size_bytes": archive.stat().st_size})
    else:
        archive_images = previous["archive_image_count"]
    paths = {}
    for path in (ROOT / "data/gqa/images/images").rglob("*"):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            paths.setdefault(path.stem, []).append(path)
    meta = evaluator.metadata
    required = meta[meta.part.isin(["train_core", "dev", "val"])]
    if required.imageId.isna().any():
        raise ValueError("Required image ID is missing in accepted metadata")
    parts = required.groupby("imageId").part.agg(lambda x: ";".join(sorted(set(x)))).to_dict()
    invalid = {key: len(paths.get(key, [])) for key in parts if len(paths.get(key, [])) != 1}
    if invalid:
        save_json(output / "image_coverage_errors.json", invalid)
        raise ValueError(f"STOP: {len(invalid)} registry images missing or duplicated")

    def verify(item):
        image_id, part = item
        path = paths[image_id][0]
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            width, height = image.size
        return {"imageId": image_id, "relative_path": str(path.relative_to(ROOT)), "width": width,
                "height": height, "bytes": path.stat().st_size, "part_set": part, "sha256": file_hash(path)}

    print(f"Verifying {len(parts):,} required image files ...", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(verify, sorted(parts.items())))
    images = pd.DataFrame(records)
    images.to_csv(output / "image_manifest.csv", index=False)
    # Only image IDs are read from sealed testdev; no questions or answers.
    relative = "gqa_audit/outputs/stage2/cache/questions_testdev.parquet"
    manifest = json.loads((ROOT / "gqa_audit/outputs/stage2b/run_manifest.json").read_text())
    if file_hash(ROOT / relative) != manifest["input_hashes"][relative]:
        raise ValueError("Sealed image-ID cache hash mismatch")
    sealed = pq.read_table(ROOT / relative, columns=["question_id", "image_id"]).to_pandas()
    ids = set(meta.loc[meta.part.eq("testdev"), "question_id"])
    sealed_ids = set(sealed.loc[sealed.question_id.isin(ids), "image_id"])
    report = {"archive_sha256": archive_hash, "archive_crc_verified": True,
              "archive_size_bytes": archive.stat().st_size, "archive_image_count": archive_images,
              "extracted_image_count": sum(len(x) for x in paths.values()), "required_images_verified": len(images),
              "testdev_registry_images": len(sealed_ids),
              "testdev_images_with_file": sum(bool(paths.get(x)) for x in sealed_ids),
              "testdev_policy": "image existence counts only",
              "distribution": images[["width", "height", "bytes"]].describe().to_dict()}
    save_json(report_path, report)
    return images, report


def validate_predictions(predictions, expected):
    if predictions.question_id.map(type).ne(str).any() or predictions.question_id.duplicated().any():
        raise ValueError("Prediction IDs must be unique strings")
    if predictions.question_id.tolist() != list(expected):
        raise ValueError("Prediction shard question IDs or ordering differ")
    if not predictions.part.isin(["dev", "val"]).all():
        raise ValueError("Only dev and val can be scored; testdev is sealed")
    if not predictions.pred.isin(["yes", "no"]).all() or not np.isfinite(predictions.score).all():
        raise ValueError("Invalid predictions/scores")
    if not np.array_equal(predictions.pred.to_numpy(), np.where(predictions.score > 0, "yes", "no")):
        raise ValueError("Predictions must use the frozen threshold 0")
    if not np.allclose(predictions.p_yes, 1 / (1 + np.exp(-predictions.score)), atol=1e-7):
        raise ValueError("Invalid yes probabilities")
