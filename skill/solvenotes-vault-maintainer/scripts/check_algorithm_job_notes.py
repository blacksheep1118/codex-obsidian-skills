#!/usr/bin/env python3
"""Project-level adapter for the canonical algorithm-job Skill scanner.

The taxonomy and structural implementation live in
``algorithm-job-notes-for-obsidian``.  This adapter keeps the Solvenotes
maintenance gate's command name stable without maintaining a second copy.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from notes_utils import ROOT

SKILL_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SKILL = "algorithm-job-notes-for-obsidian"


def _algorithm_scanner():
    """Load the scanner from the installed sibling Skill, not the source repo."""

    algorithm_scripts = SKILL_ROOT.parent / REQUIRED_SKILL / "scripts"
    if not algorithm_scripts.is_dir():
        raise RuntimeError(
            "required Skill not installed: "
            f"{REQUIRED_SKILL}; install {REQUIRED_SKILL!r} alongside "
            f"{SKILL_ROOT.name!r}"
        )
    scanner_path = algorithm_scripts / "check_algorithm_job_vault.py"
    if not scanner_path.is_file():
        raise RuntimeError(
            f"required Skill {REQUIRED_SKILL!r} is incomplete: "
            f"missing {scanner_path.name}"
        )
    if str(algorithm_scripts) not in sys.path:
        sys.path.insert(0, str(algorithm_scripts))
    from check_algorithm_job_vault import scan as scan_algorithm_vault

    return scan_algorithm_vault


def scan(root: Path) -> dict[str, object]:
    return _algorithm_scanner()(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        payload = scan(args.root.resolve())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"algorithm_job_files {payload.get('algorithm_files', 0)}")
        print(f"algorithm_job_directions {len(payload.get('canonical_directions', []))}")
        print(f"algorithm_job_issues {len(payload['issues'])}")
        for issue in payload["issues"]:
            print(f"ISSUE {issue}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
