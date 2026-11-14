"""A temporary benchmark pause must always release the user's experiment."""

from pathlib import Path
import signal
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vqa_research import benchmark


@pytest.mark.parametrize("interrupted", [False, True])
def test_paused_experiment_is_resumed_even_on_failure(monkeypatch, interrupted):
    signals = []
    monkeypatch.setattr(benchmark, "verify_pause_target", lambda pid: None)
    monkeypatch.setattr(benchmark.os, "kill", lambda pid, sig: signals.append((pid, sig)))
    def run():
        with benchmark.paused_process(1234):
            if interrupted:
                raise RuntimeError("benchmark failed")
    if interrupted:
        with pytest.raises(RuntimeError, match="benchmark failed"):
            run()
    else:
        run()
    assert signals == [(1234, signal.SIGSTOP), (1234, signal.SIGCONT)]


def test_no_pause_does_not_signal_any_process(monkeypatch):
    monkeypatch.setattr(benchmark.os, "kill", lambda *args: pytest.fail("unexpected signal"))
    with benchmark.paused_process(None):
        pass
