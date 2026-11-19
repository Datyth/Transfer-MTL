"""Save complete pytest output and verify frozen Stage 2b dev demo numbers."""
from pathlib import Path
import json
import subprocess
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gqa_audit.evaluation import Evaluator


def main():
    output = ROOT / "gqa_audit/outputs/stage3_5"
    result = subprocess.run([sys.executable, "-m", "pytest", "-ra"], cwd=ROOT, capture_output=True, text=True)
    (output / "pytest_report.txt").write_text(result.stdout + result.stderr)
    print(result.stdout[-2000:], flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
    old = pd.read_csv(ROOT / "gqa_audit/outputs/stage2b/demo_eval_blind.csv")
    predictions = pd.read_csv(ROOT / "gqa_audit/outputs/stage2/blind_predictions.csv", dtype={"question_id": str})
    evaluator = Evaluator(mode="stage3_5")
    comparisons = []
    for variant in ("program_strict", "unfiltered"):
        subset = predictions[(predictions.variant == variant) & (predictions.analysis_split == "dev")]
        new = evaluator.evaluate(subset[["question_id", "prediction"]].rename(columns={"prediction": "pred"}), variant, "dev")
        reference = old[(old.variant == variant) & (old.part == "dev")]
        keys = ["variant", "part", "level", "task", "unit"]
        merged = new.merge(reference, on=keys, validate="one_to_one", suffixes=("_new", "_old"))
        if len(merged) != len(new) or len(merged) != len(reference):
            raise ValueError("Stage 2b demo row mismatch")
        for column in new.select_dtypes(include="number").columns:
            a, b = merged[f"{column}_new"], merged[f"{column}_old"]
            if not np.allclose(a, b, atol=1e-15, rtol=1e-14, equal_nan=True):
                raise ValueError(f"Stage 2b demo changed: {variant}/{column}")
        comparisons.append({"variant": variant, "rows": len(new), "status": "PASS"})
    (output / "stage2b_demo_regression.json").write_text(json.dumps(comparisons, indent=2) + "\n")
    print("Stage 2b dev demo regression PASS (all numeric columns, both variants)", flush=True)


if __name__ == "__main__":
    main()
