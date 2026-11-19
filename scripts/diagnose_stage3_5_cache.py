"""Read-only diagnosis of CLIP cache validation failures."""

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.vqa_research.probe.features import ROOT, EXPECTED, _encode, image_ids


ids = image_ids()
rows = np.random.default_rng(np.random.SeedSequence([1000, 7])).choice(len(ids), 64, replace=False)
cache = np.memmap(ROOT / "data/features/clip_vitb16_224/tokens.float16.memmap", dtype=np.float16,
                  mode="r", shape=(EXPECTED, 197, 768))
model = CLIPModel.from_pretrained(ROOT / "checkpoints/clip-vit-base-patch16", local_files_only=True,
                                  use_safetensors=False).eval().to("cuda")
directory = ROOT / "data/gqa/images/images"
print("tf32", torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
last_base, same_batch_tokens = None, None
max_batch, max_single = 0.0, 0.0
for row in sorted(rows):
    row = int(row)
    base = row // 32 * 32
    if base != last_base:
        images = []
        for i in range(base, min(base + 32, len(ids))):
            with Image.open(directory / f"{ids[i]}.jpg") as image:
                images.append(image.copy())
        same_batch_tokens = _encode(model, images, "cuda")
        last_base = base
    same_batch = same_batch_tokens[row - base].astype(np.float32)
    single = _encode(model, [images[row - base]], "cuda")[0].astype(np.float32)
    cached = cache[row].astype(np.float32)
    batch_diff = float(np.max(np.abs(same_batch - cached)))
    single_diff = float(np.max(np.abs(single - cached)))
    max_batch = max(max_batch, batch_diff)
    max_single = max(max_single, single_diff)
    if single_diff > 0.02 or batch_diff > 0.02:
        print(row, "same_batch", batch_diff, "single", single_diff, flush=True)
print("max_batch", max_batch, "max_single", max_single)
