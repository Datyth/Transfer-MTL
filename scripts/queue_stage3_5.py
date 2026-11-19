"""Wait for an idle GPU, then execute the protocol through its P1 checkpoint."""

from __future__ import annotations

import json
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

from filelock import FileLock, Timeout

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.vqa_research.probe.features import ROOT, GPUOccupiedError, build_cache
from src.vqa_research.probe.recipe import run_recipe


OUTPUT = ROOT / "gqa_audit/outputs/stage3_5"


def status(state: str, **fields):
    temporary = OUTPUT / "queue_status.tmp"
    temporary.write_text(json.dumps({"state": state, "pid": os.getpid(), "updated_unix": time.time(),
                                     **fields}, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, OUTPUT / "queue_status.json")


def gpu_pids() -> list[str]:
    result = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, check=True)
    return [pid.strip() for pid in result.stdout.splitlines() if pid.strip() and pid.strip() != str(os.getpid())]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--remaining", action="store_true", help="Queue P2–P5 and report after completed P1")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(OUTPUT / "queue.lock"), timeout=0):
            while True:
                others = gpu_pids()
                if others:
                    status("waiting_for_gpu", other_gpu_pids=others)
                    time.sleep(30)
                    continue
                try:
                    with FileLock(str(OUTPUT / "gpu.lock"), timeout=0):
                        # A second check closes the race before starting work.
                        others = gpu_pids()
                        if others:
                            raise GPUOccupiedError(others)
                        if args.remaining:
                            from src.vqa_research.probe.protocol import preflight, cost_checkpoint
                            from src.vqa_research.probe.transfer import run_curves, run_transfer
                            from src.vqa_research.lora_pilot import run_qwen
                            from src.vqa_research.probe.report import build_report
                            preflight()
                            cost_checkpoint()
                            for phase in ("curves", "blank"):
                                status(phase)
                                run_curves(phase)
                            status("transfer")
                            run_transfer()
                            status("qwen")
                            run_qwen()
                            status("report")
                            build_report()
                            subprocess.run([sys.executable, str(ROOT / "scripts/check_stage3_5.py")], check=True)
                            status("pilot_complete")
                            return 0
                        status("features")
                        build_cache()
                        status("P1_recipe")
                        selected = run_recipe()
                        progress = (OUTPUT / "PROGRESS_P1.md").read_text()
                        state = "STOP_24_GPU_HOURS" if "STOP:" in progress else "P1_complete"
                        status(state, selected_recipe=selected)
                        return 0
                except GPUOccupiedError as error:
                    status("waiting_for_gpu", other_gpu_pids=error.pids,
                           note="P1 will resume from complete run hashes")
                time.sleep(30)
    except Timeout:
        print("Stage 3.5 queue is already active", file=sys.stderr)
        return 2
    except Exception as error:
        status("failed", error=str(error), traceback=traceback.format_exc())
        raise


if __name__ == "__main__":
    raise SystemExit(main())
