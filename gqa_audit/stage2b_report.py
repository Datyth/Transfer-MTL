"""Stage 2b tables, publication figures and executed overview notebook."""

from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .notebook import _cache_execution, _code, _markdown
from .stage2_report import md_table
from .stage2b_data import PLAN_SHA256, REGISTRY_SHA256


def report_stage2b(output, tables, metadata, context):
    fig_dir = output / "figures"
    fig_dir.mkdir(exist_ok=True)
    provenance = json.dumps({"analysis_plan_sha256": PLAN_SHA256, "registry_sha256": REGISTRY_SHA256,
                             "input_hashes": context["hashes"]}, sort_keys=True)
    figures = []
    def save(fig, name):
        fig.tight_layout()
        fig.savefig(fig_dir / f"{name}.png", dpi=context["runtime"]["plot_dpi"], metadata={"Description": provenance})
        fig.savefig(fig_dir / f"{name}.pdf", metadata={"Title": name, "Subject": provenance, "CreationDate": None})
        plt.close(fig)
        figures.append(name)

    dash = tables["dash_rate_by_type"].groupby("detailed")[["n", "n_dash"]].sum()
    dash["rate"] = dash.n_dash / dash.n
    fig, ax = plt.subplots(figsize=(10, max(6, len(dash) * .25)))
    dash.rate.sort_values().plot.barh(ax=ax, color="#31688e")
    ax.set(xlabel="Fraction of programs with unresolved-object marker (-)", ylabel="Detailed type",
           title="Dash annotation rates: train_core + dev + val", xlim=(0, 1.03))
    save(fig, "dash_rate_by_type")

    tasks = list(context["task_rules"]["pilot_tasks"])
    counts = tables["question_overlap_counts"]
    matrix = counts[counts.part.eq("val")].pivot(index="source", columns="target", values="share").reindex(index=tasks, columns=tasks)
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(matrix, vmin=0, vmax=1, cmap="viridis")
    ax.set_xticks(range(len(tasks)), tasks, rotation=35, ha="right")
    ax.set_yticks(range(len(tasks)), tasks)
    ax.set(xlabel="Target task (val)", ylabel="Source task (train_core)", title="Share of questions sharing an operation subtype")
    for i in range(len(tasks)):
        for j in range(len(tasks)):
            value = matrix.iloc[i, j]
            ax.text(j, i, "—" if pd.isna(value) else f"{value:.1%}", color="white" if pd.isna(value) or value < .65 else "black", ha="center", va="center")
    fig.colorbar(im, ax=ax, label="Target questions sharing ≥ 1 non-select token")
    save(fig, "question_level_share")

    conf = tables["overlap_confounds"]
    val = conf[conf.part.eq("val")].copy()
    val["edge"] = val.source + " → " + val.target
    fig, axes = plt.subplots(2, 1, figsize=(12, 9))
    for ax, column, label in zip(axes, ["program_length_mean", "blind_accuracy"], ["Mean program length", "Question-only accuracy"]):
        pivot = val.pivot(index="edge", columns="shared_binary", values=column).rename(columns={False: "No shared operation", True: "Shared operation"})
        pivot.plot.bar(ax=ax, color=["#c78f43", "#31688e"], rot=40)
        ax.set(xlabel="", ylabel=label)
        ax.tick_params(axis="x", labelsize=8)
    save(fig, "overlap_confounds")

    flags = tables["preregistered_checks_family"]
    chosen = flags[flags.variant.eq("program_strict") & flags.part.eq("val")].sort_values("gain_over_majority")
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(chosen.family, chosen.gain_over_majority, color=np.where(chosen.status.eq("FLAG"), "#b94040", "#31688e"))
    ax.axvline(context["task_rules"]["thresholds"]["blind_baseline_margin_over_majority"], color="black", linestyle="--")
    ax.set(xlabel="Accuracy gain over training-majority predictor", title="Family-level question-only baseline: program_strict val")
    save(fig, "family_blind_gain")

    sections = [
        "# GQA Stage 2b analysis addendum",
        f"Source commit: {metadata['git_commit']}\n\nRegistry: {REGISTRY_SHA256}\n\nFrozen H-L plan: {PLAN_SHA256}",
        "## Preflight and immutability",
        "All pinned hashes and cache fingerprints passed. Stage 1 and Stage 2 were not rerun. "
        "Their output files and existing notebooks were hashed before and after this run; all bytes are unchanged. "
        "Testdev contributed assignment metadata only: no text, program or predictions were processed.",
        "## Regression targets (expected versus actual)",
        md_table(tables["regression_checks"], ["kind", "key", "field", "expected", "actual", "status"]),
        "## Subsets and answer balance",
        md_table(tables["analysis_subset_sizes"], ["subset", "variant", "task", "part", "n", "yes", "yes_ratio"]),
        "The 383 val not-cue exclusions intersect val text_hard in zero questions. The frozen blind model "
        "scores zero on text_hard by construction; this is a membership/scoring correctness check. "
        "Text-hard is conditional on this particular baseline and is not an independent test sample.",
        "## Missing Stage 2 diagnostics",
        "Detailed-type tables are annotation/structure audits. Predictive performance is reported by task/family/stratum; "
        "the three preregistered verifyRel type-specific recalls are explicitly class diagnostics. "
        "The dash-enabled model is a leakage demonstration and must not provide features to a VLM.",
        "### Program-structure baseline",
        md_table(tables["program_structure_baseline"], ["task", "part", "condition", "accuracy", "balanced_accuracy", "majority_accuracy", "reference_accuracy", "difference", "status"]),
        "Structure features use StandardScaler fit on train_core only, frozen C/solver/seed, numeric length/depth/relate count "
        "and frozen operation-family presence flags. Optional dash is the sole difference between fits. "
        "Reference differences above 0.01 are flagged without modifying settings; exact input feature columns are recorded in the CSV.",
        "### Models trained within verifyRel subsets",
        md_table(tables["verifyrel_within_subset_baselines"], ["variant", "subset", "part", "train_n", "n", "accuracy", "balanced_accuracy", "majority_accuracy"]),
        "### Per-class recall of the existing pooled verifyRel model",
        md_table(tables["verifyrel_pooled_class_recall"], ["variant", "part", "detailed", "n", "class_recall", "reference_recall"]),
        "### Family-level flags",
        md_table(flags[flags.status.eq("FLAG")], ["variant", "part", "task", "family", "n", "accuracy", "majority_accuracy", "gain_over_majority"]),
        "All family rows, dash expectations, descriptor UNSEEN counts, structure reference differences and regression checks "
        "appear in preregistered_checks.csv. A FLAG reports an observation and never changes frozen rules.",
        "## Question-level descriptors and overlap",
        f"Vocabulary size (program_strict train_core including select and negation indicators): {metadata['vocabulary_size']}. "
        "Arguments, IDs, detailed types, task/family labels and the dash marker never enter the token vocabulary. "
        "Task/family/answer columns in descriptor tables are audit metadata and are not model features.",
        "Binary overlap uses distinct non-select operation tokens. Continuous overlap sums source train_core document frequencies. "
        "These are raw counts; comparisons across differently sized source tasks require care. "
        "Vocabulary and source frequencies never use dev/val programs for fitting.",
        md_table(matrix.reset_index(), ["source"] + tasks),
        "### Contrast viability",
        md_table(tables["overlap_contrast_viability"], ["source", "target", "n_target", "n_sharing", "share", "status"]),
        "NO_CONTRAST means <5% or >95% sharing; the planned binary question-level contrast is not informative for that edge. "
        "Task-level overlap remains descriptive. OK does not establish a causal comparison.",
        "### Confounds in viable contrasts",
        md_table(conf, ["source", "target", "part", "shared_binary", "n", "program_length_mean", "depth_mean", "yes_ratio", "blind_accuracy"]),
        "Full family/stratum mixes are in overlap_confounds_mix.csv. Future analyses must account for these differences; "
        "no transfer model is fitted here.",
        "## Evaluation library demonstration",
        "All units report accuracy, balanced accuracy, yes-prediction rate and n. Confidence intervals resample images "
        "with replacement 1,000 times (seed 0), retaining all questions from a sampled image. "
        "A single-class unit has undefined balanced accuracy. verifyRel primary_value uses the relation-subset "
        "intersection; its primary_n and scope are explicit. Pooled accuracy remains available separately.",
        md_table(tables["demo_eval_blind"][tables["demo_eval_blind"].level.eq("task")],
                 ["variant", "part", "task", "n", "accuracy", "balanced_accuracy", "primary_n", "primary_metric", "primary_value", "ci_low", "ci_high"]),
        "The shortcut table needs actual text-hard edge scores; absent scores are marked MISSING instead of inferred. "
        "Its blind-gain column is explicitly pooled accuracy minus the training-majority accuracy, not a relation balanced-accuracy gain. "
        "No-image gains remain empty for Stage 3.",
        "## Manual review and leakage",
        "75 extra train_core verifyRel examples were sampled (25 each positive/Co/Cr, seed 0). human_ok remains empty. "
        "The original 300-row manual review is unchanged and is not automatically approved. "
        "entailment_leakage.csv distinguishes outside-balanced targets, self-links, split crossings and task crossings.",
        "## PASS / FLAG / INFO",
        md_table(tables["preregistered_checks"].groupby(["check", "status"]).size().reset_index(name="rows"), ["check", "status", "rows"]),
        "## Open decisions for the human",
        "- Review the original and supplementary manual samples and record human_ok in a separate review artifact.\n"
        "- Confirm the Stage 3 VLM and image/no-image evaluation protocol before viewing its val results.\n"
        "- Keep text-hard results alongside full results, and restrict the planned binary RQ2 contrast to viable edges.\n"
        "- Decide how later transfer models will account for the reported family, length, depth and language confounds.\n"
        "- Keep testdev sealed until the explicitly authorized final evaluation.",
        "## Reproduce",
        "```bash\nconda activate datpt_mtl\nOPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python -m gqa_audit stage2b --questions data/gqa/questions\n```",
    ]
    for name in figures:
        sections += [f"### {name}", f"![{name}](figures/{name}.png)"]
    (output / "STAGE2B_REPORT.md").write_text("\n\n".join(sections) + "\n")
    notebook_path = output.parents[2] / "notebooks/gqa_stage2b_analysis.ipynb"
    cells = [
        _markdown("# GQA Stage 2b — subsets, diagnostics and evaluation\n\n"
                  "Frozen H–L plan; Stage 1/2 outputs and registry remain unchanged. "
                  "Cached outputs below execute the visible cells. Testdev stays sealed.", "intro"),
        _code("from pathlib import Path\nimport pandas as pd\nimport matplotlib.pyplot as plt\n"
              "ROOT = Path(globals().get('_AUDIT_ROOT', Path.cwd()))\n"
              "if not (ROOT / 'gqa_audit').exists(): ROOT = ROOT.parent\n"
              "OUT = ROOT / 'gqa_audit/outputs/stage2b'", "setup"),
    ]
    for name in ("analysis_subset_sizes", "verifyrel_within_subset_baselines", "overlap_contrast_viability"):
        cells.append(_code(f"print(pd.read_csv(OUT / '{name}.csv').to_string(index=False))", name))
    for name in figures:
        cells.append(_code(f"fig, ax = plt.subplots(figsize=(12, 8))\n"
                           f"ax.imshow(plt.imread(OUT / 'figures/{name}.png'))\nax.axis('off')\nplt.tight_layout()\nplt.show()", name))
    _cache_execution(cells, output.parents[2])
    notebook_path.parent.mkdir(exist_ok=True)
    notebook_path.write_text(json.dumps({"cells": cells, "metadata": {"kernelspec": {
        "display_name": "Python (datpt_mtl)", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"}}, "nbformat": 4, "nbformat_minor": 5}, indent=1) + "\n")
    return figures, notebook_path
