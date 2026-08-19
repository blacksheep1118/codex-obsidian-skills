#!/usr/bin/env python3
"""Validate the algorithm-job skill's closed direction contract."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
CONTRACT = ROOT / "references" / "algorithm-job-contract.md"
EXPECTED = {
    "cv",
    "nlp_llm",
    "recommendation",
    "search",
    "speech",
    "robotics",
    "automotive",
    "embodied_ai",
    "ai_infra",
}


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
    if ids != EXPECTED:
        print(f"ERROR: canonical IDs differ: {sorted(ids)}", file=sys.stderr)
        return 1
    if table.count("| `") != len(EXPECTED):
        print("ERROR: canonical direction table is not a single nine-row table", file=sys.stderr)
        return 1
    if "Do not create a tenth" not in text or "Migration decisions" not in contract:
        print("ERROR: migration boundary is incomplete", file=sys.stderr)
        return 1
    print("algorithm_job_skill_validator ok directions=9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
