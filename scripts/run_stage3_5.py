"""Stage 3.5 pilot entry point. Run phases in the frozen order."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from filelock import FileLock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.vqa_research.probe.features import ROOT, build_cache
from src.vqa_research.probe.recipe import run_recipe
from src.vqa_research.probe.protocol import preflight, cost_checkpoint
from src.vqa_research.probe.transfer import run_curves, run_transfer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("features", "recipe", "curves", "blank", "transfer", "qwen",
                                           "qwen-benchmark", "checkpoint", "report", "all"))
    args = parser.parse_args()
    output = ROOT / "gqa_audit/outputs/stage3_5"
    output.mkdir(parents=True, exist_ok=True)
    with FileLock(str(output / "gpu.lock"), timeout=0):
        preflight()
        if args.command == "features":
            print(json.dumps(build_cache(), indent=2))
        elif args.command == "recipe":
            if not (ROOT / "data/features/clip_vitb16_224/manifest.json").exists():
                raise RuntimeError("Complete validated feature cache required before P1")
            print(json.dumps(run_recipe(), indent=2))
        elif args.command == "qwen-benchmark":
            from src.vqa_research.lora_pilot import run_qwen
            run_qwen(benchmark=True)
            print(json.dumps(cost_checkpoint(), indent=2))
        elif args.command == "checkpoint":
            print(json.dumps(cost_checkpoint(), indent=2))
        elif args.command == "report":
            from src.vqa_research.probe.report import build_report
            build_report()
            import subprocess
            subprocess.run([sys.executable, str(ROOT / "scripts/check_stage3_5.py")], check=True)
        elif args.command in ("curves", "blank", "transfer", "qwen", "all"):
            cost_checkpoint()
            if args.command in ("curves", "all"):
                run_curves("curves")
            if args.command in ("blank", "all"):
                run_curves("blank")
            if args.command in ("transfer", "all"):
                run_transfer()
            if args.command in ("qwen", "all"):
                from src.vqa_research.lora_pilot import run_qwen
                run_qwen()
            if args.command == "all":
                from src.vqa_research.probe.report import build_report
                build_report()
                import subprocess
                subprocess.run([sys.executable, str(ROOT / "scripts/check_stage3_5.py")], check=True)


if __name__ == "__main__":
    main()
