#!/usr/bin/env python3
"""Run the Solvenotes environment doctor from the repository root."""

from __future__ import annotations

from pathlib import Path
import runpy
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = (
    REPO_ROOT
    / "skill"
    / "solvenotes-vault-maintainer"
    / "scripts"
    / "doctor.py"
)


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if "--skills-root" not in arguments:
        arguments.extend(["--skills-root", str(REPO_ROOT)])
    if "--profile" not in arguments and "--mode" not in arguments:
        arguments.extend(["--profile", "tool-quick"])
    sys.argv = [str(TARGET), *arguments]
    runpy.run_path(str(TARGET), run_name="__main__")
