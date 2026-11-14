"""H-L analysis addendum. Never reruns or rewrites Stage 1 or Stage 2."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .evaluation import Evaluator, shortcut_control_table
from .stage2 import majority_label
from .stage2_core import file_hash
from .stage2b_analysis import (dash_diagnostics, entailment_by_task, family_flags, manual_relation_samples,
                              question_overlap, relation_baselines, structure_baselines)
from .stage2b_data import (ROOT, PLAN_SHA256, REGISTRY_SHA256, checked_predictions, load_analysis_tables,
                          make_descriptors, make_subsets, preflight, regression_checks)
from .stage2b_report import report_stage2b


def snapshot_accepted(root):
    paths = []
    for stage in ("stage1", "stage2"):
        paths.extend((root / f"gqa_audit/outputs/{stage}").rglob("*"))
        paths.append(root / f"notebooks/gqa_{stage}_audit.ipynb")
    return {str(path.relative_to(root)): file_hash(path) for path in sorted(paths) if path.is_file()}


def save_csv(output, name, frame, context):
    saved = frame.copy()
    saved["analysis_plan_sha256"] = PLAN_SHA256
    saved["registry_sha256"] = REGISTRY_SHA256
    saved["stage2_config_bundle_sha256"] = context["bundle"]
    saved.to_csv(output / f"{name}.csv", index=False, lineterminator="\n")


def save_parquet(path, frame):
    table = pa.Table.from_pandas(frame, preserve_index=False)
    table = table.replace_schema_metadata({**(table.schema.metadata or {}), b"analysis_plan_sha256": PLAN_SHA256.encode(),
                                           b"registry_sha256": REGISTRY_SHA256.encode()})
    pq.write_table(table, path, compression="zstd")


def all_checks(tables):
    rows = []
    for r in tables["regression_checks"].to_dict("records"):
        rows.append({"check": "regression", "unit": f"{r['kind']}/{r['key']}/{r['field']}", "status": r["status"],
                     "observed": r["actual"], "expected": r["expected"]})
    for r in tables["dash_rate_by_type"].to_dict("records"):
        rows.append({"check": "dash_rate", "unit": f"{r['detailed']}/{r['part']}/{r['answer']}", "status": r["status"],
                     "observed": r["dash_rate"], "expected": r["expected_dash_rate"]})
    for r in tables["preregistered_checks_family"].to_dict("records"):
        rows.append({"check": "family_blind_gain", "unit": f"{r['variant']}/{r['part']}/{r['family']}", "status": r["status"],
                     "observed": r["gain_over_majority"], "expected": f"<= {r['threshold']}; n >= 100"})
    for r in tables["program_structure_baseline"].to_dict("records"):
        rows.append({"check": "structure_reference", "unit": f"{r['condition']}/{r['task']}/{r['part']}", "status": r["status"],
                     "observed": r["accuracy"], "expected": r["reference_accuracy"]})
    for r in tables["overlap_contrast_viability"].to_dict("records"):
        rows.append({"check": "overlap_contrast", "unit": f"{r['source']}->{r['target']}",
                     "status": "PASS" if r["status"] == "OK" else "INFO", "observed": r["share"], "expected": r["status"]})
    for r in tables["descriptor_unseen"].to_dict("records"):
        rows.append({"check": "descriptor_unseen", "unit": f"{r['variant']}/{r['part']}/{r['task']}",
                     "status": "INFO" if r["unseen_tokens"] else "PASS", "observed": r["unseen_tokens"], "expected": "UNSEEN mapped"})
    return pd.DataFrame(rows)


def run_stage2b(questions: Path) -> int:
    output = ROOT / "gqa_audit/outputs/stage2b"
    output.mkdir(parents=True, exist_ok=True)
    before = snapshot_accepted(ROOT)
    (output / "failure.json").unlink(missing_ok=True)
    try:
        print("Stage 2b: verifying frozen inputs and read-only cache fingerprints", flush=True)
        context, registry, preflight_result = preflight(ROOT, questions)
        (output / "preflight.json").write_text(json.dumps(preflight_result, indent=2) + "\n")
        for name in ("analysis_plan.FROZEN.yaml", "stage2b_runtime.yaml"):
            shutil.copyfile(ROOT / "gqa_audit/config" / name, output / name)
        raw, sealed, basic = load_analysis_tables(ROOT, context, registry)
        predictions = checked_predictions(ROOT / "gqa_audit/outputs/stage2/blind_predictions.csv", raw, registry)
        print(f"Stage 2b: loaded {len(raw):,} train/dev/val pilot records; testdev assignment metadata only", flush=True)
        tables = {}
        subsets, tables["analysis_subset_sizes"] = make_subsets(raw, predictions, context)
        (output / "analysis_subsets.json").write_text(json.dumps(subsets, sort_keys=True, indent=1, ensure_ascii=False) + "\n")
        descriptors, vocabulary, tables["descriptor_unseen"] = make_descriptors(raw)
        (output / "descriptor_vocabulary.json").write_text(json.dumps(vocabulary, indent=2, ensure_ascii=False) + "\n")
        save_parquet(output / "question_descriptors.parquet", descriptors)
        columns = ["question_id", "image_id", "part", "task", "family", "stratum", "in_program_strict", "in_unfiltered",
                   "answer", "program_length", "depth", "relation_steps"]
        registry_rows = pd.concat([raw[columns].rename(columns={"image_id": "imageId", "relation_steps": "n_relate"}), sealed], ignore_index=True)
        save_parquet(output / "registry_questions.parquet", registry_rows.sort_values("question_id"))
        text_hard = []
        for variant, tasks in subsets["subsets"]["text_hard"].items():
            for task, parts in tasks.items():
                for part, ids in parts.items():
                    frame = raw[raw.question_id.isin(ids)]
                    for family, chosen in frame.groupby("family", sort=True):
                        text_hard.append({"variant": variant, "task": task, "part": part, "family": family,
                                          "n": len(chosen), "yes": int(chosen.answer.eq("yes").sum()), "yes_ratio": chosen.answer.eq("yes").mean()})
        tables["text_hard_by_family"] = pd.DataFrame(text_hard)
        print("Stage 2b: computing question-level overlap and exact regression targets", flush=True)
        (tables["question_overlap_counts"], tables["overlap_contrast_viability"], tables["overlap_confounds"],
         tables["overlap_confounds_mix"], per_question) = question_overlap(descriptors, predictions, context)
        save_parquet(output / "question_overlap.parquet", per_question)
        tables["regression_checks"] = regression_checks(raw, subsets, vocabulary, tables["question_overlap_counts"], context)
        save_csv(output, "regression_checks", tables["regression_checks"], context)
        if not tables["regression_checks"].status.eq("PASS").all():
            failed = tables["regression_checks"][tables["regression_checks"].status.ne("PASS")]
            raise ValueError("Frozen regression target mismatch; STOP:\n" + failed.to_string(index=False))
        print(f"Stage 2b: {len(tables['regression_checks'])} exact regression checks PASS", flush=True)
        tables["dash_rate_by_type"], tables["program_structure_by_type"] = dash_diagnostics(raw, context)
        tables["preregistered_checks_family"] = family_flags(predictions, raw, context)
        tables["manual_review_verifyrel"] = manual_relation_samples(raw, context)
        tables["entailment_leakage"] = entailment_by_task(basic, raw, context)
        print("Stage 2b: fitting diagnostic structure and within-subset question-only baselines", flush=True)
        tables["program_structure_baseline"], tables["program_structure_predictions"] = structure_baselines(raw, context)
        (tables["verifyrel_within_subset_baselines"], tables["verifyrel_pooled_class_recall"],
         tables["verifyrel_within_subset_predictions"]) = relation_baselines(raw, predictions, subsets, context)
        tables["preregistered_checks"] = all_checks(tables)
        print("Stage 2b: demonstrating frozen evaluation with 1,000 image-cluster bootstrap resamples", flush=True)
        scorer = Evaluator(ROOT, metadata=registry_rows, registry=registry, subsets=subsets, plan=context["analysis_plan"], questions=questions)
        blind_scores, majority_scores = [], []
        for variant in context["task_rules"]["audit_variants"]:
            pred = predictions[predictions.variant.eq(variant)][["question_id", "prediction"]].rename(columns={"prediction": "pred"})
            blind_scores.append(scorer.evaluate(pred, variant, ["dev", "val"]))
            labels = {task: majority_label(raw.loc[raw[f"in_{variant}"] & raw.part.eq("train_core") & raw.task.eq(task), "answer"])
                      for task in context["task_rules"]["pilot_tasks"]}
            majority_pred = predictions[predictions.variant.eq(variant)][["question_id", "task"]].copy()
            majority_pred["pred"] = majority_pred.task.map(labels)
            majority_scores.append(scorer.evaluate(majority_pred[["question_id", "pred"]], variant, ["dev", "val"]))
        tables["demo_eval_blind"] = pd.concat(blind_scores, ignore_index=True)
        tables["demo_eval_majority"] = pd.concat(majority_scores, ignore_index=True)
        hard_scores = tables["demo_eval_blind"].query("level == 'subset' and unit == 'text_hard'")
        if not hard_scores.accuracy.eq(0).all() or len(hard_scores) != 20:
            raise ValueError("Blind text-hard demonstration must have exactly 20 zero-accuracy units")
        edges = []
        for row in tables["demo_eval_blind"].itertuples():
            if row.part == "val" and (row.level == "task" or row.unit == "text_hard"):
                edges.append({"source": "none", "target": row.task, "condition": "blind_demo", "variant": row.variant,
                              "part": row.part, "metric": row.primary_metric, "value": row.primary_value,
                              "ci": (row.ci_low, row.ci_high), "subset": "text_hard" if row.unit == "text_hard" else "main"})
        tables["demo_shortcut_control"] = shortcut_control_table(edges, ROOT)
        for name, table in tables.items():
            save_csv(output, name, table, context)
        print("Stage 2b: running complete pytest suite", flush=True)
        result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        (output / "pytest_report.txt").write_text(result.stdout)
        print(result.stdout, flush=True)
        if result.returncode:
            raise ValueError("Pytest failed; see pytest_report.txt")
        metadata = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    "registry_sha256": REGISTRY_SHA256, "analysis_plan_sha256": PLAN_SHA256,
                    "analysis_subsets_sha256": subsets["analysis_subsets_sha256"], "vocabulary_size": len(vocabulary["tokens"]),
                    "vocabulary_sha256": vocabulary["vocabulary_sha256"], "input_hashes": context["input_hashes_stage2b"],
                    "package_versions": {package: version(package) for package in (
                        "ijson", "pandas", "numpy", "pyarrow", "scikit-learn", "matplotlib", "PyYAML", "pytest")},
                    "sealed_testdev": {"text_rows": 0, "program_rows": 0, "predictions": 0, "final_mode_called": False},
                    "expected_regressions": len(tables["regression_checks"]), "pytest_exit_code": result.returncode}
        figures, notebook = report_stage2b(output, tables, metadata, context)
        if snapshot_accepted(ROOT) != before:
            raise ValueError("Accepted Stage 1/2 outputs changed during Stage 2b")
        metadata["accepted_stage1_stage2_snapshot"] = before
        metadata["accepted_outputs_unchanged"] = True
        metadata["source_hashes"] = {str(path.relative_to(ROOT)): file_hash(path) for path in sorted((ROOT / "gqa_audit").glob("*.py"))}
        metadata["test_hashes"] = {str(path.relative_to(ROOT)): file_hash(path) for path in sorted((ROOT / "tests").glob("*.py"))}
        metadata["notebook_sha256"] = file_hash(notebook)
        metadata["artifacts"] = {str(path.relative_to(output)): file_hash(path) for path in sorted(output.rglob("*"))
                                 if path.is_file() and path.name not in ("run_manifest.json", "independent_verification.json")}
        metadata["manifest_self_hash_policy"] = "Manifest excludes itself; independent_verification.json is a later verifier result."
        (output / "run_manifest.json").write_text(json.dumps(metadata, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
        print(f"Stage 2b complete: {output}; {len(figures)} PNG/PDF figure pairs", flush=True)
        return 0
    except Exception as exc:
        unchanged = snapshot_accepted(ROOT) == before
        failure = {"status": "FAIL", "error": str(exc), "accepted_outputs_unchanged": unchanged}
        (output / "failure.json").write_text(json.dumps(failure, indent=2, ensure_ascii=False) + "\n")
        traceback.print_exc()
        return 1
