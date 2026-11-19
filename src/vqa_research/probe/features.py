"""Resumable, pinned CLIP image-token cache for Stage 3.5."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import torch
from PIL import Image
from transformers import CLIPModel

from gqa_audit.evaluation import load_registry


ROOT = Path(__file__).resolve().parents[3]
COMMIT = "57c216476eefef5ab752ec549e440a49ae4ae5f3"
EXPECTED = 82374
FILL = (122, 116, 104)
MEAN = np.asarray((0.48145466, 0.4578275, 0.40821073), dtype=np.float32)
STD = np.asarray((0.26862954, 0.26130258, 0.27577711), dtype=np.float32)


def pad_and_resize(image: Image.Image) -> Image.Image:
    """Retain the entire image, including pixels along its shorter axis."""
    image = image.convert("RGB")
    width, height = image.size
    side = max(width, height)
    canvas = Image.new("RGB", (side, side), FILL)
    canvas.paste(image, ((side - width) // 2, (side - height) // 2))
    return canvas.resize((224, 224), Image.Resampling.BICUBIC)


def image_tensor(image: Image.Image) -> torch.Tensor:
    pixels = np.asarray(pad_and_resize(image), dtype=np.float32) / 255.0
    return torch.from_numpy(((pixels - MEAN) / STD).transpose(2, 0, 1).copy())


def image_ids(root: Path = ROOT) -> list[str]:
    cache = root / "gqa_audit/outputs/stage2/cache"
    train = pq.read_table(cache / "questions_train.parquet", columns=["image_id"]).column(0).to_pylist()
    val = pq.read_table(cache / "questions_val.parquet", columns=["image_id"]).column(0).to_pylist()
    ids = sorted(set(train) | set(val))
    if len(ids) != EXPECTED:
        raise ValueError(f"Image count {len(ids)} != {EXPECTED}")
    registry = load_registry(root / "gqa_audit/outputs/stage2/task_registry.json")
    required = {qid for task in registry["variants"]["program_strict"].values()
                for part in ("train_core", "dev", "val") for qid in task[part]}
    metadata = pq.read_table(root / "gqa_audit/outputs/stage2b/registry_questions.parquet",
                             columns=["question_id", "imageId"]).to_pandas()
    covered = set(metadata.loc[metadata.question_id.isin(required), "imageId"])
    if not covered <= set(ids):
        raise ValueError("Registry image is missing from CLIP cache index")
    return ids


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class GPUOccupiedError(RuntimeError):
    """Another compute process owns the pilot GPU."""

    def __init__(self, pids: list[str]):
        self.pids = pids
        super().__init__(f"GPU is occupied by other compute process(es): {', '.join(pids)}")


def assert_gpu_exclusive() -> None:
    """Refuse to start a pilot GPU phase while another compute process exists."""
    result = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, check=True)
    others = [line.strip() for line in result.stdout.splitlines()
              if line.strip() and line.strip() != str(os.getpid())]
    if others:
        raise GPUOccupiedError(others)


def _atomic_json(path: Path, content: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _encode(model: CLIPModel, images: list[Image.Image], device: str) -> np.ndarray:
    inputs = torch.stack([image_tensor(image) for image in images]).to(device)
    with torch.no_grad():
        result = model.vision_model(pixel_values=inputs, output_hidden_states=True)
    tokens = result.hidden_states[-2]
    if tokens.shape[1:] != (197, 768):
        raise ValueError(f"Unexpected CLIP token shape: {tuple(tokens.shape)}")
    return tokens.to(torch.float16).cpu().numpy()


def build_cache(root: Path = ROOT, batch_size: int = 32) -> dict:
    assert_gpu_exclusive()
    root = Path(root)
    ids = image_ids(root)
    output = root / "data/features/clip_vitb16_224"
    output.mkdir(parents=True, exist_ok=True)
    progress_path = output / "progress.json"
    manifest_path = output / "manifest.json"
    index_path = output / "index.parquet"
    token_path = output / "tokens.float16.memmap"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if (manifest.get("count") == EXPECTED and manifest.get("commit") == COMMIT and
                manifest.get("tokens_sha256") == sha256(token_path)):
            return manifest
        raise ValueError("Existing feature manifest is invalid")
    if index_path.exists():
        index = pq.read_table(index_path).to_pandas()
        if index.imageId.tolist() != ids or index.row.tolist() != list(range(len(ids))):
            raise ValueError("Existing feature index does not match frozen input")
    else:
        pd.DataFrame({"imageId": ids, "row": np.arange(len(ids), dtype=np.int32)}).to_parquet(index_path, index=False)
    if progress_path.exists():
        progress = json.loads(progress_path.read_text())
        if progress.get("commit") != COMMIT or progress.get("count") != len(ids):
            raise ValueError("Feature progress belongs to another input")
        start = progress["next_row"]
    else:
        if token_path.exists():
            raise ValueError("Feature file exists without progress metadata")
        start = 0
        _atomic_json(progress_path, {"commit": COMMIT, "count": len(ids), "next_row": 0})
    mode = "r+" if token_path.exists() else "w+"
    cache = np.memmap(token_path, dtype=np.float16, mode=mode, shape=(len(ids), 197, 768))
    model = CLIPModel.from_pretrained(root / "checkpoints/clip-vit-base-patch16", local_files_only=True,
                                      use_safetensors=False).eval().to("cuda")
    images_dir = root / "data/gqa/images/images"
    for row in range(start, len(ids), batch_size):
        batch = ids[row:row + batch_size]
        images = []
        for image_id in batch:
            path = images_dir / f"{image_id}.jpg"
            if not path.is_file():
                raise FileNotFoundError(path)
            with Image.open(path) as image:
                images.append(image.copy())
        cache[row:row + len(batch)] = _encode(model, images, "cuda")
        cache.flush()
        _atomic_json(progress_path, {"commit": COMMIT, "count": len(ids), "next_row": row + len(batch)})
    blank = Image.new("RGB", (224, 224), FILL)
    np.save(output / "blank_tokens.npy", _encode(model, [blank], "cuda")[0])
    rng = np.random.default_rng(np.random.SeedSequence([1000, 7]))
    chosen = rng.choice(len(ids), size=64, replace=False)
    max_diff = 0.0
    # Reproduce the original batch shape: CUDA's convolution kernels can give
    # different fp16-rounded tokens for a batch of one versus a batch of 32.
    # The seeded 64 images remain independently re-encoded from source JPEGs.
    for start_row in sorted({int(row) // batch_size * batch_size for row in chosen}):
        images = []
        for image_id in ids[start_row:start_row + batch_size]:
            with Image.open(images_dir / f"{image_id}.jpg") as image:
                images.append(image.copy())
        fresh_batch = _encode(model, images, "cuda")
        for row in chosen[(chosen >= start_row) & (chosen < start_row + len(images))]:
            fresh = fresh_batch[int(row) - start_row]
            max_diff = max(max_diff, float(np.max(np.abs(fresh.astype(np.float32) - cache[int(row)].astype(np.float32)))))
    if max_diff > 0.02:
        raise ValueError(f"Feature validation maximum difference {max_diff} > 0.02")
    manifest = {"model_id": "openai/clip-vit-base-patch16", "commit": COMMIT,
                "preprocess": "RGB; centred square pad fill (122,116,104); bicubic 224; CLIP mean/std; no crop",
                "layer": "vision_model.hidden_states[-2]", "shape": [len(ids), 197, 768],
                "dtype": "float16", "count": len(ids), "validation_images": 64,
                "validation_max_abs_difference": max_diff, "validation_batch_size": batch_size,
                "tokens_sha256": sha256(token_path),
                "index_sha256": sha256(index_path), "blank_sha256": sha256(output / "blank_tokens.npy")}
    _atomic_json(manifest_path, manifest)
    return manifest
