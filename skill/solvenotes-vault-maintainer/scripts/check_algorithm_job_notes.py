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

from check_algorithm_job_vault import scan as scan_algorithm_vault
from notes_utils import ROOT


def scan(root: Path) -> dict[str, object]:
    return scan_algorithm_vault(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = scan(args.root.resolve())
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
