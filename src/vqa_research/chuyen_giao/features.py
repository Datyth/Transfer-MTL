"""Pinned L/14 weights and interruption-safe, separate image feature cache."""
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from transformers import CLIPModel, CLIPTokenizerFast

from ..probe.features import image_ids, image_tensor, sha256, FILL
from .core import ROOT, OUT, CACHE, MODEL, REVISION, atomic


def prepare_model():
    from huggingface_hub import snapshot_download
    MODEL.mkdir(parents=True, exist_ok=True)
    snapshot_download('openai/clip-vit-large-patch14', revision=REVISION,
                      local_dir=MODEL, allow_patterns=['config.json', 'pytorch_model.bin',
                          'merges.txt', 'vocab.json', 'tokenizer*.json',
                          'special_tokens_map.json', 'preprocessor_config.json'])
    files = {p.name: sha256(p) for p in MODEL.iterdir() if p.is_file()}
    atomic(OUT / 'model.json', {'revision': REVISION, 'files': files})


def tokenizer_check(data):
    data.tokenizer = CLIPTokenizerFast.from_pretrained(MODEL, local_files_only=True)
    # Training, development and verification only. Never inspect testdev.
    required = set(data.placebo)
    for pool in data._pools.values():
        required.update(pool)
    texts = data.by_id.loc[sorted(required), 'question'].tolist()
    if any(not isinstance(t, str) for t in texts):
        raise ValueError('Required question text is missing')
    longest = 0
    for start in range(0, len(texts), 4096):
        encoded = data.tokenizer(texts[start:start + 4096], truncation=False)['input_ids']
        longest = max(longest, max(map(len, encoded), default=0))
    rounded = ((longest + 7) // 8) * 8
    if longest > 77 or rounded > 77:
        raise ValueError(f'Token length unsupported: {longest} -> {rounded}')
    # Keep 32 only if it actually covers every question.
    data.max_text_tokens = max(8, rounded)
    atomic(OUT / 'text_length.json', {'maximum': longest, 'padded': data.max_text_tokens})


def encode(model, ids):
    tensors = []
    for ident in ids:
        with Image.open(ROOT / f'data/gqa/images/images/{ident}.jpg') as img:
            tensors.append(image_tensor(img))
    with torch.inference_mode():
        result = model.vision_model(pixel_values=torch.stack(tensors).cuda(),
                                    output_hidden_states=True).hidden_states[-2]
    if result.shape[1:] != (257, 1024):
        raise ValueError('Wrong L/14 image dimensions')
    return result.half().cpu().numpy()


def cpu_smoke():
    """Check actual downloaded L/14 weights and fusion without claiming a GPU test."""
    import gc
    from ..probe.model import ProbeModel
    torch.set_num_threads(4)
    tokenizer = CLIPTokenizerFast.from_pretrained(MODEL, local_files_only=True)
    text = tokenizer(['Is there a red car?'], padding='max_length', max_length=32,
                     truncation=False, return_tensors='pt')
    model = CLIPModel.from_pretrained(MODEL, local_files_only=True, use_safetensors=False).eval()
    ident = image_ids()[0]
    with Image.open(ROOT / f'data/gqa/images/images/{ident}.jpg') as img:
        pixels = image_tensor(img).unsqueeze(0)
    with torch.inference_mode():
        image = model.vision_model(pixel_values=pixels, output_hidden_states=True).hidden_states[-2].clone()
    if tuple(image.shape) != (1, 257, 1024):
        raise ValueError('Actual L/14 image model differs from configuration')
    del model
    gc.collect()
    probe = ProbeModel(MODEL, train_text=False, max_text_tokens=32).eval()
    with torch.inference_mode():
        scores = probe(image_tokens=image, input_ids=text.input_ids, attention_mask=text.attention_mask)
    if scores.shape != (1,) or not torch.isfinite(scores).all():
        raise ValueError('Actual L/14 fusion CPU check failed')
    result = {'status': 'PASS', 'device': 'cpu', 'revision': REVISION,
              'image_shape': list(image.shape), 'text_width': probe.text_projection.in_features,
              'output_shape': list(scores.shape)}
    atomic(OUT / 'cpu_smoke.json', result)
    return result


def cache_identity(ids, batch_size):
    return {'revision': REVISION, 'ids_hash': __import__('hashlib').sha256(
        '\n'.join(ids).encode()).hexdigest(), 'batch_size': batch_size,
        'weights_hash': sha256(MODEL / 'pytorch_model.bin'),
        'preprocessing_code_hash': sha256(ROOT / 'src/vqa_research/probe/features.py'),
        'encoder_code_hash': sha256(Path(__file__))}


def build_cache(guard, batch_size=16):
    CACHE.mkdir(parents=True, exist_ok=True)
    ids = image_ids()
    manifest = CACHE / 'manifest.json'
    tokens = CACHE / 'tokens.float16.memmap'
    index = CACHE / 'index.parquet'
    identity = cache_identity(ids, batch_size)
    if manifest.exists():
        m = json.loads(manifest.read_text())
        if (m['revision'] != REVISION or m['shape'] != [len(ids), 257, 1024]
                or m.get('identity') != identity
                or any(sha256(CACHE / name) != digest for name, digest in m['files'].items())):
            raise ValueError('L/14 cache checksum mismatch')
        return m
    progress = CACHE / 'progress.json'
    start = 0
    if progress.exists():
        p = json.loads(progress.read_text())
        if p['identity'] != identity or not tokens.exists() or not index.exists():
            raise ValueError('Cache progress differs from current inputs')
        start = p['next_row']
        ix = pd.read_parquet(index)
        if ix.imageId.tolist() != ids or ix.row.tolist() != list(range(len(ids))):
            raise ValueError('Cache index changed')
    else:
        if tokens.exists():
            raise ValueError('Cache file without valid progress')
        pd.DataFrame({'imageId': ids, 'row': range(len(ids))}).to_parquet(index, index=False)
        atomic(progress, {'identity': identity, 'next_row': 0})
    mmap = np.memmap(tokens, dtype='float16', mode='r+' if tokens.exists() else 'w+',
                     shape=(len(ids), 257, 1024))
    model = CLIPModel.from_pretrained(MODEL, local_files_only=True,
                                      use_safetensors=False).eval().cuda()
    start_time = time.monotonic()
    for row in range(start, len(ids), batch_size):
        guard.check()
        mmap[row:row + min(batch_size, len(ids) - row)] = encode(model, ids[row:row + batch_size])
        mmap.flush()
        atomic(progress, {'identity': identity, 'next_row': min(row + batch_size, len(ids))})
        guard.tick('features', completed=min(row + batch_size, len(ids)), total=len(ids))
    chosen = np.random.default_rng(1000).choice(len(ids), 64, replace=False)
    difference = 0.
    for row in sorted({int(i) // batch_size * batch_size for i in chosen}):
        fresh = encode(model, ids[row:row + batch_size])
        for i in chosen[(chosen >= row) & (chosen < row + len(fresh))]:
            difference = max(difference, float(np.max(np.abs(
                fresh[int(i) - row].astype('float32') - mmap[i].astype('float32')))))
    if difference > .02:
        raise ValueError(f'Cache validation difference {difference} > 0.02')
    with torch.inference_mode():
        blank = model.vision_model(pixel_values=image_tensor(
            Image.new('RGB', (224, 224), FILL)).unsqueeze(0).cuda(),
            output_hidden_states=True).hidden_states[-2].half().cpu().numpy()[0]
    np.save(CACHE / 'blank_tokens.npy', blank)
    del model, mmap
    torch.cuda.empty_cache()
    m = {'revision': REVISION, 'identity': identity, 'shape': [len(ids), 257, 1024], 'dtype': 'float16',
         'validation_max_abs_difference': difference, 'validation_images': 64,
         'batch_size': batch_size, 'seconds_this_session': time.monotonic() - start_time,
         'files': {p.name: sha256(p) for p in (tokens, index, CACHE / 'blank_tokens.npy')}}
    atomic(manifest, m)
    return m
