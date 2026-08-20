from __future__ import annotations

import os
import sys
import time
from pathlib import Path

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


def test_run_with_timeout_terminates_parent_and_grandchild_with_inherited_pipes(tmp_path: Path) -> None:
    """A descendant holding stdout must not keep the timeout wrapper blocked."""

    marker = tmp_path / "grandchild-survived.txt"
    child = tmp_path / "child.py"
    parent = tmp_path / "parent.py"
    child.write_text(
        "import pathlib, time\n"
        f"marker = pathlib.Path({str(marker)!r})\n"
        "time.sleep(0.7)\n"
        "marker.write_text('survived\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    parent.write_text(
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, {str(child)!r}])\n"
        "print('parent-started', flush=True)\n"
        "time.sleep(10)\n",
        encoding="utf-8",
    )

    started = time.monotonic()
    status = run_with_timeout.run([sys.executable, str(parent)], 0.1, "parent-grandchild", cwd=tmp_path)
    elapsed = time.monotonic() - started

    assert status == 124
    assert elapsed < 5
    time.sleep(1.0)
    assert not marker.exists(), "the grandchild survived the timeout tree termination"


def test_run_with_timeout_accepts_environment_and_unrelated_cwd(tmp_path: Path) -> None:
    marker = tmp_path / "env.txt"
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    status = run_with_timeout.run(
        [sys.executable, "-c", "import os, pathlib; pathlib.Path(os.environ['RUNNER_MARKER']).write_text(os.getcwd())"],
        5,
        "cwd-env",
        cwd=unrelated,
        env={**os.environ, "RUNNER_MARKER": str(marker)},
    )

    assert status == 0
    assert Path(marker.read_text(encoding="utf-8")).resolve() == unrelated.resolve()
