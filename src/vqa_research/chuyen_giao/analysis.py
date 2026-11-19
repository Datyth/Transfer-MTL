"""Study reports, gate decisions and directed evidence labels."""
import json

import numpy as np
import pandas as pd

from gqa_audit.evaluation import point_metrics, probabilistic_metrics
from .core import OUT, ROOT, TASKS, FAMILIES, NAMES, SPEC, atomic, shuffled_control


def frame(data, job, path, subset=None):
    ids = data.evaluation(job['level'], job['target'], job['split'], subset)
    p = pd.read_parquet(path / 'predictions.parquet')
    metadata = data.by_id.loc[ids, ['question_id', 'image_id', 'answer', 'part']].reset_index(drop=True)
    f = metadata.rename(columns={'image_id': 'imageId'}).merge(p, on='question_id', validate='one_to_one')
    if len(f) != len(ids):
        raise ValueError('Missing evaluation predictions')
    return f


def metrics(f, balanced=False):
    m = point_metrics(f)
    return {'primary': m['balanced_accuracy' if balanced else 'accuracy'],
            **probabilistic_metrics(f, class_balanced=balanced)}


def gates(data, entries):
    rows = []
    for job, path in entries:
        rows.append({**job, **metrics(frame(data, job, path), job['target'] == 'verifyRel')})
    table = pd.DataFrame(rows)
    table.to_csv(OUT / 'gate_metrics.csv', index=False)
    from ..probe.gates import gate_table
    result = gate_table(table[~table.blank], table[table.blank], ROOT)
    result.to_csv(OUT / 'gates.csv', index=False)
    return result


def adjust_p(values, method):
    p = np.asarray(values, dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    n = len(p)
    adjusted = (np.maximum.accumulate(ranked * (n - np.arange(n))) if method == 'holm'
                else np.minimum.accumulate((ranked * n / np.arange(1, n + 1))[::-1])[::-1])
    out = np.empty(n)
    out[order] = np.minimum(1., adjusted)
    return out


def label(mean, low, high, delta, positive_fraction, negative_fraction,
          adjusted_positive_p, adjusted_negative_p, placebo_ok, subset_ok):
    if (low > delta and positive_fraction >= .8 and adjusted_positive_p <= .05
            and placebo_ok and subset_ok):
        return 'hỗ trợ'
    if high < -delta and negative_fraction >= .8 and adjusted_negative_p <= .05:
        return 'gây hại'
    return 'chưa đủ bằng chứng'


def report(data, entries, thresholds, primary, source_paths=None, exploratory=False):
    from gqa_audit.evaluation import study_contrast
    lookup = {tuple(j.get(k) for k in ('level', 'target', 'budget', 'seed', 'blank', 'disjoint', 'arm', 'source')):
              (j, p) for j, p in entries}
    groups = {}
    point_rows = []
    for job, path in entries:
        balanced = job['level'] == 'group' and job['target'] == 'verifyRel'
        point_rows.append({**job, **metrics(frame(data, job, path), balanced)})
        if job['arm'] != 'B':
            key = tuple(job[k] for k in ('level', 'target', 'budget', 'blank', 'disjoint', 'arm', 'source'))
            groups.setdefault(key, []).append((job, path))
    pd.DataFrame(point_rows).to_csv(OUT / 'metrics.csv', index=False)
    zero = []
    for path in (source_paths or {}).values():
        job = json.loads((path / 'run.json').read_text())['config']['job']
        for target in (TASKS if job['level'] == 'group' else FAMILIES):
            zero.append({**job, 'target': target, **metrics(frame(data, {**job, 'target': target}, path),
                        job['level'] == 'group' and target == 'verifyRel')})
    pd.DataFrame(zero).to_csv(OUT / 'source_only_metrics.csv', index=False)
    results = []
    for key, arms in groups.items():
        level, target, budget, blank, disjoint, arm, source = key
        balanced = level == 'group' and target == 'verifyRel'
        def collect(which, subset=None):
            fs = []
            for j, p in arms:
                if which == 'B':
                    j, p = lookup[(level, target, budget, j['seed'], blank, False, 'B', '')]
                elif which != 'A':
                    j, p = lookup[(level, target, budget, j['seed'], blank, False, arm, which)]
                fs.append(frame(data, j, p, subset))
            return fs
        a, b = collect('A'), collect('B')
        contrast = study_contrast(a, b, balanced=balanced, delta=thresholds[level], metric=primary)
        loss_contrast = study_contrast(a, b, balanced=balanced, metric='log_loss')
        placebo_ok = True
        is_real = source in (TASKS if level == 'group' else FAMILIES)
        placebo = {}
        if is_real:
            for name in ('placebo', shuffled_control(level, target)):
                comp = study_contrast(a, collect(name), balanced=balanced, metric=primary)
                placebo[name] = comp
                placebo_ok &= comp['ci_low'] > 0
        hard_a, hard_b = collect('A', 'text_hard'), collect('B', 'text_hard')
        subset_ok = False
        hard = None
        if all(len(x) and x.answer.nunique() == 2 for x in hard_a + hard_b):
            hard = study_contrast(hard_a, hard_b, balanced=balanced, metric=primary)
            subset_ok = hard['ci_low'] > 0
        row = dict(level=level, target=target, budget=budget, blank=blank, disjoint=disjoint,
                   arm=arm, source=source, **contrast, delta=thresholds[level],
                   evidence_level='exploratory' if exploratory else 'main_study',
                   log_loss_gain_mean=loss_contrast['mean'],
                   log_loss_gain_ci_low=loss_contrast['ci_low'],
                   log_loss_gain_ci_high=loss_contrast['ci_high'],
                   placebo_ok=bool(placebo_ok), subset_ok=bool(subset_ok), text_hard=hard,
                   placebo_comparisons=placebo)
        if level == 'group' and target == 'logic':
            la, lb = collect('A', 'logic_no_not_cue'), collect('B', 'logic_no_not_cue')
            row['logic_no_not_cue'] = study_contrast(la, lb, metric=primary)
        row['primary_test'] = (not exploratory and level == 'group' and not blank and not disjoint and arm == 'Seq'
                               and budget == 1000 and [source, target] in SPEC['primary_edges'])
        results.append(row)
        atomic(OUT / 'contrasts_progress.json', {'completed': len(results), 'total': len(groups)})
    for confirm in (True, False):
        # Separate levels and directions of the hypothesis tests. Controls are reported,
        # not added to the set of scientific source -> target hypotheses.
        for level in ('group', 'family'):
            rows = [r for r in results if r['primary_test'] == confirm and r['level'] == level
                    and r['source'] in (TASKS if level == 'group' else FAMILIES)]
            for name in ('p_positive', 'p_negative'):
                for r, p in zip(rows, adjust_p([r[name] for r in rows], 'holm' if confirm else 'bh')):
                    r['adjusted_' + name] = float(p)
    for r in results:
        r['label'] = label(r['mean'], r['ci_low'], r['ci_high'], r['delta'],
            r['positive_fraction'], r['negative_fraction'], r.get('adjusted_p_positive', 1.),
            r.get('adjusted_p_negative', 1.), r['placebo_ok'], r['subset_ok'])
        if r['source'] not in (TASKS if r['level'] == 'group' else FAMILIES):
            r['label'] = 'đối chứng'
    atomic(OUT / 'edges.json', {'metric': primary, 'thresholds': thresholds,
           'evidence_level': 'exploratory' if exploratory else 'main_study', 'edges': results})
    pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, dict)} for r in results]).to_csv(
        OUT / 'edges.csv', index=False)
    draw(results)
    lines = ['# Bản đồ chuyển giao bằng CLIP ViT-L/14', '',
             ('Thí nghiệm thăm dò trên tập phát triển. Bộ kiểm chứng đầy đủ chất lượng mô hình chưa được chạy. '
              'Kết quả chưa chứng minh quan hệ hỗ trợ tổng quát và chưa được xác nhận trên tập độc lập.'
              if exploratory else 'Đánh giá trên tập xác nhận. Qwen được để sang đợt sau.'), '',
             'Màu biểu thị mức thay đổi so với học riêng. Nhãn ghi mức bằng chứng sau đối chứng.', '']
    if exploratory:
        baselines = pd.DataFrame([r for r in point_rows if r['arm'] == 'B'])
        lines += ['## Mốc học riêng', '', '| Nhóm | Điểm trung bình | Độ lệch chuẩn |', '|---|---:|---:|']
        for target, group in baselines.groupby('target'):
            lines.append(f'| {NAMES.get(target, target)} | {group.primary.mean():.2%} | {group.primary.std(ddof=1):.2%} |')
        lines += ['', '## Các hướng chuyển giao', '',
                  '| Nguồn | Đích | Cách học | Mức tăng điểm phần trăm | Khoảng tin cậy 95% | Kết luận thăm dò |',
                  '|---|---|---|---:|---|---|']
        for r in results:
            if r['source'] in TASKS:
                method = 'Học lần lượt' if r['arm'] == 'Seq' else 'Học chung'
                lines.append(f'| {NAMES[r["source"]]} | {NAMES[r["target"]]} | {method} | '
                             f'{100*r["mean"]:+.2f} | [{100*r["ci_low"]:+.2f}, {100*r["ci_high"]:+.2f}] | {r["label"]} |')
        lines += ['', 'Độ chính xác cân bằng được dùng cho nhóm quan hệ, độ chính xác thông thường cho các nhóm khác.',
                  'Mốc cải thiện tối thiểu được đặt trước ở một điểm phần trăm. Ba lần khởi tạo phải cùng chiều để đạt quy tắc 80%.',
                  'Không có bản sao ma trận dùng ảnh trắng hoặc nguồn tách ảnh. Không diễn giải kết quả này thành bằng chứng chắc chắn về chuyển giao thị giác.', '']
    for level in sorted({j['level'] for j, _ in entries}):
        selected = [r for r in results if r['level'] == level and r['label'] in ('hỗ trợ', 'gây hại')
                    and not r['blank'] and not r['disjoint']]
        lines += [f'## {"Năm nhóm nhiệm vụ" if level == "group" else "Mười bốn họ câu hỏi"}', '',
                  f'Số kết quả có bằng chứng: {len(selected)}.', '']
        for r in selected:
            lines.append(f'- {r["source"]} → {r["target"]}, {r["arm"]}, {r["budget"]} câu: '
                         f'{r["mean"]:.4f}, khoảng tin cậy [{r["ci_low"]:.4f}, {r["ci_high"]:.4f}], {r["label"]}.')
    (OUT / 'BAO_CAO.md').write_text('\n'.join(lines) + '\n')


def draw(results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figures = OUT / 'figures'
    figures.mkdir(exist_ok=True)
    for level, names, budgets in [('group', TASKS, (250, 1000, 4000)), ('family', FAMILIES, (500,))]:
        if not any(r['level'] == level for r in results):
            continue
        for arm in ('Seq', 'Joint'):
            for budget in budgets:
                selected = [r for r in results if r['level'] == level and r['arm'] == arm
                            and r['budget'] == budget and not r['blank'] and not r['disjoint']
                            and r['source'] in names]
                if not selected:
                    continue
                values = np.full((len(names), len(names)), np.nan)
                for r in selected:
                    values[names.index(r['source']), names.index(r['target'])] = r['mean']
                fig, ax = plt.subplots(figsize=(10, 8))
                limit = max(.01, float(np.nanmax(np.abs(values))))
                im = ax.imshow(values, cmap='RdBu', vmin=-limit, vmax=limit)
                labels = [NAMES.get(n, n) for n in names]
                ax.set(xticks=range(len(names)), yticks=range(len(names)), xticklabels=labels,
                       yticklabels=labels, xlabel='Nhiệm vụ đích', ylabel='Nhiệm vụ nguồn',
                       title=f'{"Học lần lượt" if arm == "Seq" else "Học chung"}, {budget} câu đích')
                plt.setp(ax.get_xticklabels(), rotation=60, ha='right')
                fig.colorbar(im, ax=ax, label='Mức cải thiện so với học riêng')
                fig.tight_layout()
                for suffix in ('png', 'pdf'):
                    fig.savefig(figures / f'{level}_{arm}_{budget}.{suffix}', dpi=200)
                plt.close(fig)
                # Directed map includes every direction, including inconclusive ones.
                graph = ['digraph BanDo {', 'rankdir=LR']
                for n in names:
                    graph.append(f'"{n}" [label="{NAMES.get(n, n)}"]')
                for r in selected:
                    color = {'hỗ trợ': 'green', 'gây hại': 'red'}.get(r['label'], 'gray')
                    graph.append(f'"{r["source"]}" -> "{r["target"]}" '
                                 f'[color="{color}", label="{r["mean"]:+.3f} | {r["label"]}"]')
                graph.append('}')
                (figures / f'{level}_{arm}_{budget}.dot').write_text('\n'.join(graph) + '\n')
                fig, ax = plt.subplots(figsize=(11, 11))
                angle = np.arange(len(names)) * 2 * np.pi / len(names)
                positions = dict(zip(names, np.column_stack((np.cos(angle), np.sin(angle)))))
                for r in selected:
                    color = {'hỗ trợ': 'green', 'gây hại': 'red'}.get(r['label'], 'gray')
                    known = r['label'] != 'chưa đủ bằng chứng'
                    ax.annotate('', xy=positions[r['target']], xytext=positions[r['source']],
                                arrowprops=dict(arrowstyle='->', color=color,
                                    alpha=.85 if known else .1, lw=1.5 if known else .4,
                                    shrinkA=15, shrinkB=15, connectionstyle='arc3,rad=0.08'))
                for name, (x, y) in positions.items():
                    ax.scatter(x, y, s=240, color='lightblue', zorder=3)
                    ax.text(x * 1.18, y * 1.18, NAMES.get(name, name), ha='center', va='center', fontsize=9)
                ax.set(xlim=(-1.5, 1.5), ylim=(-1.5, 1.5), aspect='equal',
                       title='Xanh: hỗ trợ | Đỏ: gây hại | Xám: chưa đủ bằng chứng')
                ax.axis('off')
                fig.tight_layout()
                for suffix in ('png', 'pdf'):
                    fig.savefig(figures / f'{level}_{arm}_{budget}_directions.{suffix}', dpi=200)
                plt.close(fig)
