"""Start a detached, single-instance CLIP queue or execute its worker."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

# Must precede importing torch through any study module.
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('MKL_NUM_THREADS', '4')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from filelock import FileLock, Timeout
from src.vqa_research.chuyen_giao.core import ROOT, OUT, REPORT_OUT, atomic

FULL_OUT = OUT


def gpu_pids():
    result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader,nounits'],
                            capture_output=True, text=True, check=True)
    return [int(p.strip()) for p in result.stdout.splitlines() if p.strip() and int(p.strip()) != os.getpid()]


def status(state, **fields):
    atomic(OUT / 'status.json', {'state': state, 'pid': os.getpid(),
                               'updated_unix': time.time(), **fields})


def worker(compact=False):
    from src.vqa_research.chuyen_giao.engine import Budget, BudgetStop
    from src.vqa_research.chuyen_giao.pipeline import execute, execute_report, update_readme
    guard = None
    try:
        with FileLock(str(OUT / 'queue.lock'), timeout=0):
            status('waiting_for_gpu')
            update_readme('queued')
            while True:
                occupied = gpu_pids()
                if occupied:
                    status('waiting_for_gpu', other_pids=occupied)
                    time.sleep(30)
                    continue
                try:
                    # Cooperate with the earlier pilot as well as the GPU process check.
                    with FileLock(str(ROOT / 'gqa_audit/outputs/stage3_5/gpu.lock'), timeout=0):
                        if gpu_pids():
                            time.sleep(30)
                            continue
                        guard = Budget()
                        if compact and not guard.path.exists():
                            # The prior feature extraction and failed full forecast count
                            # against the same 24-hour allowance, not a fresh budget.
                            ledger = FULL_OUT / 'budget.json'
                            if ledger.exists():
                                guard.previous = json.loads(ledger.read_text())['seconds']
                            guard.save()
                        status('preflight')
                        state = execute_report(guard) if compact else execute(guard)
                        guard.save()
                        update_readme(state)
                        status(state, gpu_seconds=guard.seconds)
                        return 0 if state == 'complete' else 3
                except Timeout:
                    status('waiting_for_previous_pipeline')
                    time.sleep(30)
    except Timeout:
        print('Hàng đợi đã hoạt động.', flush=True)
        return 2
    except BudgetStop as error:
        status('STOP_BUDGET', error=str(error), gpu_seconds=guard.seconds if guard else 0.)
        update_readme('STOP_BUDGET')
        return 3
    except Exception as error:
        if guard:
            guard.save()
        status('failed', error=str(error), traceback=traceback.format_exc())
        update_readme('failed')
        traceback.print_exc()
        return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--bao-cao', action='store_true', help='Chạy thăm dò năm nhóm trên tập phát triển')
    args = parser.parse_args()
    if args.bao_cao:
        global OUT
        import src.vqa_research.chuyen_giao.core as core
        OUT = core.OUT = REPORT_OUT
    OUT.mkdir(parents=True, exist_ok=True)
    if args.worker:
        return worker(args.bao_cao)
    with FileLock(str(OUT / 'launch.lock'), timeout=0):
        # Lock state, not a recycled PID, is the authority for an active queue.
        try:
            with FileLock(str(OUT / 'queue.lock'), timeout=0):
                pass
        except Timeout:
            print((OUT / 'status.json').read_text())
            return 0
        with (OUT / 'queue.log').open('ab', buffering=0) as log:
            child = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve()), '--worker'] +
                                     (['--bao-cao'] if args.bao_cao else []),
                                     cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
        # Wait only for worker initialization. No recurring monitoring is installed.
        for _ in range(300):
            if child.poll() is not None:
                raise RuntimeError(f'Queue exited during initialization: {child.returncode}')
            p = OUT / 'status.json'
            if p.exists() and json.loads(p.read_text()).get('pid') == child.pid:
                print(f'Đã xếp hàng. PID {child.pid}. Nhật ký: {OUT / "queue.log"}')
                return 0
            time.sleep(.1)
        raise RuntimeError(f'Worker {child.pid} has not acknowledged initialization. Inspect queue.log before restarting.')


if __name__ == '__main__':
    raise SystemExit(main())
