"""Independent checks for the CLIP-only main study and its safety gates."""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import torch
from torch import nn

from gqa_audit.evaluation import study_contrast, paired_contrast
from src.vqa_research.chuyen_giao.core import (SPEC, TASKS, FAMILIES, ROOT, atomic,
    plan, source_config, gate_plan, rng, shuffled_control, StudyData)
from src.vqa_research.chuyen_giao.engine import Budget, BudgetStop, verified
from src.vqa_research.chuyen_giao.analysis import adjust_p, label
from src.vqa_research.probe.features import sha256


def sample(perfect=True):
    return pd.DataFrame({'question_id': list('abcd'), 'imageId': ['a', 'a', 'b', 'b'],
        'answer': ['yes', 'no', 'yes', 'no'], 'part': 'val',
        'pred': ['yes', 'no', 'yes', 'no'] if perfect else ['no', 'yes', 'no', 'yes'],
        'p_yes': [.8, .2, .8, .2] if perfect else [.2, .8, .2, .8],
        'score': [1., -1., 1., -1.] if perfect else [-1., 1., -1., 1.]})


def test_bootstrap_known_effects_and_split_guard():
    a, b = [sample(), sample()], [sample(False), sample(False)]
    result = study_contrast(a, b, resamples=100, delta=.01)
    assert result['mean'] == result['ci_low'] == result['ci_high'] == 1.
    assert result['positive_fraction'] == 1.
    assert result['p_positive'] == pytest.approx(1 / 101)
    assert result['p_negative'] == 1.
    assert study_contrast(a, b, metric='log_loss', resamples=100)['mean'] == pytest.approx(np.log(4))
    assert study_contrast(b, a, balanced=True, resamples=100)['mean'] == -1.
    assert study_contrast(a, a, resamples=100)['p_positive'] == 1.
    assert result == study_contrast(a, b, resamples=100, delta=.01)
    bad = sample()
    bad['part'] = 'testdev'
    with pytest.raises(ValueError, match='dev/val'):
        study_contrast([bad], [bad])
    bad = sample().iloc[::-1].copy()
    bad.loc[0, 'answer'] = 'no'
    with pytest.raises(ValueError, match='identical'):
        study_contrast([sample()], [bad])


def test_bootstrap_matches_reference_on_nonconstant_balanced_data():
    a, b = sample(), sample(False)
    a.loc[0, ['pred', 'score', 'p_yes']] = ['no', -.2, .45]
    a['part'] = b['part'] = 'dev'
    for balanced in (False, True):
        reference = paired_contrast({1000: a}, {1000: b}, [1000],
                                     class_balanced=balanced, resamples=100)
        for metric, key in [('primary', 'primary_gain'), ('log_loss', 'log_loss_gain')]:
            result = study_contrast([a], [b], balanced=balanced, metric=metric, resamples=100)
            for stat in ('mean', 'ci_low', 'ci_high', 'se'):
                assert result[stat] == pytest.approx(reference[key][stat])


def test_multiple_comparisons_and_evidence_labels():
    assert adjust_p([.01, .04, .03], 'holm') == pytest.approx([.03, .06, .06])
    assert adjust_p([.01, .04, .03], 'bh') == pytest.approx([.03, .04, .04])
    assert len(adjust_p([], 'bh')) == 0
    assert label(.04, .02, .06, .015, .8, 0, .01, 1, True, True) == 'hỗ trợ'
    assert label(.04, .02, .06, .015, .8, 0, .01, 1, False, True) == 'chưa đủ bằng chứng'
    assert label(-.04, -.06, -.02, .015, 0, 1, 1, .01, False, False) == 'gây hại'
    assert label(.001, -.02, .02, .015, .6, .4, .8, .8, True, True) == 'chưa đủ bằng chứng'


def test_exhaustive_plans_and_checkpoint_sharing():
    sources, jobs = plan()
    assert len(jobs) == 3086
    assert len(sources) == 323
    assert len({json.dumps(j, sort_keys=True) for j in jobs}) == len(jobs)
    for level, names, size in [('group', TASKS, 20), ('family', FAMILIES, 182)]:
        real = [j for j in jobs if j['level'] == level and not j['blank'] and not j['disjoint']
                and j['source'] in names]
        assert len({(j['source'], j['target']) for j in real}) == size
        assert {j['arm'] for j in real} == {'Seq', 'Joint'}
        assert all(j['target'] != j['source'] for j in real)
    assert len(gate_plan()) == 110
    assert SPEC['qwen'] is False
    j = next(j for j in jobs if j['source'] == 'exist' and not j['blank'] and not j['disjoint'])
    shared = source_config(j)
    assert shared['target'] == '*'
    assert shared == source_config({**j, 'target': 'logic', 'budget': 4000})
    assert source_config({**j, 'disjoint': True})['target'] == j['target']
    assert source_config({**j, 'source': 'self'})['target'] == j['target']
    assert shuffled_control('group', 'compare') == 'shuffled:verifyAttr'
    with pytest.raises(ValueError):
        rng(999, 1)


def test_budget_persists_and_waiting_is_not_counted(tmp_path):
    now = [500.]
    budget = Budget(tmp_path, limit=100, clock=lambda: now[0])
    now[0] += 20
    budget.save()
    assert json.loads((tmp_path / 'budget.json').read_text())['seconds'] == 20
    now[0] += 1000
    resumed = Budget(tmp_path, limit=100, clock=lambda: now[0])
    assert resumed.seconds == 20
    resumed.check(79)
    with pytest.raises(BudgetStop):
        resumed.check(80)


def test_run_validation_detects_corruption_and_missing_weights(tmp_path):
    p = sample().rename(columns={'imageId': 'unused'})[['question_id', 'score', 'p_yes', 'pred']]
    p['p_yes'] = torch.sigmoid(torch.tensor(p.score.to_numpy())).numpy()
    p.to_parquet(tmp_path / 'predictions.parquet', index=False)
    config = {'data': 'hash'}
    atomic(tmp_path / 'run.json', {'status': 'complete', 'config': config,
            'predictions_sha256': sha256(tmp_path / 'predictions.parquet'), 'checkpoint_sha256': None})
    assert verified(tmp_path, config, list('abcd'))
    assert not verified(tmp_path, config, list('abcd'), checkpoint=True)
    assert not verified(tmp_path, {'data': 'changed'}, list('abcd'))
    p.loc[0, 'p_yes'] = .99
    p.to_parquet(tmp_path / 'predictions.parquet', index=False)
    assert not verified(tmp_path, config, list('abcd'))


@pytest.mark.parametrize('width,tokens,text_width', [(768, 197, 512), (1024, 257, 768)])
def test_model_reads_both_clip_shapes(monkeypatch, width, tokens, text_width):
    import src.vqa_research.probe.model as module
    class Text(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(20, text_width)
        def forward(self, input_ids, attention_mask):
            return SimpleNamespace(last_hidden_state=self.embedding(input_ids))
    clip = SimpleNamespace(config=SimpleNamespace(
        vision_config=SimpleNamespace(image_size=224, patch_size=16 if tokens == 197 else 14,
                                      hidden_size=width),
        text_config=SimpleNamespace(hidden_size=text_width)), text_model=Text())
    monkeypatch.setattr(module.CLIPModel, 'from_pretrained', lambda *a, **k: clip)
    model = module.ProbeModel('unused', train_text=False, max_text_tokens=8).eval()
    assert model.image_projection.in_features == width
    assert model.text_projection.in_features == text_width
    with torch.no_grad():
        scores = model(image_tokens=torch.zeros(1, tokens, width),
                       input_ids=torch.ones(1, 8, dtype=torch.long),
                       attention_mask=torch.ones(1, 8, dtype=torch.long))
    assert scores.shape == (1,) and torch.isfinite(scores).all()
    assert not any(p.requires_grad for p in model.text_encoder.parameters())


def test_real_family_and_target_sampling():
    d = StudyData()
    for level, target, budget, offset, size in [('group', 'compare', 4000, 4000, 10000),
                                               ('family', 'existAttr', 500, 500, 2000)]:
        ids = d.target(level, target, budget, 0)
        source, labels = d.source(dict(level=level, target=target, budget=budget, seed=0, source='self'))
        assert len(source) == size and len(set(source)) == size
        assert not set(source) & set(ids)
        assert d.by_id.loc[source, 'part'].eq('train_core').all()
    assert set(d.target('group', 'compare', 250, 1)) <= set(d.target('group', 'compare', 1000, 1))


def test_readme_language_and_links():
    text = (ROOT / 'README.md').read_text()
    assert ';' not in text
    assert not re.search(r'\b(?:transfer|seed|task)\b', text, re.I)
    for link in re.findall(r'\]\(([^)]+)\)', text):
        if not link.startswith('http'):
            assert (ROOT / link).exists(), link


def test_gate_failure_never_reaches_the_main_matrix(monkeypatch, tmp_path):
    import src.vqa_research.chuyen_giao.pipeline as p
    monkeypatch.setattr(p, 'OUT', tmp_path)
    monkeypatch.setattr(p, 'CACHE', tmp_path / 'cache')
    atomic(tmp_path / 'model.json', {'revision': 'test'})
    atomic(tmp_path / 'cache/manifest.json', {'revision': 'test'})
    monkeypatch.setattr(p, 'StudyData', lambda: SimpleNamespace(max_text_tokens=32))
    monkeypatch.setattr(p, 'preflight', lambda d: {'inputs': {}, 'code': {}})
    for name in ('prepare_model', 'tokenizer_check', 'build_cache', 'smoke', 'projection'):
        monkeypatch.setattr(p, name, lambda *a: None)
    seen = []
    monkeypatch.setattr(p, 'run', lambda d, j, *a: (seen.append(j) or tmp_path))
    monkeypatch.setattr(p, 'gates', lambda *a: pd.DataFrame([
        {'G1': 'FLAG', 'G2': 'PASS', 'G3': 'PASS', 'G4': 'PASS'}]))
    assert p.execute(None) == 'STOP_GATES'
    assert len(seen) == 110 and all(j['phase'] == 'gates' for j in seen)


def test_queue_waits_for_other_gpu_processes(monkeypatch, tmp_path):
    import scripts.queue_chuyen_giao as q
    import src.vqa_research.chuyen_giao.pipeline as p
    monkeypatch.setattr(q, 'OUT', tmp_path)
    monkeypatch.setattr(q, 'gpu_pids', lambda: [123456])
    monkeypatch.setattr(p, 'update_readme', lambda *a: None)
    calls = []
    monkeypatch.setattr(p, 'execute', lambda *a: calls.append('should not execute'))
    def stop_waiting(seconds):
        assert seconds == 30
        raise RuntimeError('test wait interrupted')
    monkeypatch.setattr(q.time, 'sleep', stop_waiting)
    assert q.worker() == 1
    assert calls == []
    assert 'test wait interrupted' in json.loads((tmp_path / 'status.json').read_text())['error']


def test_real_engine_source_loading_union_and_resume_without_cuda(monkeypatch, tmp_path):
    import contextlib
    import src.vqa_research.chuyen_giao.engine as e
    monkeypatch.setattr(e, 'OUT', tmp_path)
    monkeypatch.setattr(e, 'assert_gpu_exclusive', lambda: None)
    monkeypatch.setattr(nn.Module, 'cuda', lambda self: self)
    monkeypatch.setattr(torch.Tensor, 'cuda', lambda self, *a, **k: self)
    monkeypatch.setattr(torch, 'autocast', lambda *a, **k: contextlib.nullcontext())
    for name in ('manual_seed_all', 'reset_peak_memory_stats', 'synchronize', 'empty_cache'):
        monkeypatch.setattr(torch.cuda, name, lambda *a: None)
    monkeypatch.setattr(torch.cuda, 'max_memory_allocated', lambda: 0)
    loaded = []
    class Small(nn.Module):
        def __init__(self, *a, **k):
            super().__init__()
            self.head = nn.Linear(1, 1)
        def forward(self, image_tokens, input_ids, attention_mask):
            return self.head(image_tokens).squeeze(-1)
        def load_state_dict(self, weights, strict=True):
            loaded.append({k: v.clone() for k, v in weights.items()})
            return super().load_state_dict(weights, strict=strict)
    monkeypatch.setattr(e, 'ProbeModel', Small)
    class Examples(torch.utils.data.Dataset):
        def __init__(self, data, ids, blank=False, labels=None):
            self.ids = ids
        def __len__(self):
            return len(self.ids)
        def __getitem__(self, i):
            return {'image_tokens': torch.tensor([float(i)]), 'input_ids': torch.tensor([1]),
                    'attention_mask': torch.tensor([1]), 'labels': torch.tensor(float(i % 2))}
    monkeypatch.setattr(e, 'Encoded', Examples)
    ids = ['s1', 's2', 't1', 't2', 'e1', 'e2']
    metadata = pd.DataFrame({'question_id': ids, 'answer': ['yes', 'no'] * 3,
                             'part': ['train_core'] * 4 + ['dev'] * 2}).set_index('question_id', drop=False)
    data = SimpleNamespace(by_id=metadata, max_text_tokens=8)
    base = dict(level='group', target='compare', seed=1000, budget=250, blank=False,
                disjoint=False, split='dev', phase='smoke', epochs=1, smoke_eval=['e1', 'e2'])
    guard = Budget(tmp_path)
    source = e.run(data, {**base, 'source': 'exist', 'arm': 'source', 'smoke_ids': ['s1', 's2']},
                   {'test': True}, guard, save_checkpoint=True)
    expected = torch.load(source / 'weights.pt', weights_only=True)
    target = e.run(data, {**base, 'source': 'exist', 'arm': 'Seq', 'smoke_ids': ['t1', 't2']},
                   {'test': True}, guard, initial=source / 'weights.pt')
    assert loaded and all(torch.equal(expected[k], loaded[0][k]) for k in expected)
    assert json.loads((target / 'run.json').read_text())['optimizer_steps'] == 1
    joint_job = {**base, 'source': 'exist', 'arm': 'Joint', 'smoke_ids': ids[:4]}
    joint = e.run(data, joint_job, {'test': True}, guard)
    assert json.loads((joint / 'run.json').read_text())['examples_seen'] == 4
    before = (joint / 'run.json').stat().st_mtime_ns
    assert e.run(data, joint_job, {'test': True}, guard) == joint
    assert (joint / 'run.json').stat().st_mtime_ns == before
    assert not list(tmp_path.glob('runs/*/*.tmp*'))


def test_budget_stops_charging_during_cpu_reporting(tmp_path):
    now = [0.]
    b = Budget(tmp_path, limit=100, clock=lambda: now[0])
    now[0] = 25.
    b.pause()
    now[0] = 10000.
    assert b.seconds == 25.
    b.save()
    assert json.loads((tmp_path / 'budget.json').read_text())['seconds'] == 25.


def test_readme_updates_only_the_generated_section(monkeypatch, tmp_path):
    import src.vqa_research.chuyen_giao.pipeline as p
    monkeypatch.setattr(p, 'ROOT', tmp_path)
    monkeypatch.setattr(p, 'OUT', tmp_path / 'outputs')
    text = 'Phần đầu\n<!-- KET_QUA_TU_DONG -->\ncũ\n<!-- HET_KET_QUA_TU_DONG -->\nPhần cuối\n'
    (tmp_path / 'README.md').write_text(text)
    p.update_readme('STOP_BUDGET')
    result = (tmp_path / 'README.md').read_text()
    assert result.startswith('Phần đầu\n') and result.endswith('\nPhần cuối\n')
    assert '24 giờ' in result and ';' not in result
    assert not re.search(r'\b(?:transfer|seed|task)\b', result, re.I)


def test_map_figures_and_directed_graphs(monkeypatch, tmp_path):
    import src.vqa_research.chuyen_giao.analysis as a
    monkeypatch.setattr(a, 'OUT', tmp_path)
    monkeypatch.setattr(a, 'TASKS', ('a', 'b'))
    monkeypatch.setattr(a, 'FAMILIES', ('c', 'd'))
    rows = []
    for level, names, budgets in [('group', a.TASKS, (250, 1000, 4000)), ('family', a.FAMILIES, (500,))]:
        for arm in ('Seq', 'Joint'):
            for budget in budgets:
                for source in names:
                    for target in names:
                        if source != target:
                            rows.append(dict(level=level, arm=arm, budget=budget, source=source,
                                             target=target, blank=False, disjoint=False,
                                             mean=.01, label='chưa đủ bằng chứng'))
    a.draw(rows)
    assert len(list((tmp_path / 'figures').glob('*.png'))) == 16
    assert len(list((tmp_path / 'figures').glob('*.pdf'))) == 16
    graph = (tmp_path / 'figures/group_Seq_1000.dot').read_text()
    assert '"a" -> "b"' in graph and '"b" -> "a"' in graph


def test_cache_identity_accepts_module_filename_string(monkeypatch, tmp_path):
    import src.vqa_research.chuyen_giao.features as f
    monkeypatch.setattr(f, 'MODEL', tmp_path)
    (tmp_path / 'pytorch_model.bin').write_bytes(b'pinned weights')
    identity = f.cache_identity(['image1', 'image2'], 16)
    assert identity == f.cache_identity(['image1', 'image2'], 16)
    assert identity['encoder_code_hash'] == sha256(Path(f.__file__))
    assert identity != f.cache_identity(['image2', 'image1'], 16)
    assert identity != f.cache_identity(['image1', 'image2'], 32)


def test_compact_plan_is_20_directions_only_with_paired_controls():
    from src.vqa_research.chuyen_giao.core import report_plan, REPORT_SPEC
    sources, jobs = report_plan()
    assert len(sources) == 39 and len(jobs) == 225
    assert all(j['level'] == 'group' and j['budget'] == 1000 and j['split'] == 'dev' for j in jobs)
    assert {j['seed'] for j in jobs} == {1000, 1001, 1002}
    assert all(not j['blank'] and not j['disjoint'] for j in jobs)
    assert sum(j['arm'] == 'B' for j in jobs) == 15
    real = [j for j in jobs if j['source'] in TASKS]
    assert len(real) == 120
    assert len({(j['source'], j['target']) for j in real}) == 20
    assert REPORT_SPEC['quality_gates'] == 'waived_by_user'
    assert REPORT_SPEC['family_seeds'] == []
    assert REPORT_SPEC['primary_edges'] == []


def test_compact_execution_omits_quality_suite_and_family_matrix(monkeypatch, tmp_path):
    import src.vqa_research.chuyen_giao.pipeline as p
    monkeypatch.setattr(p, 'OUT', tmp_path)
    monkeypatch.setattr(p, 'CACHE', tmp_path / 'cache')
    atomic(tmp_path / 'model.json', {'revision': 'test'})
    atomic(tmp_path / 'cache/manifest.json', {'revision': 'test'})
    atomic(tmp_path / 'plan.json', {'scope': 'compact'})
    data = SimpleNamespace(max_text_tokens=32, training=lambda j: (['training'], None),
                           evaluation=lambda *a: ['evaluation'])
    monkeypatch.setattr(p, 'StudyData', lambda: data)
    monkeypatch.setattr(p, 'preflight', lambda d, compact=False: {'inputs': {}, 'code': {}})
    for name in ('prepare_model', 'tokenizer_check', 'build_cache', 'smoke'):
        monkeypatch.setattr(p, name, lambda *a: None)
    def forbidden(*a):
        raise AssertionError('Skipped experiments must never run')
    for name in ('gate_plan', 'gates', 'family_calibration', 'select_pilot_metric'):
        monkeypatch.setattr(p, name, forbidden)
    def forecast(d, identity, guard, workload=None):
        assert len(workload[0]) == 39 and len(workload[1]) == 225
        return dict(seconds_per_example=.01, seconds_per_evaluation=.01, overhead_seconds_per_run=.01)
    monkeypatch.setattr(p, 'projection', forecast)
    seen = []
    monkeypatch.setattr(p, 'run', lambda d, job, *a, **kw: (seen.append(job) or tmp_path))
    monkeypatch.setattr(p, 'frame', lambda *a: None)
    monkeypatch.setattr(p, 'metrics', lambda *a: {'primary': .5})
    reports = []
    monkeypatch.setattr(p, 'report', lambda *a, **kw: reports.append(kw))
    guard = SimpleNamespace(check=lambda *a: None, tick=lambda *a, **kw: None, pause=lambda: None)
    assert p.execute_report(guard) == 'complete'
    assert len(seen) == 264 and all(j['split'] == 'dev' for j in seen)
    assert all(j['arm'] == 'B' for j in seen[:15])
    assert reports == [{'exploratory': True}]
    frozen = json.loads((tmp_path / 'design.FROZEN.json').read_text())
    assert frozen['evidence_level'] == 'exploratory'
    assert frozen['thresholds'] == {'group': .01}


def test_compact_report_is_exploratory_and_contains_all_real_edges(monkeypatch, tmp_path):
    import gqa_audit.evaluation as evaluation
    import src.vqa_research.chuyen_giao.analysis as a
    from src.vqa_research.chuyen_giao.core import report_plan
    monkeypatch.setattr(a, 'OUT', tmp_path)
    monkeypatch.setattr(a, 'draw', lambda *args: None)
    def fake_frame(data, job, path, subset=None):
        f = sample(perfect=job['source'] in TASKS)
        f['part'] = 'dev'
        return f
    monkeypatch.setattr(a, 'frame', fake_frame)
    original = evaluation.study_contrast
    monkeypatch.setattr(evaluation, 'study_contrast', lambda *args, **kw: original(*args, **kw, resamples=50))
    _, jobs = report_plan()
    a.report(None, [(j, tmp_path) for j in jobs], {'group': .01}, 'primary', exploratory=True)
    edges = json.loads((tmp_path / 'edges.json').read_text())
    real = [r for r in edges['edges'] if r['source'] in TASKS]
    assert len(real) == 40
    assert all(r['evidence_level'] == 'exploratory' and not r['primary_test'] for r in real)
    assert all('log_loss_gain_ci_low' in r for r in real)
    text = (tmp_path / 'BAO_CAO.md').read_text()
    assert 'Thí nghiệm thăm dò trên tập phát triển' in text
    assert 'Bộ kiểm chứng đầy đủ chất lượng mô hình chưa được chạy' in text
    assert '## Mốc học riêng' in text
