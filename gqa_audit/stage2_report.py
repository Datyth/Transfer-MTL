"""Scientific figure exports, factual report and cached Stage 2 notebook."""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .notebook import _cache_execution, _code, _markdown


def md_table(frame, columns):
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for row in frame[columns].itertuples(index=False, name=None):
        values = []
        for value in row:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                values.append("")
            elif isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value).replace("|", "/").replace("\n", " "))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def create_stage2_report(output, notebook, stats, profiles, overlaps, baselines,
                         checks, logic, selected, metadata, context):
    fig_dir = output / "figures"
    fig_dir.mkdir(exist_ok=True)
    figures = []
    primary = context["task_rules"]["primary_variant"]
    tasks = list(context["task_rules"]["pilot_tasks"])
    variants = list(context["task_rules"]["audit_variants"])
    bundle = context["bundle"]
    provenance = json.dumps({"config_bundle_sha256": bundle, "config_hashes": context["hashes"]}, sort_keys=True)

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(fig_dir / f"{name}.png", dpi=context["runtime"]["plot_dpi"], metadata={"Description": provenance})
        fig.savefig(fig_dir / f"{name}.pdf", metadata={"Title": name, "Subject": provenance})
        plt.close(fig)
        figures.append(name)

    def heatmap(table, name, title, fmt=".2f", figsize=(8, 6)):
        fig, ax = plt.subplots(figsize=figsize)
        image = ax.imshow(table.to_numpy(dtype=float), aspect="auto", cmap="viridis")
        ax.set_xticks(range(len(table.columns)), table.columns, rotation=45, ha="right")
        ax.set_yticks(range(len(table.index)), table.index)
        ax.set_title(title)
        for i in range(len(table.index)):
            for j in range(len(table.columns)):
                ax.text(j, i, format(float(table.iloc[i, j]), fmt), ha="center", va="center", color="white", fontsize=8)
        fig.colorbar(image, ax=ax)
        save(fig, name)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, split in zip(axes.flat, ("train_core", "dev", "val", "testdev")):
        stats[(stats.level == "task") & (stats.split == split)].pivot(
            index="task", columns="variant", values="questions").reindex(tasks).plot.bar(ax=ax)
        ax.set(title=split, ylabel="Questions", xlabel="")
    save(fig, "task_sizes")
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, split in zip(axes, ("train_core", "dev", "val")):
        t = stats[(stats.level == "task") & (stats.variant == primary) & (stats.split == split)].set_index("task").reindex(tasks)
        pd.DataFrame({"yes": t.yes_ratio, "no": 1 - t.yes_ratio}).plot.bar(stacked=True, ax=ax)
        ax.set(title=split, ylim=(0, 1), ylabel="Answer fraction", xlabel="")
    save(fig, "answer_balance")
    train = selected[primary][selected[primary].analysis_split.eq("train_core")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for task in tasks:
        frame = train[train.task.eq(task)]
        axes[0].hist(frame.program_length, bins=np.arange(-.5, train.program_length.max() + 1.5), histtype="step", label=task)
        axes[1].hist(frame.depth.dropna(), bins=np.arange(-.5, train.depth.max() + 1.5), histtype="step", label=task)
    axes[0].set(xlabel="Program steps", ylabel="Questions", title="Program length, train_core")
    axes[1].set(xlabel="Longest dependency path (edges)", ylabel="Questions", title="DAG depth, train_core")
    axes[1].legend()
    save(fig, "program_length_depth")
    table = profiles[(profiles.level == "task") & (profiles.variant == primary) & (profiles.split == "train_core")].pivot(
        index="task", columns="operation_family", values="fraction").reindex(tasks)
    heatmap(table, "operation_profile", "Fraction containing each operation family")
    for variant in variants:
        for metric in overlaps.metric.unique():
            table = overlaps[(overlaps.variant == variant) & (overlaps.metric == metric)].pivot(
                index="task_i", columns="task_j", values="value").reindex(index=tasks, columns=tasks)
            heatmap(table, f"{variant}_{metric}", f"{variant}: {metric}")
    fig, axes = plt.subplots(1, len(variants), figsize=(12, 4), squeeze=False)
    for ax, variant in zip(axes.flat, variants):
        t = baselines[(baselines.level == "task") & (baselines.split == "val") & (baselines.variant == variant)].set_index("task").reindex(tasks)
        t[["accuracy", "majority_accuracy"]].plot.bar(ax=ax)
        ax.set(title=f"{variant}, val", ylim=(0, 1), ylabel="Accuracy", xlabel="")
    save(fig, "blind_baselines")
    pairs = logic[(logic.variant == primary) & (logic.split == "train_core")].groupby(["operator", "operand_pair"]).size().unstack(fill_value=0)
    heatmap(pairs, "logic_operand_pairs", "Logic operand pairs, train_core", fmt=".0f", figsize=(9, 4))
    fig, ax = plt.subplots(figsize=(8, 4))
    stats[(stats.level == "task") & (stats.split == "train_core")].pivot(
        index="task", columns="variant", values="filter_exclusion_rate").reindex(tasks).plot.bar(ax=ax)
    ax.axhline(context["task_rules"]["thresholds"]["max_filter_exclusion_rate"], color="black", linestyle="--")
    ax.set(ylim=(0, 1), ylabel="Fraction excluded", title="Relation-filter exclusion, train_core (exist cap waived)")
    save(fig, "filter_exclusion_rates")
    fig, axes = plt.subplots(1, len(variants), figsize=(12, 4), squeeze=False)
    for ax, variant in zip(axes.flat, variants):
        t = baselines[(baselines.level == "metric_subset") & (baselines.variant == variant)].copy()
        t["subset"] = t.split + "/" + t.unit
        t.set_index("subset")[["accuracy", "majority_accuracy"]].plot.bar(ax=ax)
        ax.set(title=variant, ylim=(0, 1), ylabel="Accuracy", xlabel="")
    save(fig, "verifyrel_Co_Cr_baselines")

    report = ["# Frozen GQA Stage 2 audit", "",
              f"Source commit: {metadata['git_commit']}", "",
              f"Registry SHA-256: {metadata['registry_sha256']}", "",
              f"Config bundle SHA-256: {bundle}", "", "## Frozen hashes", ""]
    report += [f"- {name}: {digest}" for name, digest in context["hashes"].items()]
    report += ["", "## Applied decisions", ""]
    report += [f"- {letter}: {decision}" for letter, decision in context["task_rules"]["decisions"].items()]
    report += [
        "", "## Integrity and split policy", "",
        "Input and frozen file hashes are verified. Locked task/stratum regression counts and the exact exist "
        "semantic/program membership cross-check must pass before baselines. No rules are adjusted to audit outcomes.", "",
        f"Dev contains {metadata['dev_images_count']:,} of {metadata['train_images_count']:,} train images: "
        "ceil(10% × image count), sorted image IDs, numpy.default_rng(seed=0), without replacement. "
        "No retry or family balancing is applied. The exact list and hash are in dev_images.json.", "",
        md_table(pd.read_csv(output / "split_image_overlap.csv"),
                 ["split_a", "split_b", "overlap_images", "images_a", "images_b"]), "",
        "cross_split_references.csv counts self references, original split crossings, the train_core/dev boundary "
        "and targets outside the balanced files. An absent balanced target is not counted as a split crossing.", "",
        "Parquet preserves question IDs as strings. Program depth is the longest number of dependency edges "
        "(a dependency-free select has depth 0); missing, cyclic or out-of-range dependencies yield NaN.", "",
        "Testdev is count-only: no text/program feature cache, model predictions, operand decomposition, answer-ratio "
        "analysis or operation/lexical analysis. Only frozen assignments, locked regression counts, registry IDs, "
        "and requested image/reference boundary checks use its records.", "",
        "## Task counts", "",
        md_table(stats[stats.level == "task"], ["variant", "split", "task", "questions", "images"]), "",
        "## Answer balance and strata", "",
        md_table(stats[(stats.level == "task") & (stats.split != "testdev")],
                 ["variant", "split", "task", "yes", "no", "yes_ratio", "filter_exclusion_rate"]), "",
        md_table(stats[(stats.level == "stratum") & (stats.split != "testdev")],
                 ["variant", "split", "task", "stratum", "questions", "yes_ratio"]), "",
        "Family statistics are in family_stats.csv. Empty relational exist families under program_strict "
        "are recorded as empty, not as nonempty single-class families.", "",
        "## Question-only baseline", "",
        "Each task/variant fits TF-IDF word 1–2 grams (min_df=2) and logistic regression (C=1, max_iter=2000) "
        "on train_core question strings only. Detailed types, programs, task and family labels never enter the "
        "feature matrix. Unit accuracies use the pooled task model. Majority labels come from the corresponding "
        "train_core task/family/stratum/subset, not from evaluation answers.", "",
        md_table(baselines[(baselines.level == "task") & (baselines.split == "val")],
                 ["variant", "task", "questions", "accuracy", "majority_accuracy", "gain_over_majority"]), "",
        "## verifyRel Co/Cr diagnostics", "",
        "relVerifyCop appears only in pooled metrics. Co/Cr subset class priors differ: raw accuracy and gain "
        "over the subset's training-majority baseline are both reported. A dash pointer is a program annotation "
        "observation and by itself does not prove visual object absence.", "",
        md_table(baselines[baselines.level == "metric_subset"],
                 ["variant", "split", "unit", "questions", "accuracy", "majority_accuracy", "gain_over_majority"]), "",
    ]
    dash = pd.read_csv(output / "verifyrel_dash_rates.csv")
    report += [
        md_table(dash[dash.variant == primary],
                 ["split", "detailed_type", "questions", "verify_rel_dash_rate", "any_program_dash_rate"]), "",
        "## Logic decomposition", "",
        md_table(stats[(stats.level == "task") & (stats.task == "logic") & (stats.split != "testdev")],
                 ["variant", "split", "questions", "both_exist_count", "both_exist_share", "unparseable_logic_count"]), "",
        "Terminal operand families describe reasoning, not task labels. Shared and nested subprograms keep "
        "their complete dependency indices. See logic_decomposition.csv and logic_operand_pairs.csv.", "",
        "## Pre-registered checks", "",
        md_table(checks.groupby(["check", "status", "waived"], dropna=False).size().rename("rows").reset_index(),
                 ["check", "status", "waived", "rows"]), "",
        "The observed exist exclusion rate remains FLAG with the explicit Decision A waiver. Testdev's 300-question "
        "value is informational under the frozen rules. Complete results are in preregistered_checks.csv.", "",
        "### Unwaived flags", "",
        md_table(checks[(checks.status == "FLAG") & ~checks.waived],
                 ["check", "variant", "split", "task", "unit", "observed", "threshold"]), "",
        "## Manual review and secondary sizes", "",
        "manual_review_sample.csv has up to 25 retained train questions per task/variant and up to 25 removed "
        "questions per filtered task, without replacement. Review allocation cycles equally across families up "
        "to capacity. This does not rebalance training. human_ok is empty. Zero available removed questions are "
        "reported in manual_sample_availability.csv. Secondary types have sizes only in secondary_sizes.csv.", "",
        "## Figures", "",
    ]
    for name in figures:
        report += [f"### {name}", "", f"![{name}](figures/{name}.png)", "", f"[PDF](figures/{name}.pdf)", ""]
    report += [
        "## Open decisions for the human", "",
        "- Review manual examples and record human_ok.",
        "- Record how the unwaived audit flags will be handled in subsequent transfer experiments; this audit "
        "does not change the frozen registry.",
        "- Review Co/Cr observations and baseline gains before assigning causal shortcut interpretations.", "",
        "## Reproduce", "", chr(96) * 3 + "bash", "conda activate datpt_mtl", "python -m pytest -q",
        "OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python -m gqa_audit stage2 --questions data/gqa/questions",
        "python -m gqa_audit.verify_stage2 --questions data/gqa/questions", chr(96) * 3, "",
    ]
    (output / "AUDIT_REPORT.md").write_text("\n".join(report))
    cells = [
        _markdown(f"# GQA frozen Stage 2\n\nConfig bundle: {bundle}\n\nRegistry: {metadata['registry_sha256']}\n\n"
                  "The cached outputs execute the visible code. Testdev contributes counts only.", "intro"),
        _code(
            "from pathlib import Path\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"
            "ROOT = Path(globals().get('_AUDIT_ROOT', Path.cwd()))\n"
            "if not (ROOT / 'gqa_audit').exists(): ROOT = ROOT.parent\n"
            "OUT = ROOT / 'gqa_audit/outputs/stage2'\n"
            "stats = pd.read_csv(OUT / 'task_stats.csv')\n"
            "checks = pd.read_csv(OUT / 'preregistered_checks.csv')\n"
            "baseline = pd.read_csv(OUT / 'blind_baseline.csv')", "setup"),
        _code("print(stats[stats['level'] == 'task'][['variant', 'split', 'task', 'questions']].to_string(index=False))\n"
              "print(checks.groupby(['check', 'status', 'waived']).size().to_string())", "counts-checks"),
        _code("print(baseline[(baseline['level'] == 'task') & (baseline['split'] == 'val')]["
              "['variant', 'task', 'accuracy', 'majority_accuracy', 'gain_over_majority']].to_string(index=False))", "baselines"),
    ]
    for name in ("task_sizes", "answer_balance", "filter_exclusion_rates", "blind_baselines",
                 "operation_profile", "logic_operand_pairs", "verifyrel_Co_Cr_baselines"):
        cells += [_markdown(f"## {name}", f"title-{name}"),
                  _code(f"fig, ax = plt.subplots(figsize=(12, 7))\n"
                        f"ax.imshow(plt.imread(OUT / 'figures/{name}.png'))\n"
                        "ax.axis('off'); plt.tight_layout(); plt.show()", name)]
    _cache_execution(cells, output.parents[2])
    notebook.write_text(json.dumps({
        "cells": cells, "nbformat": 4, "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python (datpt_mtl)", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
            "config_bundle_sha256": bundle, "config_hashes": context["hashes"],
        },
    }, indent=1) + "\n")
