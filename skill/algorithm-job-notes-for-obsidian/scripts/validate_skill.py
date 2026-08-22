#!/usr/bin/env python3
"""Validate the algorithm-job skill's closed direction contract."""

from __future__ import annotations

from pathlib import Path
import sys

from algorithm_job_taxonomy import CANONICAL_IDS
from check_python_runtime_examples import exact_requirement_versions


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
CONTRACT = ROOT / "references" / "algorithm-job-contract.md"
TAXONOMY = ROOT / "scripts" / "algorithm_job_taxonomy.py"
SCANNER = ROOT / "scripts" / "check_algorithm_job_vault.py"
TIMEOUT_RUNNER = ROOT / "scripts" / "run_with_timeout.py"
PYTHON_RUNTIME_CHECKER = ROOT / "scripts" / "check_python_runtime_examples.py"
PYTHON_RUNTIME_REFERENCE = ROOT / "references" / "python-runtime-validation.md"
PYTHON_RUNTIME_REQUIREMENTS = ROOT / "requirements-runtime.txt"


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
    required_files = (
        TAXONOMY,
        SCANNER,
        TIMEOUT_RUNNER,
        PYTHON_RUNTIME_CHECKER,
        PYTHON_RUNTIME_REFERENCE,
        PYTHON_RUNTIME_REQUIREMENTS,
    )
    if any(not path.is_file() for path in required_files):
        print("ERROR: required scanner or runtime resource is missing", file=sys.stderr)
        return 1
    if "Do not create a tenth" not in text or "Migration decisions" not in contract:
        print("ERROR: migration boundary is incomplete", file=sys.stderr)
        return 1
    runtime_reference = PYTHON_RUNTIME_REFERENCE.read_text(encoding="utf-8")
    if "python-e2e" not in text or "failures=0" not in runtime_reference:
        print("ERROR: dependency-backed Python runtime contract is incomplete", file=sys.stderr)
        return 1
    try:
        runtime_pins = exact_requirement_versions(PYTHON_RUNTIME_REQUIREMENTS)
    except (OSError, ValueError) as exc:
        print(f"ERROR: invalid dependency-backed runtime pins: {exc}", file=sys.stderr)
        return 1
    expected_pins = {
        "pyyaml",
        "numpy",
        "torch",
        "onnx",
        "onnxruntime",
        "onnxscript",
        "pyspark",
    }
    if set(runtime_pins) != expected_pins:
        print("ERROR: dependency-backed runtime pin set is incomplete", file=sys.stderr)
        return 1
    print("algorithm_job_skill_validator ok directions=9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
