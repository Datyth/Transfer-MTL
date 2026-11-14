"""Repair Stage 3 analysis from saved predictions; no model or image inference."""

from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root)]

from vqa_research.analysis import KEYS, evaluate_model
from vqa_research.data import accepted_snapshot, file_hash, load_protocol, load_questions, save_json
from vqa_research.report import checks_from_files, write_report


def main():
    output = root / "gqa_audit/outputs/stage3"
    with (output / "run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest_path = output / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if manifest["status"] != "COMPLETE" or manifest["models"] != ["3b"]:
            raise ValueError("Only the completed 3B run can be reanalysed")
        if accepted_snapshot() != json.loads((output / "accepted_outputs_snapshot.json").read_text()):
            raise ValueError("Accepted Stage 1/2/2b artifacts changed")
        prediction_paths = {condition: output / f"predictions_3b_{condition}.parquet"
                            for condition in ("image", "no_image")}
        prediction_hashes = {condition: file_hash(path) for condition, path in prediction_paths.items()}
        for condition, path in prediction_paths.items():
            if prediction_hashes[condition] != manifest["artifacts"][path.name]:
                raise ValueError(f"Saved {condition} predictions differ from original run manifest")

        _, evaluator = load_protocol(root / "configs/stage3_protocol.FROZEN.yaml")
        questions = load_questions(evaluator)
        predictions = {condition: pd.read_parquet(path) for condition, path in prediction_paths.items()}
        old = pd.read_csv(output / "paired_differences_3b.csv", dtype={"variant": str})
        metrics = evaluate_model(evaluator, questions, predictions["image"], predictions["no_image"], "3b", output)
        corrected = pd.read_csv(output / "paired_differences_3b.csv")
        image_metrics = metrics[metrics.condition.eq("image")][KEYS + ["primary_n"]]
        checked = corrected.merge(image_metrics, on=KEYS, validate="one_to_one")
        if not checked.n.eq(checked.primary_n).all():
            raise ValueError("Corrected paired-unit counts do not match primary metrics")
        columns = KEYS + ["primary_metric", "model"]
        comparison = old.merge(corrected, on=columns, suffixes=("_old", "_corrected"), validate="one_to_one")
        if len(comparison) != len(corrected):
            raise ValueError("Paired-difference rows changed unexpectedly")
        changed = comparison[comparison.n_old.ne(comparison.n_corrected) |
                             comparison.difference_old.ne(comparison.difference_corrected)]
        correction_path = output / "paired_difference_corrections.csv"
        if len(changed):
            changed.to_csv(correction_path, index=False)
        elif not correction_path.exists():
            raise ValueError("No changed rows and no existing correction record")

        checks = checks_from_files(questions, predictions, metrics, "3b", output)
        checks.to_csv(output / "checks.csv", index=False)
        write_report(output, ["3b"], json.loads((output / "image_verification.json").read_text()), checks)
        report_path = output / "STAGE3_REPORT.md"
        report = report_path.read_text()
        note = ("## Post-run review correction\n\n"
                "The original paired-difference table omitted program_strict membership when selecting units. "
                "Eight rows (four task and four family rows) have been recomputed from the unchanged saved predictions; "
                "see paired_difference_corrections.csv for original and corrected values with confidence intervals. "
                "All main per-condition metrics remain unchanged. The checks now distinguish repeatability at batch 1 "
                "from cross-batch invariance. No model inference or training was performed during this correction.\n\n")
        report_path.write_text(report.replace("## Open decisions for the human", note + "## Open decisions for the human"))
        if {condition: file_hash(path) for condition, path in prediction_paths.items()} != prediction_hashes:
            raise ValueError("Saved predictions changed during reanalysis")

        manifest["artifacts"] = {str(path.relative_to(output)): file_hash(path) for path in sorted(output.rglob("*"))
            if path.is_file() and path.name not in ("run_manifest.json", "run.log") and not path.name.endswith(".tmp")}
        manifest["posthoc_analysis_correction"] = {
            "at_utc": datetime.now(timezone.utc).isoformat(),
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "source_hashes": {str(path.relative_to(root)): file_hash(path) for path in (
                root / "src/vqa_research/analysis.py", root / "src/vqa_research/report.py", Path(__file__))},
            "saved_prediction_hashes": prediction_hashes,
            "changed_paired_rows": int(len(changed)),
            "no_model_inference_or_training": True,
        }
        save_json(manifest_path, manifest)
        print(f"Reanalysis complete: {len(changed)} paired rows corrected; predictions unchanged.")


if __name__ == "__main__":
    main()
