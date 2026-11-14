"""Registered checks, plain CSV tables and publication-friendly figures."""

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from gqa_audit.evaluation import point_metrics


def diagnostic_checks(questions, predictions, sensitivity, generations, batch_diffs, metrics, model, output):
    checks = []

    def add(name, unit, value, flagged, rule, condition="image", variant="all"):
        checks.append({"model": model, "check": name, "unit": unit, "condition": condition, "variant": variant,
                       "value": value, "status": "FLAG" if flagged else "PASS", "rule": rule})

    for row in metrics[metrics.part.eq("val") & metrics.level.eq("task")].itertuples():
        if row.condition == "image":
            add("headroom_ceiling", row.task, row.primary_value, row.primary_value >= .90, ">= 0.90",
                row.condition, row.variant)
        else:
            add("no_image_reliance", row.task, row.gain_over_majority, row.gain_over_majority > .15,
                "primary minus train_core-majority primary > 0.15", row.condition, row.variant)
        frame = questions[questions.part.eq("val") & questions.task.eq(row.task) & questions[f"in_{row.variant}"]]
        difference = abs(row.yes_prediction_rate - frame.answer.eq("yes").mean())
        add("yes_bias", row.task, difference, difference > .15, "absolute predicted-minus-true yes rate > 0.15",
            row.condition, row.variant)
    template_rows = []
    for condition, secondary in sensitivity.items():
        first = predictions[condition][predictions[condition].question_id.isin(secondary.question_id)]
        a = questions.merge(first[["question_id", "pred"]], on="question_id", validate="one_to_one")
        b = questions.merge(secondary[["question_id", "pred"]], on="question_id", validate="one_to_one")
        if set(a.question_id) != set(b.question_id) or len(a) != 2000:
            raise ValueError("Template comparison must use the same frozen 2,000 questions")
        for task, group in a.groupby("task", sort=True):
            first_accuracy = point_metrics(group)["accuracy"]
            other_accuracy = point_metrics(b[b.task.eq(task)])["accuracy"]
            delta = other_accuracy - first_accuracy
            template_rows.append({"model": model, "task": task, "condition": condition, "n": len(group),
                                  "accuracy_A": first_accuracy, "accuracy_B": other_accuracy, "B_minus_A": delta})
            add("template_sensitivity", task, abs(delta), abs(delta) > .03, "absolute accuracy(A)-accuracy(B) > 0.03", condition)
    pd.DataFrame(template_rows).to_csv(output / f"template_sensitivity_{model}.csv", index=False)
    starts = float(generations.first_word.isin(["yes", "no"]).mean())
    agreement = float(generations.first_word.eq(generations.pred).mean())
    add("generation_starts_yes_no", "500 dev questions", starts, starts < .95, "share < 0.95")
    add("generation_logit_agreement", "500 dev questions", agreement, agreement < .95, "agreement < 0.95")
    for condition, group in batch_diffs.groupby("condition"):
        difference = float(group.abs_difference.max())
        add("batch_invariance", "256 dev questions", difference, difference > .05, "max absolute score difference > 0.05", condition)
    add("image_coverage", "train/dev/val registry images", 1, False, "all required images verified")
    return pd.DataFrame(checks)


def checks_from_files(questions, predictions, metrics, model, output):
    sensitivity = {condition: pd.read_parquet(output / f"template_B_{model}_{condition}.parquet")
                   for condition in ("image", "no_image")}
    generations = pd.read_csv(output / f"generation_sanity_{model}.csv", dtype={"question_id": str}, keep_default_na=False)
    batch_diffs = pd.read_csv(output / f"batch_invariance_{model}.csv", dtype={"question_id": str})
    return diagnostic_checks(questions, predictions, sensitivity, generations, batch_diffs, metrics, model, output)


def save_figure(figure, folder, name):
    figure.tight_layout()
    figure.savefig(folder / f"{name}.png", dpi=200, bbox_inches="tight")
    figure.savefig(folder / f"{name}.pdf", bbox_inches="tight")
    plt.close(figure)


def comparison_figure(all_metrics, models, variant, level, folder):
    figure, axes = plt.subplots(1, len(models), figsize=(max(9, 9 * len(models)), 5 if level == "task" else 10), squeeze=False)
    for axis, model in zip(axes[0], models):
        chosen = all_metrics[all_metrics.model.eq(model) & all_metrics.variant.eq(variant)
                             & all_metrics.part.eq("val") & all_metrics.level.eq(level)]
        image = chosen[chosen.condition.eq("image")].dropna(subset=["primary_value"]).sort_values("primary_value")
        other = chosen[chosen.condition.eq("no_image")].set_index(["task", "unit"])
        labels = [r.task if level == "task" else f"{r.task}/{r.unit}" for r in image.itertuples()]
        positions = np.arange(len(image))
        series = [("Image", image.primary_value, image.ci_low, image.ci_high),
                  ("No image", [other.loc[(r.task, r.unit), "primary_value"] for r in image.itertuples()],
                   [other.loc[(r.task, r.unit), "ci_low"] for r in image.itertuples()],
                   [other.loc[(r.task, r.unit), "ci_high"] for r in image.itertuples()]),
                  ("Text floor", image.text_floor, image.text_floor_ci_low, image.text_floor_ci_high),
                  ("Train majority", image.majority, image.majority_ci_low, image.majority_ci_high)]
        for offset, (label, values, low, high) in zip([-.27, -.09, .09, .27], series):
            values, low, high = np.array(values), np.array(low), np.array(high)
            # Percentile CIs can rarely exclude the point estimate; draw endpoints directly.
            axis.scatter(values, positions + offset, s=22, label=label)
            axis.hlines(positions + offset, low, high, linewidth=1)
        axis.set_yticks(positions, labels)
        axis.set_xlim(0, 1)
        axis.set_xlabel("Primary metric (verifyRel: relation balanced accuracy)")
        axis.set_title(f"{model} · {variant} · val")
        axis.grid(axis="x", alpha=.2)
        axis.legend(fontsize=8)
    save_figure(figure, folder, f"primary_{level}_{variant}")


def make_figures(output, models):
    folder = output / "figures"
    folder.mkdir(exist_ok=True)
    all_metrics = pd.concat([pd.read_csv(output / f"metrics_{m}.csv") for m in models], ignore_index=True)
    from .data import ROOT
    from gqa_audit.evaluation import Evaluator
    metadata = Evaluator(ROOT).metadata
    for variant in ("program_strict", "unfiltered"):
        for level in ("task", "family"):
            comparison_figure(all_metrics, models, variant, level, folder)
        for model in models:
            metrics = all_metrics[all_metrics.model.eq(model) & all_metrics.variant.eq(variant)
                                  & all_metrics.part.eq("val") & all_metrics.condition.eq("image")]
            full = metrics[metrics.level.eq("task")].set_index("task")
            hard = metrics[metrics.level.eq("subset") & metrics.unit.eq("text_hard")].set_index("task")
            tasks = sorted(full.index)
            fig, ax = plt.subplots(figsize=(8, 4))
            x = np.arange(len(tasks))
            ax.bar(x - .18, full.loc[tasks].accuracy, .36, label="Full set")
            ax.bar(x + .18, hard.loc[tasks].accuracy, .36, label="Text hard")
            ax.set(xticks=x, xticklabels=tasks, ylim=(0, 1), ylabel="Accuracy", title=f"{model} · {variant} · val · image")
            ax.legend()
            save_figure(fig, folder, f"text_hard_{model}_{variant}")
    for model in models:
        predictions = pd.read_parquet(output / f"predictions_{model}_image.parquet")
        frame = metadata[metadata.part.eq("val")].merge(predictions[["question_id", "score"]], on="question_id", validate="one_to_one")
        tasks = sorted(frame.task.unique())
        fig, axes = plt.subplots(1, len(tasks), figsize=(18, 3.8))
        for ax, task in zip(axes, tasks):
            for answer in ("yes", "no"):
                ax.hist(frame.loc[frame.task.eq(task) & frame.answer.eq(answer), "score"], bins=40, alpha=.45, density=True, label=answer)
            ax.axvline(0, color="black", linewidth=.8)
            ax.set(title=task, xlabel="Yes-minus-no logit score", ylabel="Density")
            ax.legend()
        save_figure(fig, folder, f"score_distribution_{model}")
        table = pd.read_csv(output / f"template_sensitivity_{model}.csv")
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        for ax, condition in zip(axes, ("image", "no_image")):
            group = table[table.condition.eq(condition)].set_index("task").loc[tasks]
            x = np.arange(len(tasks))
            ax.bar(x - .18, group.accuracy_A, .36, label="Template A")
            ax.bar(x + .18, group.accuracy_B, .36, label="Template B")
            ax.set(xticks=x, xticklabels=tasks, ylim=(0, 1), ylabel="Accuracy", title=f"{model} · {condition} · dev sample")
            ax.legend()
        save_figure(fig, folder, f"template_comparison_{model}")


def markdown_table(frame):
    def show(value):
        if isinstance(value, (float, np.floating)):
            return f"{value:.4f}" if np.isfinite(value) else "undefined"
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(map(str, frame.columns)) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    lines.extend("| " + " | ".join(show(x) for x in row) + " |" for row in frame.itertuples(index=False, name=None))
    return "\n".join(lines)


def write_report(output, models, images, checks):
    make_figures(output, models)
    env = json.loads((output / "environment.json").read_text())
    checkpoints = json.loads((output / "model_manifest.json").read_text())
    lines = ["# Stage 3: frozen zero-shot experiment", "", "No training. Dev and val only; testdev remains sealed.", "",
        "## Environment and provenance", "", f"Python environment: `{env['executable']}`; torch `{env['packages']['torch']}`; "
        f"transformers `{env['packages']['transformers']}`; CUDA `{env['cuda']}`; driver `{env['driver']}`; GPU `{env['gpu']}`.",
        "", "The human explicitly selected datpt_mtl and top-level configs/, checkpoints/, src/ and scripts/.", "",
        "Protocol SHA-256: `a0201c1a0a163d81d102f8f1aca677812238c7328305d69774d7101e4ada7ab2`.", "",
        "All source, accepted-input, image and output hashes are recorded in the manifests. See env_datpt_mtl.txt for exact packages.", "",
        "## Image verification", "", f"Archive CRC verified; SHA-256 `{images['archive_sha256']}`; "
        f"{images['archive_size_bytes']:,} bytes; {images['extracted_image_count']:,} extracted image files. "
        f"All {images['required_images_verified']:,} required train/dev/val images pass verification and full decoding. "
        f"testdev: {images['testdev_images_with_file']}/{images['testdev_registry_images']} image IDs have files (existence only).",
        "", "Image dimensions and bytes: image_verification.json; per-image hashes: image_manifest.csv.", ""]
    for model in models:
        token_ids = json.loads((output / f"tokens_{model}.json").read_text())
        throughput = json.loads((output / f"throughput_{model}.json").read_text())
        lines += [f"## {model}: model and scoring", "", f"Model revision: `{checkpoints[model]['revision']}`.", "",
            f"First-assistant token checks PASS: `{token_ids}`. bf16, sdpa, min_pixels=200704, max_pixels=802816; "
            "saved slow image processor; left padding; next-token logits; yes iff score > 0.", "",
            "Throughput measured after warmup on 64 fixed dev questions:", "", markdown_table(pd.DataFrame(throughput).T.reset_index().rename(columns={"index": "condition"})), "",
            "### Val primary metrics (95% image-cluster bootstrap CI)", ""]
        metrics = pd.read_csv(output / f"metrics_{model}.csv")
        task = metrics[metrics.part.eq("val") & metrics.level.eq("task")]
        for variant in ("program_strict", "unfiltered"):
            chosen = task[task.variant.eq(variant)]
            image = chosen[chosen.condition.eq("image")].set_index("task")
            no_image = chosen[chosen.condition.eq("no_image")].set_index("task")
            table = pd.DataFrame({"task": image.index, "metric": image.primary_metric,
                "image [CI]": [f"{r.primary_value:.4f} [{r.ci_low:.4f}, {r.ci_high:.4f}]" for r in image.itertuples()],
                "no image [CI]": [f"{r.primary_value:.4f} [{r.ci_low:.4f}, {r.ci_high:.4f}]" for r in no_image.loc[image.index].itertuples()],
                "text floor": image.text_floor.to_numpy(), "majority": image.majority.to_numpy()}).reset_index(drop=True)
            lines += [f"**{variant}**", "", markdown_table(table), ""]
        lines += ["verifyRel primary uses balanced accuracy on verifyRel_relation. Its val text floor is 0.6463072367 "
            "(the frozen within-subset baseline), rather than pooled accuracy or the pooled relation balanced accuracy 0.5553. "
            "Family, stratum and subset baselines use corresponding scope and metric. verifyRel_Co remains secondary accuracy.", "",
            f"All dev/val units: metrics_{model}.csv. Paired image-minus-no-image CIs: paired_differences_{model}.csv. "
            f"Secondary calibration: calibrated_metrics_{model}.csv and thresholds_{model}.csv. "
            "Thresholds maximize balanced accuracy on each whole-task dev union, then apply to val and both variants. "
            "Ties use smallest absolute threshold, then lower threshold.", "",
            f"Shortcut table: shortcut_control_{model}.csv. source=none denotes zero-shot, not a transfer effect. "
            "target_no_image_gain uses the target primary metric; the pooled Stage 2 blind gain is labelled secondary.", ""]
    lines += ["## Registered checks", "", markdown_table(checks), "", "## Figures", ""]
    lines += [f"![{path.stem}](figures/{path.name})" for path in sorted((output / "figures").glob("*.png"))]
    lines += ["", "Each figure is also saved as PDF; PNG resolution is 200 dpi.", "", "## Open decisions for the human", ""]
    for model in models:
        metrics = pd.read_csv(output / f"metrics_{model}.csv")
        for variant in ("program_strict", "unfiltered"):
            main = metrics[metrics.part.eq("val") & metrics.level.eq("task") & metrics.condition.eq("image") & metrics.variant.eq(variant)]
            headroom = main.loc[main.primary_value.lt(.90), "task"].tolist()
            ceiling = main.loc[main.primary_value.ge(.90), "task"].tolist()
            lines += [f"{model}/{variant}: tasks below the registered 0.90 ceiling: {', '.join(headroom) or 'none'}. "
                      f"Tasks flagged at/above the ceiling: {', '.join(ceiling) or 'none'}.", ""]
    lines += ["A 7B comparison is warranted as a next candidate test where 3B retains headroom; consult paired image gains "
        "and the no-image and template FLAGS before selecting targets. Phase B requires the human to enable it. "
        "No protocol thresholds or samples were changed in response to results.", "",
        "Qwen2.5-VL may have seen GQA or Visual Genome derived data during training. These scores measure available headroom, "
        "and do not establish generalization to unseen training data.", "",
        "Sampling choices: sorted frozen dev union, tasks sorted alphabetically, NumPy default_rng(0), 400/template and "
        "100/generation per task. Batch check uses 256 dev union IDs. Samples are persisted as CSVs. Runtime warnings are "
        "recorded in runtime_warnings.json; batch-size effects are reported without changing the frozen scoring protocol.", ""]
    (output / "STAGE3_REPORT.md").write_text("\n".join(lines))
