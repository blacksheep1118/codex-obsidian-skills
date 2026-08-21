from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import run_with_timeout


def test_run_with_timeout_returns_child_status() -> None:
    status = run_with_timeout.run([sys.executable, "-c", "print('ok')"], 5, "success")
    assert status == 0


def test_run_capture_returns_bounded_bytes() -> None:
    result = run_with_timeout.run_capture(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
        5,
        "capture",
    )

    assert result.returncode == 0
    assert result.stdout == b"out\n"
    assert result.stderr == b"err\n"
    assert result.timed_out is False


def test_run_capture_reports_output_limit_without_returning_unbounded_data() -> None:
    result = run_with_timeout.run_capture(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 10000)"],
        5,
        "capture-limit",
        max_stdout_bytes=128,
    )

    assert result.returncode == 125
    assert result.stdout_limit_exceeded is True
    assert len(result.stdout) == 129


def test_run_capture_stops_process_after_output_limit(tmp_path: Path) -> None:
    marker = tmp_path / "continued-after-output-limit.txt"
    result = run_with_timeout.run_capture(
        [
            sys.executable,
            "-c",
            (
                "import pathlib, sys, time; "
                "sys.stdout.write('x' * 1000000); sys.stdout.flush(); "
                "time.sleep(0.5); "
                f"pathlib.Path({str(marker)!r}).write_text('continued')"
            ),
        ],
        5,
        "capture-limit-stop",
        max_stdout_bytes=128,
        grace_period=0.1,
    )

    assert result.returncode == 125
    assert result.stdout_limit_exceeded is True
    time.sleep(0.7)
    assert not marker.exists()


def test_run_capture_terminates_parent_and_grandchild(tmp_path: Path) -> None:
    marker = tmp_path / "capture-grandchild-survived.txt"
    child = tmp_path / "capture-child.py"
    parent = tmp_path / "capture-parent.py"
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

    result = run_with_timeout.run_capture(
        [sys.executable, str(parent)],
        0.1,
        "capture-parent-grandchild",
        cwd=tmp_path,
    )

    assert result.returncode == 124
    assert result.timed_out is True
    assert b"parent-started" in result.stdout
    time.sleep(1.0)
    assert not marker.exists(), "the captured grandchild survived timeout termination"


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


def test_run_with_timeout_cleans_descendant_after_parent_exits(tmp_path: Path) -> None:
    """A successful direct child must not leave a background descendant behind."""

    if os.name == "nt":
        import pytest

        pytest.skip("Windows cannot recover a child tree after its parent handle exits")
    marker = tmp_path / "orphan-survived.txt"
    ready = tmp_path / "orphan-ready.txt"
    child = tmp_path / "background.py"
    parent = tmp_path / "short-parent.py"
    child.write_text(
        "import pathlib, signal, time\n"
        f"marker = pathlib.Path({str(marker)!r})\n"
        f"ready = pathlib.Path({str(ready)!r})\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "ready.write_text('ready\\n', encoding='utf-8')\n"
        "time.sleep(0.7)\n"
        "marker.write_text('survived\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    parent.write_text(
        "import pathlib, subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, {str(child)!r}])\n"
        f"ready = pathlib.Path({str(ready)!r})\n"
        "deadline = time.monotonic() + 2\n"
        "while not ready.exists() and time.monotonic() < deadline:\n"
        "    time.sleep(0.01)\n",
        encoding="utf-8",
    )

    status = run_with_timeout.run(
        [sys.executable, str(parent)],
        5,
        "successful-parent-background-child",
        cwd=tmp_path,
        grace_period=0.2,
    )

    assert status == 0
    assert ready.exists(), "the background child did not reach its signal handler"
    time.sleep(1.0)
    assert not marker.exists(), "the background descendant survived a successful wrapper"


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


def test_run_with_timeout_replays_large_output_without_pipe_capture(capsys) -> None:
    payload_size = 2 * 1024 * 1024
    status = run_with_timeout.run(
        [sys.executable, "-c", f"import sys; sys.stdout.write('x' * {payload_size})"],
        10,
        "large-output",
    )

    captured = capsys.readouterr()
    assert status == 0
    assert len(captured.out) == payload_size
