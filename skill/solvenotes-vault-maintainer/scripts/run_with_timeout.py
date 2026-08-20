#!/usr/bin/env python3
"""Run one maintenance subprocess with a bounded lifetime and diagnostics."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping, Sequence

TAIL_LIMIT = 4000


def _wait_for_exit(process: subprocess.Popen[str], timeout: float) -> bool:
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    return True


def _terminate(process: subprocess.Popen[str], *, grace_period: float = 5.0) -> None:
    """Terminate the complete process tree owned by *process*.

    A direct ``Popen.kill`` is insufficient for validation commands because a
    child can inherit the parent's stdout/stderr pipes and keep the parent
    ``communicate`` call blocked.  POSIX uses the process group created by
    ``start_new_session``.  Windows uses ``taskkill /T`` as the reliable tree
    operation and falls back to the direct process handle if the utility is
    unavailable.
    """

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=max(1.0, grace_period),
            )
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.send_signal(signal.CTRL_BREAK_EVENT)
            except (OSError, ValueError):
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    if _wait_for_exit(process, grace_period):
        return

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=max(1.0, grace_period),
            )
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    # A hostile or detached process may still refuse both tree operations.
    # Do not turn that edge case into an unbounded wait in the caller.
    if not _wait_for_exit(process, grace_period):
        try:
            process.kill()
        except OSError:
            pass
        _wait_for_exit(process, grace_period)


def _tail(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run(
    command: Sequence[str],
    timeout: float,
    label: str,
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    grace_period: float = 5.0,
) -> int:
    if not command:
        raise ValueError("a command is required")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=Path(cwd).resolve() if cwd is not None else None,
            env=dict(env) if env is not None else None,
            start_new_session=os.name != "nt",
            creationflags=creationflags,
        )
    except OSError as exc:
        print(f"FAILED step={label}: {exc}", file=sys.stderr)
        return 127
    started = time.monotonic()
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _terminate(process, grace_period=grace_period)
        try:
            stdout, stderr = process.communicate(timeout=grace_period)
        except subprocess.TimeoutExpired:
            # A process that detached from the group should not make the
            # caller wait forever.  Close the pipes after the tree kill and
            # collect the parent status one final time.
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
            stdout, stderr = "", ""
        elapsed = time.monotonic() - started
        print(f"TIMEOUT step={label} timeout_seconds={timeout:g} elapsed_seconds={elapsed:.2f}", file=sys.stderr)
        print(f"COMMAND {' '.join(command)}", file=sys.stderr)
        stdout_text = _tail(stdout or exc.stdout)
        stderr_text = _tail(stderr or exc.stderr)
        if stdout_text:
            print(f"STDOUT_TAIL\n{stdout_text[-TAIL_LIMIT:]}", file=sys.stderr)
        if stderr_text:
            print(f"STDERR_TAIL\n{stderr_text[-TAIL_LIMIT:]}", file=sys.stderr)
        return 124
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    return process.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--label", default="subprocess")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        return run(command, args.timeout, args.label)
    except OSError as exc:
        print(f"FAILED step={args.label}: {exc}", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
