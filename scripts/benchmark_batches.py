"""Small dev-only benchmark; full experiment settings are not modified."""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root)]

from vqa_research.benchmark import main

if __name__ == "__main__":
    raise SystemExit(main())
