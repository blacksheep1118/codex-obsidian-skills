#!/usr/bin/env python3
"""Validate the algorithm-job skill's closed direction contract."""

from __future__ import annotations

from pathlib import Path
import sys

from algorithm_job_taxonomy import CANONICAL_IDS


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
CONTRACT = ROOT / "references" / "algorithm-job-contract.md"
TAXONOMY = ROOT / "scripts" / "algorithm_job_taxonomy.py"
SCANNER = ROOT / "scripts" / "check_algorithm_job_vault.py"


def main() -> int:
    text = SKILL.read_text(encoding="utf-8")
    contract = CONTRACT.read_text(encoding="utf-8")
    table = text.split("## Canonical direction set", 1)[1].split(
        "## Evidence And Assumption Gate", 1
    )[0]
    ids = {
        line.split("|", 2)[1].strip().strip("`")
        for line in table.splitlines()
        if line.startswith("| `")
    }
    if ids != CANONICAL_IDS:
        print(f"ERROR: canonical IDs differ: {sorted(ids)}", file=sys.stderr)
        return 1
    if table.count("| `") != len(CANONICAL_IDS):
        print("ERROR: canonical direction table is not a single nine-row table", file=sys.stderr)
        return 1
    if not TAXONOMY.is_file() or not SCANNER.is_file():
        print("ERROR: scanner or central taxonomy is missing", file=sys.stderr)
        return 1
    if "Do not create a tenth" not in text or "Migration decisions" not in contract:
        print("ERROR: migration boundary is incomplete", file=sys.stderr)
        return 1
    print("algorithm_job_skill_validator ok directions=9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
