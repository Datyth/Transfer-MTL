"""Exact-sample run identities, GPU budget ledger and atomic checkpoints."""
import gc
import json
import math
import os
import time

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader

from gqa_audit.stage2_core import canonical_hash
from ..probe.model import ProbeModel, parameter_counts
from ..probe.train import _optimizer, _schedule
from ..probe.features import sha256, assert_gpu_exclusive
from .core import OUT, CACHE, MODEL, SPEC, atomic, rng
from .core import TASKS, FAMILIES


class BudgetStop(RuntimeError):
    pass


class Budget:
    def __init__(self, output=OUT, limit=24 * 3600, clock=time.monotonic):
        self.output, self.limit, self.clock = output, limit, clock
        self.path = output / 'budget.json'
        self.previous = json.loads(self.path.read_text())['seconds'] if self.path.exists() else 0.
        self.start = clock()
        self.last_save = 0.
        self.paused_at = None

    @property
    def seconds(self):
        return self.previous + (self.clock() if self.paused_at is None else self.paused_at) - self.start

    def pause(self):
        self.paused_at = self.clock()
        self.save()

    def check(self, reserve=0.):
        if self.seconds + reserve >= self.limit:
            self.save()
            raise BudgetStop('Dừng vì giới hạn 24 giờ GPU hoặc dự toán vượt phần còn lại')

    def save(self):
        atomic(self.path, {'seconds': self.seconds, 'limit_seconds': self.limit})

    def tick(self, state, **fields):
        if self.clock() - self.last_save >= 5:
            self.save()
            atomic(self.output / 'status.json', {'pid': os.getpid(), 'state': state,
                   'updated_unix': time.time(), 'gpu_seconds': self.seconds, **fields})
            self.last_save = self.clock()


class Encoded(Dataset):
    def __init__(self, data, ids, blank=False, labels=None):
        self.ids = list(ids)
        frame = data.by_id.loc[ids]
        if frame.question.isna().any() or not frame.answer.isin(['yes', 'no']).all():
            raise ValueError('Missing text or binary answer')
        index = pd.read_parquet(CACHE / 'index.parquet')
        rows = dict(zip(index.imageId, index.row))
        self.rows = [rows[x] for x in frame.image_id]
        self.image = (np.load(CACHE / 'blank_tokens.npy', mmap_mode='r') if blank else
                      np.memmap(CACHE / 'tokens.float16.memmap', mode='r', dtype='float16',
                                shape=(len(index), 257, 1024)))
        self.blank = blank
        self.enc = data.tokenizer(frame.question.tolist(), padding='max_length',
                                  max_length=data.max_text_tokens, truncation=False, return_tensors='pt')
        if self.enc.input_ids.shape[1] != data.max_text_tokens:
            raise ValueError('Question exceeds validated token length')
        self.y = torch.tensor([float((labels or {}).get(q, a) == 'yes')
                               for q, a in zip(ids, frame.answer)])

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, i):
        return {'image_tokens': torch.from_numpy(np.array(
                    self.image if self.blank else self.image[self.rows[i]], dtype='float32', copy=True)),
                'input_ids': self.enc.input_ids[i], 'attention_mask': self.enc.attention_mask[i],
                'labels': self.y[i]}


def verified(path, config, ids, checkpoint=False):
    try:
        r = json.loads((path / 'run.json').read_text())
        p = pd.read_parquet(path / 'predictions.parquet')
        score = p.score.to_numpy()
        valid = (r['status'] == 'complete' and r['config'] == config
                 and r['predictions_sha256'] == sha256(path / 'predictions.parquet')
                 and len(p) == len(ids) and not p.question_id.duplicated().any()
                 and set(p.question_id) == set(ids) and p.question_id.map(type).eq(str).all()
                 and np.isfinite(score).all() and np.isfinite(p.p_yes).all()
                 and np.allclose(p.p_yes, torch.sigmoid(torch.tensor(score)).numpy(), atol=1e-6)
                 and p.pred.eq(np.where(score > 0, 'yes', 'no')).all())
        if checkpoint:
            valid = valid and r['checkpoint_sha256'] == sha256(path / 'weights.pt')
        return bool(valid)
    except (OSError, ValueError, KeyError, AttributeError):
        return False


def eval_ids(data, job):
    if 'smoke_eval' in job:
        return job['smoke_eval']
    if job['arm'] == 'source':
        names = TASKS if job['level'] == 'group' else FAMILIES
        return sorted({q for t in names for q in data.evaluation(job['level'], t, job['split'])})
    return data.evaluation(job['level'], job['target'], job['split'])


def run(data, job, identity, guard, initial=None, save_checkpoint=False):
    ids, labels = ((job['smoke_ids'], job.get('smoke_labels')) if 'smoke_ids' in job else data.training(job))
    evaluation = eval_ids(data, job)
    if not ids or len(ids) != len(set(ids)) or not evaluation:
        raise ValueError('Empty or duplicated run IDs')
    if not data.by_id.loc[ids, 'part'].eq('train_core').all():
        raise ValueError('Training outside train_core')
    if not data.by_id.loc[evaluation, 'part'].eq(job['split']).all():
        raise ValueError('Evaluation split mismatch')
    config = {'study': identity, 'job': job, 'training_hash': canonical_hash(ids),
              'labels_hash': canonical_hash(labels or {}), 'evaluation_hash': canonical_hash(evaluation),
              'initial_hash': sha256(initial) if initial else None}
    path = OUT / 'runs' / canonical_hash(config)
    if verified(path, config, evaluation, checkpoint=save_checkpoint):
        return path
    assert_gpu_exclusive()
    guard.check()
    run_started = time.monotonic()
    path.mkdir(parents=True, exist_ok=True)
    seed = job['seed']
    torch.manual_seed(int(rng(seed, 3).integers(2**31)))
    torch.cuda.manual_seed_all(int(rng(seed, 3).integers(2**31)))
    model = ProbeModel(MODEL, train_text=False, max_text_tokens=data.max_text_tokens).cuda()
    initial_parameter_hash = None
    if initial:
        weights = torch.load(initial, map_location='cpu', weights_only=True)
        model.load_state_dict(weights, strict=True)
        initial_parameter_hash = canonical_hash({n: list(p.shape) for n, p in weights.items()})
        del weights
    torch.manual_seed(int(rng(seed, 6).integers(2**31)))
    torch.cuda.manual_seed_all(int(rng(seed, 6).integers(2**31)))
    torch.use_deterministic_algorithms(True, warn_only=True)
    # Math SDPA removes the nondeterministic backward kernels observed in P2.
    from torch.nn.attention import sdpa_kernel, SDPBackend
    train = Encoded(data, ids, blank=job['blank'], labels=labels)
    dev = Encoded(data, evaluation, blank=job['blank'])
    generator = torch.Generator().manual_seed(int(rng(seed, 4).integers(2**31)))
    loader = DataLoader(train, batch_size=64, shuffle=True, generator=generator, num_workers=0)
    epochs = job.get('epochs', 10)
    optimizer = _optimizer(model, 1e-4, False)
    schedule = _schedule(optimizer, len(loader) * epochs)
    torch.cuda.reset_peak_memory_stats()
    steps = 0
    started = time.monotonic()
    with sdpa_kernel(SDPBackend.MATH):
        model.train()
        for epoch in range(epochs):
            for batch in loader:
                guard.check()
                batch = {k: v.cuda() for k, v in batch.items()}
                y = batch.pop('labels')
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    scores = model(**batch)
                    loss = nn.functional.binary_cross_entropy_with_logits(scores.float(), y)
                if not torch.isfinite(loss):
                    raise ValueError('Nonfinite training loss')
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.)
                optimizer.step()
                schedule.step()
                steps += 1
                guard.tick(job['phase'], job=job, epoch=epoch + 1, step=steps)
        torch.cuda.synchronize()
        training_seconds = time.monotonic() - started
        started = time.monotonic()
        model.eval()
        scores = []
        with torch.inference_mode():
            for batch in DataLoader(dev, batch_size=64, num_workers=0):
                guard.check()
                batch.pop('labels')
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    scores.extend(model(**{k: v.cuda() for k, v in batch.items()}).float().cpu().tolist())
        torch.cuda.synchronize()
    scores = np.asarray(scores, dtype='float32')
    if not np.isfinite(scores).all():
        raise ValueError('Nonfinite predictions')
    predictions = pd.DataFrame({'question_id': evaluation, 'score': scores,
                                 'p_yes': torch.sigmoid(torch.tensor(scores)).numpy(),
                                 'pred': np.where(scores > 0, 'yes', 'no')})
    predictions.to_parquet(path / 'predictions.tmp.parquet', index=False)
    os.replace(path / 'predictions.tmp.parquet', path / 'predictions.parquet')
    if save_checkpoint:
        torch.save(model.state_dict(), path / 'weights.tmp.pt')
        os.replace(path / 'weights.tmp.pt', path / 'weights.pt')
    atomic(path / 'run.json', {'status': 'complete', 'config': config,
           'training_seconds': training_seconds, 'evaluation_seconds': time.monotonic() - started,
           'wall_seconds': time.monotonic() - run_started,
           'examples_seen': len(ids) * epochs, 'optimizer_steps': steps,
           'peak_gpu_bytes': torch.cuda.max_memory_allocated(), 'parameters': parameter_counts(model),
           'predictions_sha256': sha256(path / 'predictions.parquet'),
           'checkpoint_sha256': sha256(path / 'weights.pt') if save_checkpoint else None,
           'initial_parameter_shapes': initial_parameter_hash,
           'answer_counts': data.by_id.loc[ids, 'answer'].value_counts().to_dict(),
           'changed_labels': sum(labels[q] != data.by_id.at[q, 'answer'] for q in labels) if labels else 0})
    if not verified(path, config, evaluation, save_checkpoint):
        raise ValueError('Run failed its post-write verification')
    del model, optimizer, schedule, loader, train, dev
    gc.collect()
    torch.cuda.empty_cache()
    guard.save()
    return path
