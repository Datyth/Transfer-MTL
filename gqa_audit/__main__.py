"""Command-line entry point for the GQA audit."""

import argparse
from pathlib import Path

from .stage1 import run_stage1


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m gqa_audit")
    subparsers = parser.add_subparsers(dest="stage", required=True)
    stage1 = subparsers.add_parser("stage1", help="Inspect GQA and propose task rules")
    stage1.add_argument("--questions", required=True, type=Path)
    stage2 = subparsers.add_parser("stage2", help="Run the frozen task audit and question-only baselines")
    stage2.add_argument("--questions", required=True, type=Path)
    stage2b = subparsers.add_parser("stage2b", help="Run frozen H-L analysis addendum and evaluation demonstrations")
    stage2b.add_argument("--questions", required=True, type=Path)
    args = parser.parse_args()
    if args.stage == "stage1":
        return run_stage1(args.questions)
    if args.stage == "stage2":
        from .stage2 import run_stage2
        return run_stage2(args.questions)
    if args.stage == "stage2b":
        from .stage2b import run_stage2b
        return run_stage2b(args.questions)
    parser.error(f"Unsupported stage: {args.stage}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
