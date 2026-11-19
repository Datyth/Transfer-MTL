"""Immutable inputs, paired sampling and exhaustive execution plans."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from gqa_audit.stage2_core import canonical_hash
from gqa_audit.evaluation import load_registry, load_subsets
from ..probe.features import ROOT, sha256
from ..probe.data import TASKS, PLACEBO_TYPES

OUT = ROOT / "gqa_audit/outputs/chuyen_giao_clip_l14"
REPORT_OUT = ROOT / "gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14"
CACHE = ROOT / "data/features/clip_vitl14_224"
MODEL = ROOT / "checkpoints/clip-vit-large-patch14"
REVISION = "32bd64288804d66eefd0ccbe215aa642df71cc41"
FAMILIES = ('relVerify', 'existOr', 'verifyAttrs', 'existAnd', 'existAttrOr',
            'verifyAttr', 'verifyAttrK', 'exist', 'twoSame', 'twoDifferent',
            'existThatOr', 'existAttrNot', 'existThat', 'existAttr')
NAMES = dict(zip(TASKS, ('Tồn tại', 'Thuộc tính', 'Quan hệ', 'So sánh', 'Suy luận logic')))
SPEC = dict(version=1, model="openai/clip-vit-large-patch14", revision=REVISION,
            image_shape=[257, 1024], epochs=10, lr=1e-4, batch_size=64,
            train_text=False, fusion_layers=4, fusion_width=512, attention='sdpa_math',
            budgets=[250, 1000, 4000], group_seeds=list(range(5)),
            family_seeds=list(range(3)), family_budget=500, family_source=2000,
            source=10000, bootstrap=2000, gpu_hours=24, qwen=False,
            gate_seeds=list(range(1000, 1005)),
            primary_edges=[['exist', 'logic'], ['verifyAttr', 'logic'],
                           ['verifyRel', 'logic'], ['verifyAttr', 'compare'],
                           ['exist', 'verifyRel']])

REPORT_SPEC = {**SPEC, 'mode': 'exploratory_report', 'budgets': [1000],
               'group_seeds': [1000, 1001, 1002], 'family_seeds': [],
               'evaluation': 'dev', 'quality_gates': 'waived_by_user',
               'primary_metric': 'primary', 'minimum_effect': .01, 'primary_edges': []}


def atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    os.replace(tmp, path)


def rng(seed, component):
    if seed not in {*range(5), *range(1000, 1005)}:
        raise ValueError('Unregistered initialization')
    return np.random.default_rng(np.random.SeedSequence([seed, component]))


class StudyData:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.registry = load_registry(self.root / 'gqa_audit/outputs/stage2/task_registry.json')
        self.subsets = load_subsets(self.root / 'gqa_audit/outputs/stage2b/analysis_subsets.json')['subsets']
        self.membership = self.registry['variants']['program_strict']
        metadata = pq.read_table(self.root / 'gqa_audit/outputs/stage2b/registry_questions.parquet').to_pandas()
        columns = ['question_id', 'image_id', 'question', 'answer', 'detailed']
        cache = self.root / 'gqa_audit/outputs/stage2/cache'
        train = pq.read_table(cache / 'questions_train.parquet', columns=columns).to_pandas()
        dev_images = set(json.loads((self.root / 'gqa_audit/outputs/stage2/dev_images.json').read_text())['image_ids'])
        train['part'] = np.where(train.image_id.isin(dev_images), 'dev', 'train_core')
        val = pq.read_table(cache / 'questions_val.parquet', columns=columns).to_pandas()
        val['part'] = 'val'
        self.frame = pd.concat([train, val], ignore_index=True).merge(
            metadata[['question_id', 'part', 'task', 'family', 'in_program_strict']],
            on=['question_id', 'part'], how='left', validate='one_to_one')
        missing = self.frame.question.isna() & self.frame.detailed.isin(PLACEBO_TYPES) & self.frame.part.eq('train_core')
        if missing.any():
            from gqa_audit.stage1 import iter_records
            wanted = set(self.frame.loc[missing, 'question_id'])
            texts = {q: x['question'] for q, x in iter_records(
                self.root / 'data/gqa/questions/train_balanced_questions.json') if q in wanted}
            self.frame.loc[missing, 'question'] = self.frame.loc[missing, 'question_id'].map(texts)
        self.by_id = self.frame.set_index('question_id', drop=False)
        strict = self.frame[self.frame.in_program_strict.fillna(False).astype(bool)]
        eligible = strict[strict.part.eq('train_core')].family.value_counts()
        if set(eligible[eligible >= 2500].index) != set(FAMILIES):
            raise ValueError('Frozen list of 14 families no longer matches eligible pools')
        self.placebo = self.frame.loc[self.frame.part.eq('train_core') &
                                      self.frame.detailed.isin(PLACEBO_TYPES), 'question_id'].tolist()
        if len(self.placebo) != 5371:
            raise ValueError('Placebo pool changed')
        self._pools = {}
        for level, names in [('group', TASKS), ('family', FAMILIES)]:
            for name in names:
                for part in ('train_core', 'dev', 'val'):
                    ids = (list(self.membership[name][part]) if level == 'group' else
                           strict.loc[strict.family.eq(name) & strict.part.eq(part), 'question_id'].tolist())
                    self._pools[level, name, part] = ids
        self.tokenizer = None
        self.max_text_tokens = 32

    def pool(self, level, name, part):
        return self._pools[level, name, part]

    def target(self, level, target, budget, seed):
        pool = self.pool(level, target, 'train_core')
        if budget == 'full':
            return pool.copy()
        if len(pool) < budget:
            raise ValueError('Insufficient target pool')
        return [pool[i] for i in rng(seed, 1).permutation(len(pool))[:budget]]

    def source(self, job):
        level, source, target, seed = (job[k] for k in ('level', 'source', 'target', 'seed'))
        size = 10000 if level == 'group' else 2000
        labels = None
        if source == 'self':
            pool = self.pool(level, target, 'train_core')
            offset = 4000 if level == 'group' else 500
            ids = [pool[i] for i in rng(seed, 1).permutation(len(pool))[offset:offset + size]]
        elif source == 'placebo':
            indices = rng(seed, 2).permutation(len(self.placebo))
            ids = [self.placebo[i] for i in indices[:(5371 if level == 'group' else size)]]
        else:
            name = source.removeprefix('shuffled:')
            pool = self.pool(level, name, 'train_core')
            if job.get('disjoint'):
                blocked = set(self.by_id.loc[self.target(level, target, job['budget'], seed), 'image_id'])
                pool = [q for q in pool if self.by_id.at[q, 'image_id'] not in blocked]
            if len(pool) < size:
                raise ValueError(f'Insufficient disjoint source pool: {level} {source} -> {target}: {len(pool)} < {size}')
            ids = [pool[i] for i in rng(seed, 2).permutation(len(pool))[:size]]
            if source.startswith('shuffled:'):
                answers = self.by_id.loc[ids, 'answer'].to_numpy()
                labels = dict(zip(ids, answers[rng(seed, 5).permutation(len(ids))]))
        if len(ids) != (5371 if source == 'placebo' and level == 'group' else size):
            raise ValueError('Incorrect source size')
        return ids, labels

    def evaluation(self, level, target, part, subset=None):
        ids = self.pool(level, target, part)
        if level == 'group' and target == 'verifyRel':
            ids = self.subsets['verifyRel_relation']['program_strict']['verifyRel'][part]
        if subset:
            blocks = self.subsets[subset]['program_strict']
            allowed = {q for parts in blocks.values() for q in parts.get(part, [])}
            ids = [q for q in ids if q in allowed]
        return ids

    def training(self, job):
        if job['arm'] == 'source':
            return self.source(job)
        ids = self.target(job['level'], job['target'], job['budget'], job['seed'])
        labels = None
        if job['arm'] != 'B':
            source, labels = self.source(job)
            if set(source) & set(ids):
                raise ValueError('Source and target IDs overlap')
            if job['arm'] == 'source':
                ids = source
            elif job['arm'] == 'Joint':
                ids = source + ids
        return ids, labels


def plan():
    jobs, sources = [], {}
    for level, names, budgets, seeds in [('group', TASKS, (250, 1000, 4000), range(5)),
                                          ('family', FAMILIES, (500,), range(3))]:
        for target in names:
            for budget in budgets:
                for seed in seeds:
                    conditions = [(False, False)]
                    if level == 'group' and budget == 1000:
                        conditions += [(True, False), (False, True)]
                    for blank, disjoint in conditions:
                        base = dict(level=level, target=target, budget=budget, seed=seed,
                                    blank=blank, disjoint=disjoint, split='val', phase='matrix')
                        if not disjoint:
                            jobs.append({**base, 'arm': 'B', 'source': ''})
                        real = [s for s in names if s != target]
                        controls = [] if disjoint else ['self', 'placebo', shuffled_control(level, target)]
                        for source in real + controls:
                            for arm in ('Seq', 'Joint'):
                                job = {**base, 'arm': arm, 'source': source}
                                source_job = source_config(job)
                                sources[canonical_hash(source_job)] = source_job
                                jobs.append(job)
    return list(sources.values()), jobs


def shuffled_control(level, target):
    names = TASKS if level == 'group' else FAMILIES
    # Keep the pilot's named controls for its three targets. Otherwise the first
    # other member of the frozen order is used, never selected by its results.
    name = ({'logic': 'exist', 'verifyRel': 'exist', 'compare': 'verifyAttr'}.get(target)
            if level == 'group' else None)
    return 'shuffled:' + (name or next(n for n in names if n != target))


def source_config(job):
    # Shared only when source sample and labels are actually target independent.
    shared = job['source'] not in ('self',) and not job.get('disjoint')
    return {**job, 'target': '*' if shared else job['target'], 'arm': 'source',
            'budget': 1000 if job['level'] == 'group' else 500}


def report_plan():
    """A declared exploratory study, not the validity-gated main matrix."""
    sources, jobs = {}, []
    for target in TASKS:
        real = [s for s in TASKS if s != target]
        for seed in range(1000, 1003):
            base = dict(level='group', target=target, budget=1000, seed=seed,
                        blank=False, disjoint=False, split='dev', phase='report')
            jobs.append({**base, 'arm': 'B', 'source': ''})
            for source in [*real, 'self', 'placebo', shuffled_control('group', target)]:
                for arm in ('Seq', 'Joint'):
                    job = {**base, 'source': source, 'arm': arm}
                    sj = source_config(job)
                    sources[canonical_hash(sj)] = sj
                    jobs.append(job)
    return list(sources.values()), jobs


def gate_plan():
    return [dict(level='group', target=t, budget=b, seed=s, blank=blank,
                 disjoint=False, split='dev', phase='gates', arm='B', source='')
            for t in TASKS for blank in (False, True)
            for b in ((4000, 'full') if blank else (250, 1000, 4000, 'full'))
            for s in (range(1000, 1002) if b == 'full' else
                      range(1000, 1003) if blank else range(1000, 1005))]


def freeze_inputs(data):
    files = ['configs/pilot_protocol.FROZEN.yaml', 'configs/stage3_protocol.FROZEN.yaml',
             'gqa_audit/config/analysis_plan.FROZEN.yaml',
             'gqa_audit/outputs/stage2/task_registry.json',
             'gqa_audit/outputs/stage2b/analysis_subsets.json',
             'gqa_audit/outputs/stage2b/registry_questions.parquet',
             'gqa_audit/outputs/stage2/cache/questions_train.parquet',
             'gqa_audit/outputs/stage2/cache/questions_val.parquet']
    return {f: sha256(data.root / f) for f in files}
