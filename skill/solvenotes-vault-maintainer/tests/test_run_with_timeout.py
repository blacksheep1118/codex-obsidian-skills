from __future__ import annotations

import sys
import time

import run_with_timeout


def test_run_with_timeout_returns_child_status() -> None:
    status = run_with_timeout.run([sys.executable, "-c", "print('ok')"], 5, "success")
    assert status == 0


def test_run_with_timeout_terminates_slow_child() -> None:
    started = time.monotonic()
    status = run_with_timeout.run([sys.executable, "-c", "import time; time.sleep(10)"], 0.1, "slow")
    elapsed = time.monotonic() - started
    assert status == 124
    assert elapsed < 5
