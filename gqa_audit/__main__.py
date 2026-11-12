"""Command-line entry point for the GQA audit."""

import argparse
from pathlib import Path

from .stage1 import run_stage1


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m gqa_audit")
    subparsers = parser.add_subparsers(dest="stage", required=True)
    stage1 = subparsers.add_parser("stage1", help="Inspect GQA and propose task rules")
    stage1.add_argument("--questions", required=True, type=Path)
    args = parser.parse_args()
    if args.stage == "stage1":
        return run_stage1(args.questions)
    parser.error(f"Unsupported stage: {args.stage}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

