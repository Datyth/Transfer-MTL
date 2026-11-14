"""Small correctness/performance check; does not run the full experiment."""

from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root)]

from vqa_research.validation import main

if __name__ == "__main__":
    raise SystemExit(main())
