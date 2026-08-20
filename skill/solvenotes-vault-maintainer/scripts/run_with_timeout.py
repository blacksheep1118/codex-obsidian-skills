#!/usr/bin/env python3
"""Run one maintenance subprocess with a bounded lifetime and diagnostics."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from typing import Sequence

TAIL_LIMIT = 4000


def _terminate(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=5)


def run(command: Sequence[str], timeout: float, label: str) -> int:
    if not command:
        raise ValueError("a command is required")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=os.name != "nt",
        creationflags=creationflags,
    )
    started = time.monotonic()
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _terminate(process)
        stdout, stderr = process.communicate()
        elapsed = time.monotonic() - started
        print(f"TIMEOUT step={label} timeout_seconds={timeout:g} elapsed_seconds={elapsed:.2f}", file=sys.stderr)
        print(f"COMMAND {' '.join(command)}", file=sys.stderr)
        if exc.stdout or stdout:
            print(f"STDOUT_TAIL\n{(stdout or exc.stdout or '')[-TAIL_LIMIT:]}", file=sys.stderr)
        if exc.stderr or stderr:
            print(f"STDERR_TAIL\n{(stderr or exc.stderr or '')[-TAIL_LIMIT:]}", file=sys.stderr)
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
