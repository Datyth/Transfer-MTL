"""Build a self-contained Stage 1 notebook with cached tables and charts."""

from __future__ import annotations

import base64
import contextlib
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _source(text: str) -> list[str]:
    return [line + "\n" for line in text.rstrip().split("\n")]


def _markdown(text: str, cell_id: str) -> dict:
    return {"cell_type": "markdown", "id": cell_id, "metadata": {}, "source": _source(text)}


def _code(text: str, cell_id: str, output: dict | None = None, execution_count: int | None = None) -> dict:
    return {
        "cell_type": "code", "id": cell_id, "metadata": {}, "source": _source(text),
        "execution_count": execution_count, "outputs": [output] if output else [],
    }


def _text_output(value: str, count: int) -> dict:
    return {"output_type": "execute_result", "execution_count": count, "metadata": {},
            "data": {"text/plain": _source(value)}}


def _image_output(fig: plt.Figure, count: int) -> dict:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return {"output_type": "execute_result", "execution_count": count, "metadata": {},
            "data": {"image/png": base64.b64encode(buffer.getvalue()).decode("ascii"),
                     "text/plain": ["<Stage 1 chart>"]}}


def _cache_execution(cells: list, root: Path) -> None:
    """Save outputs from executing the exact visible cell code."""
    namespace = {"__name__": "__main__", "_AUDIT_ROOT": root}
    count = 0
    for cell in cells:
        if cell["cell_type"] != "code":
            continue
        count += 1
        cell["execution_count"] = count
        stdout = io.StringIO()
        original_show = plt.show
        plt.close("all")
        plt.show = lambda *args, **kwargs: None
        try:
            with contextlib.redirect_stdout(stdout):
                exec(compile("".join(cell["source"]), f"<notebook:{cell['id']}>", "exec"), namespace)
            cell["outputs"] = []
            if stdout.getvalue():
                cell["outputs"].append({
                    "output_type": "stream", "name": "stdout",
                    "text": stdout.getvalue().splitlines(keepends=True),
                })
            for number in plt.get_fignums():
                cell["outputs"].append(_image_output(plt.figure(number), count))
        finally:
            plt.show = original_show
            plt.close("all")


def create_stage1_notebook(output_dir: Path, notebook_path: Path) -> None:
    """Create a valid ipynb from saved Stage 1 artifacts; no Jupyter dependency."""
    inventory = pd.read_csv(output_dir / "detailed_type_inventory.csv")
    operations = pd.read_csv(output_dir / "operation_catalogue.csv")
    candidates = pd.read_csv(output_dir / "candidate_counts.csv")
    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    split_order = ["train", "val", "testdev"]
    cells = [
        _markdown(
            "# GQA Stage 1 — dữ liệu và đề xuất quy tắc\n\n"
            "Notebook này là ảnh chụp kết quả Stage 1. Bảng và biểu đồ đã được lưu sẵn để xem mà không cần chạy lại. "
            "Ba tệp cấu hình vẫn ở trạng thái **PROPOSED**; chưa có tác vụ nào được cố định.\n\n"
            f"Source commit: `{manifest['git_commit']}`. Đầu vào và phiên bản thư viện nằm trong "
            "`gqa_audit/outputs/stage1/run_manifest.json`.",
            "intro",
        ),
        _code(
            "from pathlib import Path\n"
            "import pandas as pd\n"
            "import matplotlib.pyplot as plt\n"
            "ROOT = Path(globals().get('_AUDIT_ROOT', Path.cwd()))\n"
            "if not (ROOT / 'gqa_audit').exists(): ROOT = ROOT.parent\n"
            "OUT = ROOT / 'gqa_audit' / 'outputs' / 'stage1'\n"
            "inventory = pd.read_csv(OUT / 'detailed_type_inventory.csv')\n"
            "operations = pd.read_csv(OUT / 'operation_catalogue.csv')\n"
            "candidates = pd.read_csv(OUT / 'candidate_counts.csv')",
            "setup",
            execution_count=1,
        ),
    ]

    sizes = inventory.groupby("split", as_index=False)["count"].sum()
    sizes["split"] = pd.Categorical(sizes["split"], split_order, ordered=True)
    sizes = sizes.sort_values("split")
    cells += [
        _markdown("## Quy mô ba split", "split-title"),
        _code(
            "sizes = inventory.groupby('split', as_index=False)['count'].sum()\n"
            "print(sizes.to_string(index=False))",
            "split-table", _text_output(sizes.to_string(index=False), 2), 2,
        ),
    ]

    top = inventory.groupby("types_detailed")["count"].sum().nlargest(20).index
    pivot = inventory[inventory.types_detailed.isin(top)].pivot_table(
        index="types_detailed", columns="split", values="count", aggfunc="sum", fill_value=0
    ).reindex(top).reindex(columns=split_order, fill_value=0)
    fig, ax = plt.subplots(figsize=(11, 7))
    pivot.iloc[::-1].plot.barh(stacked=True, ax=ax)
    ax.set(xlabel="Questions", ylabel="types.detailed", title="20 detailed types nhiều câu hỏi nhất")
    fig.tight_layout()
    cells += [
        _markdown("## Phân bố `types.detailed`", "type-title"),
        _code(
            "top = inventory.groupby('types_detailed')['count'].sum().nlargest(20).index\n"
            "pivot = inventory[inventory.types_detailed.isin(top)].pivot_table(\n"
            "    index='types_detailed', columns='split', values='count', aggfunc='sum', fill_value=0\n"
            ").reindex(top).reindex(columns=['train', 'val', 'testdev'], fill_value=0)\n"
            "ax = pivot.iloc[::-1].plot.barh(stacked=True, figsize=(11, 7), title='20 detailed types nhiều câu hỏi nhất')\n"
            "ax.set(xlabel='Questions', ylabel='types.detailed')\n"
            "plt.tight_layout(); plt.show()",
            "type-chart", _image_output(fig, 3), 3,
        ),
    ]

    answers = inventory.groupby("types_detailed")[["yes_count", "no_count", "other_count"]].sum()
    answers = answers.loc[top]
    denominator = answers.sum(axis=1)
    fractions = answers.div(denominator, axis=0)
    fig, ax = plt.subplots(figsize=(11, 7))
    fractions.iloc[::-1].plot.barh(stacked=True, ax=ax, color=["#4c78a8", "#f58518", "#b8b8b8"])
    ax.set(xlabel="Fraction", ylabel="types.detailed", xlim=(0, 1), title="Yes / no / other theo detailed type")
    fig.tight_layout()
    cells += [
        _markdown("## Thành phần đáp án theo loại câu hỏi", "answers-title"),
        _code(
            "answers = inventory.groupby('types_detailed')[[\'yes_count\', \'no_count\', \'other_count\']].sum().loc[top]\n"
            "fractions = answers.div(answers.sum(axis=1), axis=0)\n"
            "ax = fractions.iloc[::-1].plot.barh(stacked=True, figsize=(11, 7), title='Yes / no / other theo detailed type')\n"
            "ax.set(xlabel='Fraction', ylabel='types.detailed', xlim=(0, 1))\n"
            "plt.tight_layout(); plt.show()",
            "answers-chart", _image_output(fig, 4), 4,
        ),
    ]

    head_counts = operations.drop_duplicates(["split", "head"])
    head_top = head_counts.groupby("head")["head_count"].sum().nlargest(15).index
    head_pivot = head_counts[head_counts["head"].isin(head_top)].pivot_table(
        index="head", columns="split", values="head_count", aggfunc="sum", fill_value=0
    ).reindex(head_top).reindex(columns=split_order, fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 6))
    head_pivot.iloc[::-1].plot.barh(stacked=True, ax=ax)
    ax.set(xlabel="Semantic steps", ylabel="Operation head", title="15 operation heads phổ biến nhất")
    fig.tight_layout()
    cells += [
        _markdown("## Các thao tác trong chương trình suy luận", "operation-title"),
        _code(
            "head_counts = operations.drop_duplicates(['split', 'head'])\n"
            "head_top = head_counts.groupby('head')['head_count'].sum().nlargest(15).index\n"
            "head_pivot = head_counts[head_counts['head'].isin(head_top)].pivot_table(\n"
            "    index='head', columns='split', values='head_count', aggfunc='sum', fill_value=0\n"
            ").reindex(head_top).reindex(columns=['train', 'val', 'testdev'], fill_value=0)\n"
            "ax = head_pivot.iloc[::-1].plot.barh(stacked=True, figsize=(10, 6), title='15 operation heads phổ biến nhất')\n"
            "ax.set(xlabel='Semantic steps', ylabel='Operation head')\n"
            "plt.tight_layout(); plt.show()",
            "operation-chart", _image_output(fig, 5), 5,
        ),
    ]

    impact = candidates.groupby("task")[["eligible_yesno_nonempty", "R_strict_removed", "R_broad_removed"]].sum()
    impact = impact.loc[[task for task in ("exist", "verifyAttr", "compare") if task in impact.index]]
    fig, ax = plt.subplots(figsize=(8, 4))
    impact[["R_strict_removed", "R_broad_removed"]].plot.bar(ax=ax)
    ax.set(xlabel="Pilot task", ylabel="Questions removed", title="Tác động của hai định nghĩa relation")
    fig.tight_layout()
    cells += [
        _markdown(
            "## Ảnh hưởng của bộ lọc relation\n\n"
            "Mẫu số là câu hỏi yes/no có chương trình không rỗng trong các nhóm dự kiến. "
            "Các con số này chỉ hỗ trợ duyệt quy tắc; chưa chọn định nghĩa chính thức.",
            "relation-title",
        ),
        _code(
            "impact = candidates.groupby('task')[[\'eligible_yesno_nonempty\', \'R_strict_removed\', \'R_broad_removed\']].sum()\n"
            "impact = impact.loc[[task for task in ['exist', 'verifyAttr', 'compare'] if task in impact.index]]\n"
            "print(impact.to_string())",
            "relation-table", _text_output(impact.to_string(), 6), 6,
        ),
        _code(
            "ax = impact[['R_strict_removed', 'R_broad_removed']].plot.bar(figsize=(8, 4), title='Tác động của hai định nghĩa relation')\n"
            "ax.set(xlabel='Pilot task', ylabel='Questions removed')\n"
            "plt.tight_layout(); plt.show()",
            "relation-chart", _image_output(fig, 7), 7,
        ),
        _markdown(
            "## Tệp để duyệt\n\n"
            "- `gqa_audit/config/task_rules.PROPOSED.yaml`\n"
            "- `gqa_audit/config/op_family_map.PROPOSED.yaml`\n"
            "- `gqa_audit/outputs/stage1/STAGE1_SUMMARY.md`\n"
            "- `gqa_audit/outputs/stage1/relation_matches.csv`\n\n"
            "**Dừng tại đây để người nghiên cứu duyệt.**",
            "review-links",
        ),
    ]
    cells[-1:-1] = [
        _markdown(
            "## Kiểm tra eligibility sau khi sửa lỗi YAML\n\n"
            "PyYAML từng đọc yes/no không có dấu nháy thành boolean. Lần chạy này dùng chuỗi đã kiểm tra kiểu; "
            "số eligible được đối chiếu với bộ đếm đáp án và chương trình rỗng theo từng detailed type.",
            "validation-title",
        ),
        _code(
            "checks = pd.read_csv(OUT / 'validation_checks.csv')\n"
            "print(checks.groupby('status').size().to_string())\n"
            "print(candidates.groupby(['task', 'split'])[['raw_count', 'eligible', 'n_empty_program']].sum().to_string())",
            "validation-table",
        ),
        _markdown("## Quy mô tác vụ theo biến thể đề xuất (train)", "variants-title"),
        _code(
            "variants = pd.read_csv(OUT / 'variant_counts.csv')\n"
            "task_train = variants[(variants['level'] == 'task') & (variants['split'] == 'train')]\n"
            "print(task_train[['variant', 'task', 'questions', 'yes_ratio', 'exclusion_rate']].to_string(index=False))\n"
            "task_train.pivot(index='task', columns='variant', values='questions').plot.bar(figsize=(11, 5))\n"
            "plt.ylabel('Questions'); plt.tight_layout(); plt.show()",
            "variants-chart",
        ),
        _markdown(
            "## Cân bằng đáp án theo family (train, unfiltered)\n\n"
            "Family chỉ phục vụ kiểm toán. Các family một lớp được báo cờ; không có bước tái cân bằng tự động.",
            "families-title",
        ),
        _code(
            "family_rows = variants[(variants['level'] == 'family') & (variants['split'] == 'train') & (variants['variant'] == 'unfiltered')].set_index('family')\n"
            "family_rows = family_rows[family_rows['questions'] > 0]\n"
            "print(family_rows[['task', 'questions', 'yes', 'no', 'flag']].to_string())\n"
            "family_rows[['yes', 'no']].div(family_rows['questions'], axis=0).plot.barh(stacked=True, figsize=(10, 8))\n"
            "plt.xlabel('Fraction'); plt.tight_layout(); plt.show()",
            "families-chart",
        ),
    ]
    _cache_execution(cells, output_dir.parents[2])
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python (datpt_mtl)", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    }
    notebook_path.parent.mkdir(parents=True, exist_ok=True)
    notebook_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
