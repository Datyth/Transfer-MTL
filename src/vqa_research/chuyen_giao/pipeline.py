"""Gated CLIP-only study. Expensive work is preceded by an explicit cost check."""
import json
import os
import time
import shutil

import numpy as np
import pandas as pd

from gqa_audit.stage2_core import canonical_hash
from gqa_audit.evaluation import study_contrast
from ..probe.features import sha256
from .core import (ROOT, OUT, CACHE, SPEC, TASKS, FAMILIES, NAMES, StudyData, atomic,
                   plan, gate_plan, source_config, freeze_inputs, report_plan, REPORT_SPEC)
from .engine import BudgetStop, run, verified, eval_ids
from .features import prepare_model, tokenizer_check, build_cache
from .analysis import frame, metrics, gates, report


def family_calibration():
    return [dict(level='family', target=t, budget=500, seed=s, blank=False,
                 disjoint=False, split='dev', phase='calibration', arm='B', source='')
            for t in FAMILIES for s in range(1000, 1003)]


def code_hashes():
    files = [*(__import__('pathlib').Path(__file__).parent.glob('*.py')),
             ROOT / 'src/vqa_research/probe/model.py', ROOT / 'src/vqa_research/probe/train.py',
             ROOT / 'src/vqa_research/probe/features.py', ROOT / 'gqa_audit/evaluation.py']
    return {str(p.relative_to(ROOT)): sha256(p) for p in files}


def preflight(data, compact=False):
    from ..probe.protocol import PILOT_HASH
    if sha256(ROOT / 'configs/pilot_protocol.FROZEN.yaml') != PILOT_HASH:
        raise ValueError('Frozen pilot protocol changed')
    m = json.loads((ROOT / 'gqa_audit/outputs/stage2b/run_manifest.json').read_text())
    if sha256(ROOT / 'gqa_audit/outputs/stage2b/registry_questions.parquet') != m['artifacts']['registry_questions.parquet']:
        raise ValueError('Frozen registry metadata changed')
    sources, targets = report_plan() if compact else plan()
    required_bytes = 82374 * 257 * 1024 * 2 + len(sources) * 640 * 2**20 + 10 * 2**30
    existing = sum(p.stat().st_blocks * 512 for p in CACHE.glob('*') if p.is_file())
    existing += sum(p.stat().st_blocks * 512 for p in (OUT / 'runs').glob('*/weights.pt'))
    if shutil.disk_usage(ROOT).free < max(0, required_bytes - existing):
        raise ValueError('Insufficient disk space for the full CLIP-only design')
    # Resolve every exact training sample before any expensive matrix job.
    samples = {}
    for job in targets:
        key = (job['level'], job['target'], job['budget'], job['seed'])
        if key not in samples:
            samples[key] = data.target(*key)
        ids = samples[key]
        if job['arm'] != 'B':
            skey = tuple(job[k] for k in ('level', 'target', 'budget', 'seed', 'source', 'disjoint'))
            if skey not in samples:
                samples[skey] = data.source(job)[0]
            if set(ids) & set(samples[skey]):
                raise ValueError('Overlapping source/target question IDs')
    definitions = []
    for level, names in ([('group', TASKS)] if compact else [('group', TASKS), ('family', FAMILIES)]):
        for target in names:
            ids = data.pool(level, target, 'train_core')
            for part in ('train_core', 'dev', 'val'):
                pool = data.evaluation(level, target, part)
                if not pool or data.by_id.loc[pool, 'answer'].nunique() != 2:
                    raise ValueError(f'Evaluation requires both classes: {level} {target} {part}')
            examples = data.by_id.loc[ids[:2], ['question', 'answer', 'family']].to_dict('records')
            definitions.append({'level': level, 'name': target, 'title': NAMES.get(target, target),
                'counts': {p: len(data.pool(level, target, p)) for p in ('train_core', 'dev', 'val')},
                'families': sorted(data.by_id.loc[ids, 'family'].unique().tolist()),
                'examples': examples,
                'metric': 'balanced_accuracy@relation' if level == 'group' and target == 'verifyRel' else 'accuracy'})
    result = {'group_directions': 20, 'family_directions': 0 if compact else 182,
              'source_runs': len(sources), 'target_runs': len(targets),
              'gate_runs': 0 if compact else len(gate_plan()),
              'calibration_runs': 0 if compact else len(family_calibration()),
              'spec': REPORT_SPEC if compact else SPEC,
              'inputs': freeze_inputs(data), 'code': code_hashes(),
              'definitions': definitions, 'status': 'PASS'}
    atomic(OUT / 'preflight.json', result)
    atomic(OUT / 'plan.json', {'sources': sources, 'targets': targets})
    return result


def smoke(data, identity, guard):
    source_ids = data.target('group', 'exist', 250, 1000)[:8]
    target_ids = data.target('group', 'compare', 250, 1000)[:8]
    base = dict(level='group', target='compare', budget=250, seed=1000, blank=False,
                disjoint=False, split='dev', phase='smoke', epochs=1,
                smoke_eval=data.evaluation('group', 'compare', 'dev')[:8])
    b = run(data, {**base, 'arm': 'B', 'source': '', 'smoke_ids': target_ids}, identity, guard)
    a = run(data, {**base, 'arm': 'source', 'source': 'exist', 'smoke_ids': source_ids},
            identity, guard, save_checkpoint=True)
    s = run(data, {**base, 'arm': 'Seq', 'source': 'exist', 'smoke_ids': target_ids},
            identity, guard, initial=a / 'weights.pt')
    j = run(data, {**base, 'arm': 'Joint', 'source': 'exist', 'smoke_ids': source_ids + target_ids},
            identity, guard)
    labels = dict(zip(source_ids, data.by_id.loc[source_ids, 'answer'].to_numpy()[::-1]))
    run(data, {**base, 'arm': 'source', 'source': 'shuffled:exist',
               'smoke_ids': source_ids, 'smoke_labels': labels}, identity, guard)
    saved = json.loads((s / 'run.json').read_text())
    if saved['config']['initial_hash'] != sha256(a / 'weights.pt'):
        raise ValueError('Source checkpoint was not linked to sequential run')
    if json.loads((j / 'run.json').read_text())['examples_seen'] != len(source_ids + target_ids):
        raise ValueError('Joint run did not train on the union')
    mtime = (b / 'run.json').stat().st_mtime_ns
    run(data, {**base, 'arm': 'B', 'source': '', 'smoke_ids': target_ids}, identity, guard)
    if (b / 'run.json').stat().st_mtime_ns != mtime:
        raise ValueError('Completed run was not reused')
    atomic(OUT / 'gpu_smoke.json', {'status': 'PASS', 'runs': [p.name for p in (b, a, s, j)]})


def projection(data, identity, guard, workload=None):
    # Two tasks with different dev sizes, enough optimizer steps to avoid relying
    # on the first CUDA launch alone. Times are measured with the real L/14 model.
    records = []
    for target in ('compare', 'logic'):
        job = dict(level='group', target=target, budget=1000, seed=1000, blank=False,
                   disjoint=False, split='dev', phase='benchmark', arm='B', source='', epochs=1,
                   smoke_ids=data.target('group', target, 1000, 1000)[:512])
        p = run(data, job, identity, guard)
        records.append(json.loads((p / 'run.json').read_text()))
    seconds_per_example = max(r['training_seconds'] / r['examples_seen'] for r in records)
    seconds_per_eval = max(r['evaluation_seconds'] / len(eval_ids(data, r['config']['job'])) for r in records)
    overhead = max(max(0., r['wall_seconds'] - r['training_seconds'] - r['evaluation_seconds']) for r in records)
    sources, targets = workload if workload is not None else plan()
    remaining = ([*sources, *targets] if workload is not None else
                 [*gate_plan(), *family_calibration(), *sources, *targets])
    done = set()
    for record_path in (OUT / 'runs').glob('*/run.json'):
        r = json.loads(record_path.read_text())
        if r['config']['study'] == identity:
            j = r['config']['job']
            if verified(record_path.parent, r['config'], eval_ids(data, j), j['arm'] == 'source'):
                done.add(canonical_hash(j))
    remaining = [j for j in remaining if canonical_hash(j) not in done]
    total = 0.
    for job in remaining:
        train, _ = data.training(job)
        total += 10 * len(train) * seconds_per_example + len(eval_ids(data, job)) * seconds_per_eval + overhead
    # Includes validation repetitions, a repeated run, serialization, and IO margin.
    required = (total + 10 * 1000 * seconds_per_example) * 1.1
    result = {'remaining_gpu_hours': required / 3600, 'spent_gpu_hours': guard.seconds / 3600,
              'total_projected_gpu_hours': (guard.seconds + required) / 3600,
              'seconds_per_example': seconds_per_example, 'seconds_per_evaluation': seconds_per_eval,
              'overhead_seconds_per_run': overhead, 'run_count': len(remaining),
              'status': 'PASS' if guard.seconds + required < guard.limit else 'STOP_BUDGET'}
    atomic(OUT / 'projection.json', result)
    guard.check(required)
    return result


def execute_report(guard):
    """User-authorized compact exploratory run, with no validity gate suite."""
    data = StudyData()
    prepared = preflight(data, compact=True)
    prepare_model()
    tokenizer_check(data)
    build_cache(guard)
    identity = {'spec': REPORT_SPEC, 'inputs': prepared['inputs'], 'code': prepared['code'],
                'model': json.loads((OUT / 'model.json').read_text()),
                'cache_manifest_hash': sha256(CACHE / 'manifest.json'),
                'max_text_tokens': data.max_text_tokens}
    frozen = {'identity': identity, 'metric': 'primary', 'thresholds': {'group': .01},
              'plan_hash': sha256(OUT / 'plan.json'), 'evidence_level': 'exploratory',
              'limitations': ['quality_gates_not_run', 'no_blank_replication',
                              'no_image_disjoint_replication', 'no_val_inference']}
    frozen_path = OUT / 'design.FROZEN.json'
    if frozen_path.exists() and json.loads(frozen_path.read_text()) != frozen:
        raise ValueError('Compact study inputs changed after freezing. Preserve existing results and use a new study directory.')
    atomic(frozen_path, frozen)
    atomic(OUT / 'gate_decision.json', {'status': 'WAIVED_BY_USER',
           'note': 'Bỏ bộ kiểm chứng chất lượng theo yêu cầu. Đây là thí nghiệm thăm dò trên tập phát triển.'})
    smoke(data, identity, guard)
    sources, targets = report_plan()
    unit_cost = projection(data, identity, guard, workload=(sources, targets))
    entries, source_paths = [], {}
    # Collect every target-only baseline first, so an interrupted run still has
    # a readable baseline table without requiring the source arms to finish.
    targets = sorted(targets, key=lambda j: j['arm'] != 'B')
    for i, job in enumerate(targets):
        ids, _ = data.training(job)
        estimate = 1.1 * (len(ids) * 10 * unit_cost['seconds_per_example'] +
                   len(eval_ids(data, job)) * unit_cost['seconds_per_evaluation'] +
                   unit_cost['overhead_seconds_per_run'])
        if job['arm'] != 'B':
            sj = source_config(job)
            key = canonical_hash(sj)
            if key not in source_paths:
                source_ids, _ = data.training(sj)
                guard.check(estimate + 1.1 * (len(source_ids) * 10 * unit_cost['seconds_per_example'] +
                            len(eval_ids(data, sj)) * unit_cost['seconds_per_evaluation'] +
                            unit_cost['overhead_seconds_per_run']))
                source_paths[key] = run(data, sj, identity, guard, save_checkpoint=True)
        guard.check(estimate)
        initial = source_paths[canonical_hash(source_config(job))] / 'weights.pt' if job['arm'] == 'Seq' else None
        path = run(data, job, identity, guard, initial=initial)
        entries.append((job, path))
        atomic(OUT / 'matrix_manifest.json', {'runs': [{'job': j, 'path': p.name} for j, p in entries],
              'sources': {k: p.name for k, p in source_paths.items()}, 'expected': len(targets),
              'evidence_level': 'exploratory'})
        if job['arm'] == 'B':
            baseline = [{**j, **metrics(frame(data, j, p), j['target'] == 'verifyRel')}
                        for j, p in entries if j['arm'] == 'B']
            pd.DataFrame(baseline).to_csv(OUT / 'baselines.csv', index=False)
        guard.tick('report_matrix', completed=i + 1, total=len(targets), job=job)
    if len(entries) != 225 or len(source_paths) != 39:
        raise ValueError('Compact matrix is incomplete')
    guard.pause()
    guard.tick('analysis')
    report(data, entries, {'group': .01}, 'primary', source_paths, exploratory=True)
    return 'complete'


def select_pilot_metric(data):
    """Apply the frozen rule to the already finished B/16 pilot, not new val."""
    old = ROOT / 'gqa_audit/outputs/stage3_5'
    manifests = {phase: json.loads((old / f'{phase}_manifest.json').read_text())['runs']
                 for phase in ('curves', 'transfer')}
    loaded = {}
    def get(e):
        ident = e['run_id']
        if ident not in loaded:
            c = e['config']
            job = dict(level='group', target=c['task'], split='dev')
            loaded[ident] = frame(data, job, old / 'runs' / ident)
        return loaded[ident]
    pairs = []
    curves = manifests['curves']
    for target in TASKS:
        for high, low in ((1000, 250), (4000, 1000)):
            a = [e for e in curves if e['config']['task'] == target and e['config']['budget'] == high]
            b = [e for e in curves if e['config']['task'] == target and e['config']['budget'] == low]
            pairs.append((target, sorted(a, key=lambda e: e['config']['seed']), sorted(b, key=lambda e: e['config']['seed'])))
    groups, baselines = {}, {}
    for e in manifests['transfer']:
        c = e['config']
        if 'arm' not in c:
            baselines.setdefault(c['task'], {})[c['seed']] = e
        else:
            groups.setdefault((c['task'], c['arm'], c['source']), {})[c['seed']] = e
    for (target, _, _), arms in groups.items():
        seeds = sorted(arms)
        pairs.append((target, [arms[s] for s in seeds], [baselines[target][s] for s in seeds]))
    zs = {'primary': [], 'log_loss': []}
    for target, a, b in pairs:
        for metric in zs:
            result = study_contrast([get(e) for e in a], [get(e) for e in b],
                                    balanced=target == 'verifyRel', metric=metric)
            zs[metric].append(abs(result['z']))
    medians = {k: float(np.median(v)) for k, v in zs.items()}
    selected = 'log_loss' if medians['log_loss'] >= 1.25 * medians['primary'] else 'primary'
    atomic(OUT / 'metric_selection.json', {'selected': selected, 'median_abs_z': medians,
                                          'source': 'completed_stage3_5_B16_pilot'})
    return selected


def execute(guard):
    data = StudyData()
    prepared = preflight(data)
    prepare_model()
    tokenizer_check(data)
    build_cache(guard)
    identity = {'spec': SPEC, 'inputs': prepared['inputs'], 'code': prepared['code'],
                'model': json.loads((OUT / 'model.json').read_text()),
                'cache_manifest_hash': sha256(CACHE / 'manifest.json'),
                'max_text_tokens': data.max_text_tokens}
    smoke(data, identity, guard)
    projection(data, identity, guard)
    calibration = []
    for job in gate_plan():
        path = run(data, job, identity, guard)
        calibration.append((job, path))
    checks = gates(data, calibration)
    if checks[['G1', 'G2', 'G3', 'G4']].ne('PASS').any().any():
        atomic(OUT / 'gate_decision.json', {'status': 'STOP_GATES',
                'note': 'Mô hình chưa đạt điều kiện đo lường. Không chạy ma trận xác nhận.'})
        return 'STOP_GATES'
    # Measure numerical repeatability independently of across-initialization noise.
    original, original_path = next((j, p) for j, p in calibration if j['target'] == 'compare'
                                   and j['budget'] == 1000 and j['seed'] == 1000 and not j['blank'])
    repeated = run(data, {**original, 'replicate': 2}, identity, guard)
    pair = pd.read_parquet(original_path / 'predictions.parquet').merge(
        pd.read_parquet(repeated / 'predictions.parquet'), on='question_id', validate='one_to_one')
    diff = float(np.abs(pair.score_x - pair.score_y).max())
    atomic(OUT / 'repeat.json', {'max_logit_difference': diff, 'status': 'PASS' if diff <= 1e-3 else 'FLAG'})
    if diff > 1e-3:
        return 'STOP_REPEAT'
    for job in family_calibration():
        calibration.append((job, run(data, job, identity, guard)))
    primary = select_pilot_metric(data)
    metric_rows = []
    for j, p in calibration:
        if not j['blank'] and j['budget'] == (1000 if j['level'] == 'group' else 500):
            metric_rows.append({'level': j['level'], 'target': j['target'],
                               **metrics(frame(data, j, p), j['level'] == 'group' and j['target'] == 'verifyRel')})
    c = pd.DataFrame(metric_rows)
    thresholds = {level: float(max(.01, c[c.level.eq(level)].groupby('target')[primary].std(ddof=1).median() * 2))
                  for level in ('group', 'family')}
    frozen = {'identity': identity, 'thresholds': thresholds, 'metric': primary,
              'plan_hash': sha256(OUT / 'plan.json'), 'primary_edges': SPEC['primary_edges']}
    frozen_path = OUT / 'design.FROZEN.json'
    if frozen_path.exists() and json.loads(frozen_path.read_text()) != frozen:
        raise ValueError('Frozen main design differs from current inputs')
    atomic(frozen_path, frozen)
    sources, targets = plan()
    source_paths, entries = {}, []
    unit_cost = json.loads((OUT / 'projection.json').read_text())
    for i, job in enumerate(targets):
        # Reserve a conservative complete source+target job before starting it.
        training, _ = data.training(job)
        estimate = 1.1 * (len(training) * 10 * unit_cost['seconds_per_example'] +
                           len(eval_ids(data, job)) * unit_cost['seconds_per_evaluation'] +
                           unit_cost['overhead_seconds_per_run'])
        if job['arm'] != 'B':
            sj = source_config(job)
            key = canonical_hash(sj)
            if key not in source_paths:
                source_training, _ = data.training(sj)
                guard.check(estimate + len(source_training) * 10 * unit_cost['seconds_per_example'] +
                            len(eval_ids(data, sj)) * unit_cost['seconds_per_evaluation'])
                source_paths[key] = run(data, sj, identity, guard, save_checkpoint=True)
        guard.check(estimate)
        initial = source_paths[canonical_hash(source_config(job))] / 'weights.pt' if job['arm'] == 'Seq' else None
        path = run(data, job, identity, guard, initial=initial)
        entries.append((job, path))
        atomic(OUT / 'matrix_manifest.json', {'runs': [{'job': j, 'path': p.name} for j, p in entries],
                    'sources': {k: p.name for k, p in source_paths.items()}, 'expected': len(targets)})
        guard.tick('matrix', completed=i + 1, total=len(targets), job=job)
    if len(entries) != len(targets):
        raise ValueError('Incomplete matrix')
    guard.pause()
    guard.tick('analysis')
    report(data, entries, thresholds, primary, source_paths)
    update_readme('complete')
    return 'complete'


def update_readme(state):
    """Update only a bounded generated section, preserving the human introduction."""
    path = ROOT / 'README.md'
    text = path.read_text()
    opening, closing = '<!-- KET_QUA_TU_DONG -->', '<!-- HET_KET_QUA_TU_DONG -->'
    if opening not in text or closing not in text:
        return
    messages = {'complete': 'Đã hoàn thành bản đồ bằng CLIP ViT-L/14. Xem bảng số liệu và báo cáo ở đường dẫn dưới.',
                'STOP_GATES': 'CLIP bản lớn chưa đạt điều kiện đo lường. Ma trận xác nhận chưa được chạy.',
                'STOP_BUDGET': 'Dự toán hoặc thời gian đã dùng vượt giới hạn 24 giờ GPU. Chưa thể gọi bản đồ là hoàn chỉnh.',
                'failed': 'Hàng đợi gặp lỗi. Xem trạng thái và nhật ký để biết phần chưa hoàn thành.',
                'STOP_REPEAT': 'Phép chạy lặp chưa đạt độ ổn định số. Ma trận xác nhận chưa được chạy.'}
    body = messages.get(state, 'Đã xếp hàng chạy CLIP bản lớn. Kết quả đang được kiểm tra theo từng bước.')
    compact = OUT.name == 'bao_cao_chuyen_giao_clip_l14'
    if compact:
        body = ('Đã hoàn thành đợt thí nghiệm thăm dò giữa năm nhóm trên tập phát triển. '
                'Bộ kiểm chứng đầy đủ chất lượng mô hình được bỏ qua theo yêu cầu, kết quả chưa phải xác nhận độc lập.'
                if state == 'complete' else
                'Đã xếp hàng đợt thí nghiệm thu gọn giữa năm nhóm, với 1.000 câu đích và ba lần khởi tạo. '
                'Chưa có kết quả hoàn chỉnh.' if state not in messages else messages[state])
    directory = str(OUT.relative_to(ROOT))
    content = ('\n\n' + body + '\n\n'
               f'- [Trạng thái hàng đợi]({directory}/status.json)\n'
               f'- [Dự toán chi phí]({directory}/projection.json)\n'
               f'- [Điều kiện đo lường]({directory}/gates.csv)\n'
               f'- [Bảng các hướng đã đo]({directory}/edges.csv)\n'
               f'- [Báo cáo bản đồ]({directory}/BAO_CAO.md)\n\n')
    # Avoid links to outputs which do not exist yet.
    lines = [line for line in content.splitlines() if not line.startswith('- [') or
             (ROOT / line.split('](')[1].rstrip(')')).exists()]
    result = text.split(opening)[0] + opening + '\n'.join(lines) + closing + text.split(closing, 1)[1]
    tmp = path.with_suffix('.tmp')
    tmp.write_text(result)
    os.replace(tmp, path)
