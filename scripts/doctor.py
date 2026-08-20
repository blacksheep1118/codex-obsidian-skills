#!/usr/bin/env python3
"""Run the Solvenotes environment doctor from the repository root."""

from __future__ import annotations

from pathlib import Path
import runpy


TARGET = (
    Path(__file__).resolve().parents[1]
    / "skill"
    / "solvenotes-vault-maintainer"
    / "scripts"
    / "doctor.py"
)


if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")
