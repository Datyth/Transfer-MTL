"""Rebuild report tables and eight figures from saved results, on CPU only.

Style follows figures4papers scientific-figure-making conventions.
Reference commit: 0ddfbd3fc9892e804a3fa01ae46bd0d32617f2aa.
No dependency on that checkout at runtime and no borrowed example datasets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gqa_audit.evaluation import point_metrics, probabilistic_metrics

DOCS = ROOT / 'docs'
FIGURES = DOCS / 'figures/project_overview'
TABLES = DOCS / 'tables/project_overview'
OLD = ROOT / 'gqa_audit/outputs/stage3_5'
FULL = ROOT / 'gqa_audit/outputs/chuyen_giao_clip_l14'
LATEST = ROOT / 'gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14'
TASKS = ('exist', 'verifyAttr', 'verifyRel', 'compare', 'logic')
NAMES = dict(zip(TASKS, ('Tồn tại', 'Thuộc tính', 'Quan hệ', 'So sánh', 'Suy luận logic')))
LABELS = ['Tồn tại', 'Thuộc tính', 'Quan hệ†', 'So sánh', 'Suy luận\nlogic']
PALETTE = dict(blue_main='#0F4D92', blue_secondary='#3775BA', green_1='#DDF3DE',
               green_2='#AADCA9', green_3='#8BCF8B', red_1='#F6CFCB',
               red_2='#E9A6A1', red_strong='#B64342', neutral='#CFCECE',
               teal='#42949E', violet='#9A4D8E')
FIGURE_NAMES = ('01_dataset', '02_pipeline', '03_qwen', '04_learning_curves',
                '05_image_blank', '06_transfer_matrices', '07_effects_controls', '08_cost')


def apply_publication_style():
    plt.rcParams.update({'font.family': 'DejaVu Sans',
        'font.size': 13, 'axes.linewidth': 1.8, 'axes.spines.top': False,
        'axes.spines.right': False, 'legend.frameon': False, 'text.usetex': False,
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
        'figure.facecolor': 'white', 'axes.facecolor': 'white'})


def finalize_figure(fig, basename, layout=True):
    if layout:
        fig.tight_layout(pad=1.5)
    for ext in ('png', 'pdf'):
        fig.savefig(FIGURES / f'{basename}.{ext}', dpi=300, facecolor='white',
                    bbox_inches='tight', pad_inches=.12)
    plt.close(fig)


class Sources:
    def __init__(self):
        self.files = {}

    def record(self, path):
        path = Path(path)
        key = str(path.relative_to(ROOT))
        if key not in self.files:
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                    digest.update(block)
            self.files[key] = digest.hexdigest()
        return path

    def json(self, path):
        return json.loads(self.record(path).read_text())

    def csv(self, path):
        return pd.read_csv(self.record(path))


def primary_metrics(predictions, task, registry, subsets, metadata):
    ids = (subsets['verifyRel_relation']['program_strict'][task]['dev']
           if task == 'verifyRel' else registry['variants']['program_strict'][task]['dev'])
    if predictions.question_id.duplicated().any():
        raise ValueError('Duplicate prediction IDs')
    indexed = predictions.set_index('question_id')
    if not set(ids) <= set(indexed.index):
        raise ValueError('Missing primary-scope predictions')
    frame = indexed.loc[ids].join(metadata[['answer']], validate='one_to_one')
    if not frame.pred.eq(np.where(frame.score > 0, 'yes', 'no')).all():
        raise ValueError('Predictions violate the score threshold')
    p = point_metrics(frame)
    return {'n': len(frame), 'primary': p['balanced_accuracy' if task == 'verifyRel' else 'accuracy'],
            **probabilistic_metrics(frame, class_balanced=task == 'verifyRel')}


def load_data():
    src = Sources()
    registry = src.json(ROOT / 'gqa_audit/outputs/stage2/task_registry.json')
    subsets = src.json(ROOT / 'gqa_audit/outputs/stage2b/analysis_subsets.json')['subsets']
    metadata_path = src.record(ROOT / 'gqa_audit/outputs/stage2b/registry_questions.parquet')
    metadata = pq.read_table(metadata_path, columns=['question_id', 'answer']).to_pandas().set_index('question_id')
    dataset = src.csv(ROOT / 'gqa_audit/outputs/stage2/task_stats.csv')
    dataset = dataset[(dataset.variant == 'program_strict') & (dataset.level == 'task')].copy()
    qwen = src.csv(ROOT / 'gqa_audit/outputs/stage3/metrics_3b.csv')
    qwen = qwen[(qwen.variant == 'program_strict') & (qwen.level == 'task')].copy()
    blind = src.csv(ROOT / 'gqa_audit/outputs/stage2b/demo_eval_blind.csv')
    blind = blind[(blind.variant == 'program_strict') & (blind.level == 'task')].copy()
    within = src.csv(ROOT / 'gqa_audit/outputs/stage2b/verifyrel_within_subset_baselines.csv')
    within = within[(within.variant == 'program_strict') & (within.subset == 'verifyRel_relation')]
    floors = blind.set_index(['task', 'part']).primary_value.to_dict()
    for row in within.itertuples():
        floors['verifyRel', row.part] = row.balanced_accuracy
    rows, parameters = [], {}
    for phase, expected in [('curves', 85), ('blank', 25)]:
        manifest = src.json(OLD / f'{phase}_manifest.json')
        if len(manifest['runs']) != expected:
            raise ValueError(f'Incomplete {phase}')
        for entry in manifest['runs']:
            folder = OLD / 'runs' / entry['run_id']
            record = src.json(folder / 'run.json')
            pred = pd.read_parquet(src.record(folder / 'predictions.parquet'))
            config = entry['config']
            if record['config'] != config or record['status'] != 'complete':
                raise ValueError('Pilot configuration mismatch')
            rows.append(dict(phase=phase, **config,
                **primary_metrics(pred, config['task'], registry, subsets, metadata)))
            parameters['clip_b16_probe'] = record['parameters']
    pilot = pd.DataFrame(rows)
    transfer_rows = []
    transfer = src.json(OLD / 'transfer_manifest.json')
    if len(transfer['runs']) != 99 or len(transfer['sources']) != 27:
        raise ValueError('Incomplete B/16 transfer pilot')
    for entry in transfer['runs']:
        folder = OLD / 'runs' / entry['run_id']
        record = src.json(folder / 'run.json')
        config = entry['config']
        pred = pd.read_parquet(src.record(folder / 'predictions.parquet'))
        if record['config'] != config or record['status'] != 'complete':
            raise ValueError('Transfer pilot configuration mismatch')
        transfer_rows.append({**config, 'arm': config.get('arm', 'B'),
                              'source': config.get('source', ''),
                              **primary_metrics(pred, config['task'], registry, subsets, metadata)})
    lora_rows = []
    for path in sorted((OLD / 'qwen_runs').glob('*/run.json')):
        record = src.json(path)
        c = record['config']
        if record['status'] != 'complete' or c['benchmark']:
            raise ValueError('Not a completed Qwen LoRA experiment')
        pred = pd.read_parquet(src.record(path.parent / 'predictions.parquet'))
        lora_rows.append({**c, **primary_metrics(pred, 'compare', registry, subsets, metadata),
            **{k: record[k] for k in ('training_seconds', 'evaluation_seconds', 'peak_gpu_bytes')}})
    lora = pd.DataFrame(lora_rows)
    if set(zip(lora.budget, lora.seed)) != {(b, s) for b in (1000, 4000) for s in (1000, 1001)}:
        raise ValueError('Missing Qwen pilot cell')
    edges = src.csv(LATEST / 'edges.csv')
    baselines = src.csv(LATEST / 'baselines.csv')
    metrics = src.csv(LATEST / 'metrics.csv')
    manifest = src.json(LATEST / 'matrix_manifest.json')
    if len(manifest['runs']) != 225 or len(manifest['sources']) != 39:
        raise ValueError('Incomplete report experiment')
    if len(baselines) != 15 or not baselines.split.eq('dev').all():
        raise ValueError('Wrong baseline scope')
    real = edges[edges.source.isin(TASKS)]
    if len(real) != 40 or len(set(zip(real.source, real.target))) != 20:
        raise ValueError('Wrong number of directed comparisons')
    timing = []
    for path in sorted((LATEST / 'runs').glob('*/run.json')):
        record = src.json(path)
        j = record['config']['job']
        if record['status'] != 'complete':
            raise ValueError('Incomplete run record')
        timing.append({**j, **{k: record[k] for k in
                      ('training_seconds', 'evaluation_seconds', 'examples_seen', 'optimizer_steps')}})
        if j['phase'] == 'report':
            parameters['clip_l14_probe'] = record['parameters']
    for path in (OLD / 'selected_recipe.json', OLD / 'repeat.json', OLD / 'qwen_regression.json',
                 LATEST / 'design.FROZEN.json', LATEST / 'gate_decision.json'):
        src.json(path)
    for relative in ('gqa_audit/outputs/stage1/schema_report.md',
        'gqa_audit/outputs/stage2/AUDIT_REPORT.md', 'gqa_audit/config/FROZEN_MANIFEST.json',
        'gqa_audit/outputs/stage2b/STAGE2B_REPORT.md',
        'gqa_audit/outputs/stage2b/program_structure_baseline.csv',
        'gqa_audit/outputs/stage2/split_image_overlap.csv',
        'gqa_audit/outputs/stage3/STAGE3_REPORT.md',
        'gqa_audit/outputs/stage3/paired_difference_corrections.csv',
        'gqa_audit/outputs/bao_cao_chuyen_giao_clip_l14/tests.xml',
        'configs/pilot_protocol.FROZEN.yaml', 'configs/stage3_protocol.FROZEN.yaml',
        'gqa_audit/config/analysis_plan.FROZEN.yaml', 'gqa_audit/config/task_rules.yaml',
        'data/features/clip_vitb16_224/manifest.json', 'data/features/clip_vitl14_224/manifest.json'):
        src.record(ROOT / relative)
    data = dict(sources=src, registry=registry, dataset=dataset, qwen=qwen, floors=floors,
                pilot=pilot, old_transfer=pd.DataFrame(transfer_rows), lora=lora,
                edges=edges, baselines=baselines, metrics=metrics,
                timing=pd.DataFrame(timing), parameters=parameters,
                recipe=src.csv(OLD / 'recipe_selection.csv'),
                full_projection=src.json(FULL / 'projection.json'),
                compact_projection=src.json(LATEST / 'projection.json'),
                status=src.json(LATEST / 'status.json'),
                old_budget=src.json(FULL / 'budget.json'))
    return data


def make_tables(d):
    out = {'dataset': d['dataset'], 'qwen_zero_shot': d['qwen'],
           'clip_b16_runs': d['pilot'], 'qwen_lora_runs': d['lora'],
           'clip_l14_baselines': d['baselines'], 'clip_l14_edges': d['edges'],
           'run_timings': d['timing']}
    curves = d['pilot'][d['pilot'].phase.eq('curves')]
    out['clip_b16_learning_summary'] = curves.groupby(['task', 'budget']).agg(
        mean=('primary', 'mean'), sd=('primary', 'std'), n=('primary', 'count'),
        log_loss=('log_loss', 'mean'), auroc=('auroc', 'mean')).reset_index()
    b16 = curves[curves.budget.eq(1000) & curves.seed.isin([1000, 1001, 1002])]
    l14 = d['baselines'].rename(columns={'target': 'task'})
    left = b16.groupby('task').primary.agg(['mean', 'std']).add_prefix('b16_')
    right = l14.groupby('task').primary.agg(['mean', 'std']).add_prefix('l14_')
    out['matched_baselines'] = left.join(right).reset_index()
    rows = []
    for task in TASKS:
        image = curves[curves.task.eq(task) & curves.budget.eq('full')]
        blank = d['pilot'][d['pilot'].phase.eq('blank') & d['pilot'].task.eq(task)
                          & d['pilot'].budget.eq('full')]
        pair = image[['seed', 'primary']].merge(blank[['seed', 'primary']], on='seed', validate='one_to_one')
        if len(pair) != 2:
            raise ValueError('Image/blank seeds are not paired')
        rows.append(dict(task=task, image=pair.primary_x.mean(), blank=pair.primary_y.mean(),
                         image_gain=(pair.primary_x - pair.primary_y).mean(),
                         text_floor=d['floors'][task, 'dev']))
    out['image_blank_summary'] = pd.DataFrame(rows)
    gate_rows = []
    for r in rows:
        task = r['task']
        values = curves[curves.task.eq(task)]
        noise = values[values.budget.eq(1000)].primary.std(ddof=1)
        growth = (values[values.budget.eq(4000)].primary.mean() -
                  values[values.budget.eq(1000)].primary.mean()) / 2
        gate_rows.append(dict(task=task, G1='PASS' if r['image'] - r['text_floor'] >= .1 else 'FLAG',
            G2='PASS' if r['image_gain'] >= .1 else 'FLAG', G3='PASS' if growth >= .01 else 'FLAG',
            G4='PASS' if noise <= .015 else 'FLAG', growth_per_doubling=growth, sd_1000=noise))
    out['clip_b16_gates'] = pd.DataFrame(gate_rows)
    old = d['old_transfer']
    baseline = old[old.arm.eq('B')].set_index(['task', 'seed'])
    gains = old[~old.arm.eq('B')].copy()
    gains['gain'] = [value - baseline.loc[(task, seed), 'primary']
                     for task, seed, value in zip(gains.task, gains.seed, gains.primary)]
    out['clip_b16_transfer_runs'] = gains
    out['clip_b16_transfer_summary'] = gains.groupby(['task', 'source', 'arm']).agg(
        gain_mean=('gain', 'mean'), gain_sd=('gain', 'std'), n=('gain', 'size')).reset_index()
    ranks = d['recipe'].groupby(['lr_fusion', 'train_text', 'epochs']).agg(
        mean_rank=('rank', 'mean'), median_loss=('dev_log_loss', 'median'), n=('rank', 'size')).reset_index()
    out['recipe_ranks'] = ranks.sort_values('mean_rank')
    return out


def plot_dataset(d):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.3))
    ax = axes[0]
    bottom = np.zeros(5)
    for part, label_, color in [('train_core', 'Huấn luyện', 'blue_main'), ('dev', 'Phát triển', 'teal'), ('val', 'Xác nhận', 'red_2')]:
        f = d['dataset'][d['dataset'].split.eq(part)].set_index('task').loc[list(TASKS)]
        ax.bar(range(5), f.questions, bottom=bottom, label=label_, color=PALETTE[color], edgecolor='white')
        bottom += f.questions.to_numpy()
    ax.set(xticks=range(5), xticklabels=LABELS, ylabel='Số câu hỏi', title='(a) Năm nhóm sau lọc')
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x/1000:g}k'))
    ax.legend(fontsize=11)
    f = d['dataset'][d['dataset'].split.eq('train_core')].set_index('task').loc[list(TASKS)]
    axes[1].bar(range(5), f.yes_ratio * 100, color=PALETTE['blue_secondary'], edgecolor='black', linewidth=.7)
    axes[1].axhline(50, color='#555555', ls='--', lw=1)
    for i, ratio in enumerate(f.yes_ratio):
        axes[1].text(i, ratio * 100 + 2, f'{ratio:.1%}', ha='center', fontsize=11)
    axes[1].set(xticks=range(5), xticklabels=LABELS, ylim=(0, 100),
                ylabel='Tỷ lệ nhãn yes (%)', title='(b) Cân bằng trên tập huấn luyện')
    finalize_figure(fig, '01_dataset')


def plot_pipeline():
    fig, ax = plt.subplots(figsize=(16, 6.6))
    ax.set(xlim=(0, 16), ylim=(0, 7))
    ax.axis('off')
    def box(x, y, w, h, text, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.12',
                     edgecolor=PALETTE['blue_main'], facecolor=color, linewidth=1.5))
        ax.text(x + w / 2, y + h / 2, text, ha='center', va='center', fontsize=12)
    def arrow(a, b):
        ax.annotate('', xy=b, xytext=a, arrowprops={'arrowstyle': '-|>', 'color': '#4D4D4D', 'lw': 1.6})
    box(.25, 4.5, 2.3, 1.4, 'Ảnh và câu hỏi GQA\nNhãn yes/no', PALETTE['green_1'])
    box(3.2, 4.5, 3., 1.4, 'Kiểm toán và registry\nQuy tắc cố định\nChia tập theo ảnh', '#EDF2F8')
    box(7., 4.5, 3.3, 1.4, 'Các mốc tham chiếu\nChỉ đọc câu hỏi\nQwen trước huấn luyện', '#EDF2F8')
    box(11.3, 4.5, 4., 1.4, 'CLIP đóng băng\nẢnh + câu hỏi → biểu diễn\nBộ kết hợp và đầu ra chung', PALETTE['green_1'])
    for a, b in [((2.7, 5.2), (3., 5.2)), ((6.4, 5.2), (6.8, 5.2)), ((10.5, 5.2), (11.1, 5.2))]:
        arrow(a, b)
    box(8.6, 1.85, 6.7, 1.5, 'Học riêng  |  Học lần lượt  |  Học chung\nCùng mẫu đích và lần khởi tạo\nĐối chứng cùng nhóm, ngoài nhóm, đảo nhãn', '#EDF2F8')
    arrow((13.3, 4.3), (13.3, 3.55))
    box(.25, 1.85, 6.9, 1.5, 'Đánh giá và bằng chứng\nChênh lệch so với học riêng + khoảng tin cậy\nBản đồ có hướng và báo cáo giới hạn kết luận', PALETTE['red_1'])
    arrow((8.4, 2.6), (7.35, 2.6))
    ax.text(8, .65, 'Chương trình suy luận, họ câu hỏi và tên nhiệm vụ chỉ dùng để phân tích, không đưa vào mô hình.',
            ha='center', fontsize=12, color='#4D4D4D')
    finalize_figure(fig, '02_pipeline')


def plot_qwen(d):
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.8), gridspec_kw={'width_ratios': [1.6, 1]})
    f = d['qwen'][d['qwen'].part.eq('val')]
    x = np.arange(5)
    for offset, condition, label_, color in [(-.26, 'image', 'Có ảnh', 'blue_main'), (0, 'no_image', 'Không ảnh', 'red_2')]:
        rows = f[f.condition.eq(condition)].set_index('task').loc[list(TASKS)]
        y = rows.primary_value.to_numpy() * 100
        err = np.stack((y - rows.ci_low.to_numpy() * 100, rows.ci_high.to_numpy() * 100 - y))
        axes[0].bar(x + offset, y, width=.25, color=PALETTE[color], label=label_,
                    yerr=err, capsize=3, edgecolor='black', linewidth=.5)
    floors = [d['floors'][t, 'val'] * 100 for t in TASKS]
    axes[0].bar(x + .26, floors, width=.25, color=PALETTE['green_3'], label='Chỉ đọc câu hỏi', edgecolor='black', linewidth=.5)
    axes[0].set(xticks=x, xticklabels=LABELS, ylim=(0, 100), ylabel='Điểm chính (%)',
                title='(a) Qwen chưa huấn luyện thêm, tập xác nhận')
    axes[0].legend(fontsize=10, ncol=3, loc='upper center', bbox_to_anchor=(.5, 1.02))
    reference = d['qwen'][d['qwen'].part.eq('dev') & d['qwen'].task.eq('compare') & d['qwen'].condition.eq('image')].primary_value.item()
    axes[1].axhline(reference * 100, color=PALETTE['red_strong'], ls='--', label=f'Chưa huấn luyện: {reference:.2%}')
    for i, budget in enumerate((1000, 4000)):
        values = d['lora'][d['lora'].budget.eq(budget)].sort_values('seed').primary.to_numpy() * 100
        axes[1].scatter(i + np.array([-.055, .055]), values, s=60, color=PALETTE['blue_main'], zorder=3)
        axes[1].errorbar(i, values.mean(), yerr=values.std(ddof=1), fmt='_', markersize=22,
                         color='black', capsize=5)
    axes[1].set(xticks=[0, 1], xticklabels=['1.000 câu', '4.000 câu'], xlim=(-.5, 1.5), ylim=(68, 81),
                ylabel='Accuracy (%)', title='(b) LoRA trên nhóm so sánh, tập phát triển')
    axes[1].legend(fontsize=11, loc='lower right')
    fig.text(.5, -.015, '† Quan hệ dùng balanced accuracy. (a) Thanh sai số: CI 95%. (b) Điểm: hai lần khởi tạo, gạch và sai số: trung bình ± SD.',
             ha='center', fontsize=11)
    finalize_figure(fig, '03_qwen')


def plot_learning(d):
    fig, axes = plt.subplots(1, 5, figsize=(20, 4.7), sharey=True)
    curves = d['pilot'][d['pilot'].phase.eq('curves')]
    for ax, task, label_ in zip(axes, TASKS, LABELS):
        means, deviations, positions = [], [], []
        full = len(d['registry']['variants']['program_strict'][task]['train_core'])
        for budget in (250, 1000, 4000, 'full'):
            values = curves[curves.task.eq(task) & curves.budget.eq(budget)].sort_values('seed').primary.to_numpy() * 100
            pos = full if budget == 'full' else budget
            ax.scatter(pos * np.linspace(.94, 1.06, len(values)), values, color=PALETTE['blue_secondary'], s=20, alpha=.65)
            positions.append(pos)
            means.append(values.mean())
            deviations.append(values.std(ddof=1))
        ax.errorbar(positions, means, yerr=deviations, color=PALETTE['blue_main'], marker='o', capsize=3, lw=2)
        ax.set(xscale='log', xticks=positions, xticklabels=['250', '1k', '4k', f'Đủ\n{full/1000:.1f}k'],
               ylim=(40, 85), title=label_, xlabel='Số câu huấn luyện')
        ax.tick_params(axis='x', labelsize=10)
    axes[0].set_ylabel('Điểm chính (%)')
    fig.suptitle('CLIP ViT-B/16 trên tập phát triển, trung bình ± SD', y=1.05)
    fig.text(.5, -.035, 'Các mức 250–4.000 có năm lần khởi tạo. Mức toàn bộ có hai lần. † Quan hệ dùng balanced accuracy.', ha='center', fontsize=11)
    finalize_figure(fig, '04_learning_curves')


def plot_image_blank(d, tables):
    fig, ax = plt.subplots(figsize=(11, 5.6))
    f = tables['image_blank_summary'].set_index('task').loc[list(TASKS)]
    x = np.arange(5)
    ax.bar(x - .18, f.image * 100, width=.35, color=PALETTE['blue_main'], label='Ảnh thật')
    ax.bar(x + .18, f.blank * 100, width=.35, color=PALETTE['neutral'], label='Ảnh trắng')
    for i, task in enumerate(TASKS):
        for phase, pos in [('curves', i - .18), ('blank', i + .18)]:
            values = d['pilot'][d['pilot'].phase.eq(phase) & d['pilot'].task.eq(task)
                                & d['pilot'].budget.eq('full')].sort_values('seed').primary.to_numpy() * 100
            ax.scatter(pos + np.array([-.035, .035]), values, s=30, color='black', zorder=3)
        ax.text(i, max(f.loc[task, 'image'], f.loc[task, 'blank']) * 100 + 4,
                f'{100*f.loc[task, "image_gain"]:+.2f} điểm', ha='center', fontsize=11)
    ax.set(xticks=x, xticklabels=LABELS, ylim=(0, 100), ylabel='Điểm chính (%)',
           title='CLIP ViT-B/16, toàn bộ dữ liệu huấn luyện, tập phát triển')
    ax.legend(ncol=2, loc='upper left')
    finalize_figure(fig, '05_image_blank')


def plot_matrices(d):
    edges = d['edges'][d['edges'].source.isin(TASKS)]
    limit = float(np.ceil(edges['mean'].abs().max() * 100 * 2) / 2)
    cmap = LinearSegmentedColormap.from_list('report_diverging', [PALETTE['red_strong'], '#FFFFFF', PALETTE['blue_main']])
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    im = None
    for ax, arm, label_ in zip(axes, ('Seq', 'Joint'), ('Học lần lượt', 'Học chung')):
        values = np.full((5, 5), np.nan)
        for row in edges[edges.arm.eq(arm)].itertuples():
            values[TASKS.index(row.source), TASKS.index(row.target)] = row.mean * 100
        if np.isfinite(values).sum() != 20:
            raise ValueError('A transfer matrix must contain exactly 20 directions')
        im = ax.imshow(values, cmap=cmap, vmin=-limit, vmax=limit)
        for i in range(5):
            for j in range(5):
                if i != j:
                    value = values[i, j]
                    ax.text(j, i, f'{value:+.2f}', ha='center', va='center', fontsize=12,
                            color='white' if abs(value) > .65 * limit else 'black')
        ax.set(xticks=range(5), yticks=range(5), xticklabels=LABELS, yticklabels=LABELS,
               xlabel='Nhóm đích', ylabel='Nhóm nguồn', title=label_)
        plt.setp(ax.get_xticklabels(), rotation=35, ha='right')
    fig.subplots_adjust(left=.10, right=.88, bottom=.22, top=.87, wspace=.45)
    cax = fig.add_axes([.91, .24, .018, .56])
    fig.colorbar(im, cax=cax, label='Mức tăng điểm phần trăm so với học riêng')
    fig.suptitle('CLIP ViT-L/14, 1.000 câu đích, ba lần khởi tạo, tập phát triển', y=.98)
    fig.text(.5, .025, 'Màu thể hiện ước lượng trung bình. Cả 40 phép so sánh chưa vượt toàn bộ tiêu chí bằng chứng.', ha='center', fontsize=11)
    finalize_figure(fig, '06_transfer_matrices', layout=False)


def plot_effects(d):
    fig, axes = plt.subplots(3, 2, figsize=(16, 14), sharex=True)
    low = np.floor(d['edges'].ci_low.min() * 100) - .5
    high = np.ceil(d['edges'].ci_high.max() * 100) + .5
    for ax, target in zip(axes.flat, TASKS):
        subset = d['edges'][d['edges'].target.eq(target)]
        shuffled = next(s for s in subset.source.unique() if s.startswith('shuffled:'))
        sources = [s for s in TASKS if s != target] + ['self', 'placebo', shuffled]
        labels = [NAMES[s] if s in NAMES else 'Cùng nhóm' if s == 'self' else
                  'Ngoài nhóm' if s == 'placebo' else 'Đảo nhãn\n(' + NAMES[s.split(':')[1]].lower() + ')' for s in sources]
        ax.axvspan(-1, 1, color=PALETTE['neutral'], alpha=.25)
        ax.axvline(0, color='#555555', ls='--', lw=1)
        for offset, arm, marker, color in [(-.13, 'Seq', 'o', 'blue_main'), (.13, 'Joint', 'D', 'teal')]:
            rows = subset[subset.arm.eq(arm)].set_index('source').loc[sources]
            y = np.arange(7) + offset
            mean = rows['mean'].to_numpy() * 100
            errors = np.maximum(0, np.stack((mean - rows.ci_low.to_numpy()*100, rows.ci_high.to_numpy()*100 - mean)))
            ax.errorbar(mean, y, xerr=errors, fmt=marker, color=PALETTE[color], capsize=3, markersize=5, lw=1.4)
        ax.set(yticks=range(7), yticklabels=labels, ylim=(6.7, -.7), xlim=(low, high),
               xlabel='Mức tăng điểm phần trăm', title='Đích: ' + NAMES[target] + ('†' if target == 'verifyRel' else ''))
        ax.tick_params(axis='y', labelsize=11)
        ax.tick_params(axis='x', labelbottom=True, labelsize=10)
    legend = axes.flat[-1]
    legend.set_axis_off()
    legend.legend(handles=[Line2D([0], [0], color=PALETTE['blue_main'], marker='o', label='Học lần lượt'),
                           Line2D([0], [0], color=PALETTE['teal'], marker='D', label='Học chung'),
                           Patch(facecolor=PALETTE['neutral'], alpha=.4, label='Vùng ±1 điểm')], loc='upper left')
    legend.text(.02, .52, 'Thanh sai số: CI 95% ghép cặp\nqua lần khởi tạo và cụm ảnh.\n\nCI thô khác với kết luận sau điều chỉnh\nnhiều phép kiểm định và đối chứng.\n\n† Quan hệ dùng balanced accuracy.\n\nKết quả thăm dò trên tập phát triển.', transform=legend.transAxes, fontsize=12, va='top')
    fig.suptitle('Nguồn thật và đối chứng trong đợt CLIP ViT-L/14', y=1.01)
    finalize_figure(fig, '07_effects_controls')


def plot_cost(d):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6))
    full = d['full_projection']['total_projected_gpu_hours']
    forecast = d['compact_projection']['total_projected_gpu_hours']
    actual = d['status']['gpu_seconds'] / 3600
    axes[0].bar([0], [full], width=.45, color=PALETTE['red_2'], edgecolor='black', hatch='//')
    axes[0].axhline(24, color=PALETTE['red_strong'], ls='--', label='Giới hạn 24 giờ')
    axes[0].text(0, full + 3, f'{full:.2f} giờ\nChỉ là dự toán', ha='center', fontsize=12)
    axes[0].set(xticks=[0], xticklabels=['Thiết kế đầy đủ'], ylim=(0, full * 1.2),
                ylabel='Giờ theo bộ đếm dự toán', title='(a) Thiết kế đầy đủ đã dừng')
    axes[0].legend(loc='upper right', fontsize=11)
    axes[1].bar([0, 1], [forecast, actual], color=[PALETTE['neutral'], PALETTE['blue_main']],
                edgecolor='black', width=.55)
    for i, value in enumerate([forecast, actual]):
        axes[1].text(i, value + .5, f'{value:.2f} giờ', ha='center')
    axes[1].axhline(24, color=PALETTE['red_strong'], ls='--')
    axes[1].set(xticks=[0, 1], xticklabels=['Dự toán', 'Đã ghi nhận'], ylim=(0, 26),
                ylabel='Giờ theo bộ đếm', title='(b) Đợt thu gọn đã hoàn thành')
    fig.text(.5, -.02, 'Hai thiết kế khác phạm vi. Các tổng đều gồm phần chuẩn bị trước, không phải phép đo thời gian kernel GPU thuần.', ha='center', fontsize=10)
    finalize_figure(fig, '08_cost')


def check_report(d):
    text = (ROOT / 'PROJECT_OVERVIEW_EXPERIMENT_REPORT.md').read_text()
    if ';' in text:
        raise ValueError('Report contains a semicolon')
    if re.findall(r'^## ([1-6])\. ', text, flags=re.M) != list('123456'):
        raise ValueError('Expected exactly six report sections')
    for link in re.findall(r'\]\((<[^>]+>|[^)\s]+)\)', text):
        link = link.strip('<>')
        if not link.startswith(('http:', 'https:', '#')) and not (ROOT / link.split('#')[0]).exists():
            raise ValueError('Broken report link: ' + link)
    for name in FIGURE_NAMES:
        for suffix in ('png', 'pdf'):
            if not (FIGURES / f'{name}.{suffix}').exists():
                raise ValueError('Missing figure: ' + name)
    manifest = json.loads((TABLES / 'sources.json').read_text())
    if manifest['files'] != d['sources'].files:
        raise ValueError('Input files changed since rendering')
    if manifest['generator_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('Figure generator changed since rendering')
    for name, table in make_tables(d).items():
        if (TABLES / f'{name}.csv').read_text() != table.to_csv(index=False):
            raise ValueError('Derived table changed: ' + name)
    real = d['edges'][d['edges'].source.isin(TASKS)]
    if not real.label.eq('chưa đủ bằng chứng').all():
        raise ValueError('Narrative evidence counts require updating')
    print('PASS: six sections, eight PNG/PDF pairs, live input and generator hashes, derived tables and report links')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    data = load_data()
    if args.check_only:
        check_report(data)
        return
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    tables = make_tables(data)
    for name, table in tables.items():
        table.to_csv(TABLES / f'{name}.csv', index=False)
    apply_publication_style()
    plot_dataset(data)
    plot_pipeline()
    plot_qwen(data)
    plot_learning(data)
    plot_image_blank(data, tables)
    plot_matrices(data)
    plot_effects(data)
    plot_cost(data)
    provenance = {'files': data['sources'].files, 'parameters': data['parameters'],
                  'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'style_reference': 'https://github.com/ChenLiu-1996/figures4papers',
                  'style_commit': '0ddfbd3fc9892e804a3fa01ae46bd0d32617f2aa',
                  'style_note': 'Independent matplotlib implementation following scientific-figure-making conventions',
                  'figures': list(FIGURE_NAMES), 'inference_or_training': False}
    (TABLES / 'sources.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
    print('Rendered eight figures and derived tables from saved results only.')
    print('Paired baseline comparison:\n' + tables['matched_baselines'].round(5).to_string(index=False))


if __name__ == '__main__':
    main()
