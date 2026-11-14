"""Run from the project root: python scripts/run_experiment.py --models 3b."""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root)]

from vqa_research.experiment import main

if __name__ == "__main__":
    raise SystemExit(main())
