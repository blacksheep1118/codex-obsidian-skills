#!/usr/bin/env python3
"""Validate the Notes lock against a Skills source checkout or mirror."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vault_contract import validate_checkout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notes-root", type=Path, required=True)
    parser.add_argument("--skills-root", type=Path, required=True)
    parser.add_argument(
        "--allow-no-git",
        action="store_true",
        help="allow an installed mirror without .git; contract and files are still checked",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = validate_checkout(
        args.notes_root.resolve(),
        args.skills_root.resolve(),
        require_git=not args.allow_no_git,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        lock = report.get("lock") or {}
        print(f"skills_lock_repository {lock.get('repository', 'MISSING')}")
        print(f"skills_lock_commit {lock.get('commit', 'MISSING')}")
        print(f"skills_checkout_commit {report.get('actual_sha') or 'UNAVAILABLE'}")
        print(f"skills_contract_version {report.get('actual_contract_version') or 'UNAVAILABLE'}")
        print(f"skills_lock_issues {len(report['issues'])}")
        for issue in report["issues"]:
            print(f"ISSUE {issue}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
