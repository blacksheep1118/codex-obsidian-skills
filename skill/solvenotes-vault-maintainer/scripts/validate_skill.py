#!/usr/bin/env python3
"""Validate this project Skill's metadata and external-vault entry points."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from doctor import exact_requirement_versions, normalize_distribution_name
from skill_metadata import (
    MetadataValidationError,
    load_skill_frontmatter,
    validate_openai_yaml,
)

SKILL_ROOT = Path(__file__).resolve().parents[1]
ALGORITHM_SKILL_ROOT = SKILL_ROOT.parent / "algorithm-job-notes-for-obsidian"


def checker_requirement_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "REQUIREMENTS"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Dict):
            break
        names = {
            ast.literal_eval(key)
            for key in node.value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        if len(names) != len(node.value.keys):
            break
        return names
    raise ValueError(f"cannot read REQUIREMENTS mapping from {path}")


def main() -> int:
    try:
        metadata = load_skill_frontmatter(SKILL_ROOT / "SKILL.md", expected_name=SKILL_ROOT.name)
        validate_openai_yaml(SKILL_ROOT / "agents" / "openai.yaml", metadata["name"])
    except (OSError, MetadataValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    required = (
        SKILL_ROOT / "LICENSE",
        SKILL_ROOT / "scripts" / "dev_check.sh",
        SKILL_ROOT / "scripts" / "check_all_notes.py",
        SKILL_ROOT / "scripts" / "doctor.py",
        SKILL_ROOT / "scripts" / "check_skills_lock.py",
        SKILL_ROOT / "scripts" / "check_workspace_guidance.py",
        SKILL_ROOT / "scripts" / "check_documented_commands.py",
        SKILL_ROOT / "scripts" / "update_notes_skill_lock.py",
        SKILL_ROOT / "scripts" / "validate_notes_candidate.py",
        SKILL_ROOT / "scripts" / "vault_contract.py",
        SKILL_ROOT / "scripts" / "package_vault.py",
        SKILL_ROOT / "scripts" / "verify_vault_package.py",
        SKILL_ROOT / "scripts" / "package_workspace.py",
        SKILL_ROOT / "scripts" / "verify_workspace_package.py",
        SKILL_ROOT / "scripts" / "archive_contract.py",
        SKILL_ROOT / "scripts" / "safe_io.py",
        SKILL_ROOT / "scripts" / "skill_metadata.py",
        SKILL_ROOT / "scripts" / "run_with_timeout.py",
        SKILL_ROOT / "references" / "validation-profiles.json",
    )
    missing = [str(path.relative_to(SKILL_ROOT)) for path in required if not path.exists()]
    if missing:
        print(f"ERROR: missing project Skill entry points: {', '.join(missing)}", file=sys.stderr)
        return 1
    cross_skill_required = (
        ALGORITHM_SKILL_ROOT / "scripts" / "check_python_runtime_examples.py",
        ALGORITHM_SKILL_ROOT / "requirements-runtime.txt",
        ALGORITHM_SKILL_ROOT / "references" / "python-runtime-validation.md",
    )
    cross_skill_missing = [
        str(path) for path in cross_skill_required if not path.is_file()
    ]
    if cross_skill_missing:
        print(
            "ERROR: vault-runtime dependency closure is incomplete: "
            + ", ".join(cross_skill_missing),
            file=sys.stderr,
        )
        return 1
    try:
        profile_contract = json.loads(
            (SKILL_ROOT / "references" / "validation-profiles.json").read_text(
                encoding="utf-8"
            )
        )
        profiles = profile_contract["profiles"]
        module_contract = profile_contract["modules"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"ERROR: invalid validation profile contract: {exc}", file=sys.stderr)
        return 1
    runtime_profile = profiles.get("vault-runtime", {})
    dev_check = (SKILL_ROOT / "scripts" / "dev_check.sh").read_text(encoding="utf-8")
    expected_runtime_modules = {
        "PyYAML",
        "numpy",
        "torch",
        "onnx",
        "onnxruntime",
        "onnxscript",
        "pyspark",
    }
    if (
        runtime_profile.get("requirements_file")
        != "algorithm-job-notes-for-obsidian/requirements-runtime.txt"
        or set(runtime_profile.get("required_modules", []))
        != expected_runtime_modules
        or runtime_profile.get("minimum_python") != "3.10"
        or runtime_profile.get("minimum_java_major") != 17
        or "java" not in runtime_profile.get("required_commands", [])
        or "vault-runtime) vault_runtime" not in dev_check
    ):
        print("ERROR: vault-runtime entry point is incomplete", file=sys.stderr)
        return 1
    try:
        runtime_pins = exact_requirement_versions(
            ALGORITHM_SKILL_ROOT / "requirements-runtime.txt"
        )
        checker_names = checker_requirement_names(
            ALGORITHM_SKILL_ROOT / "scripts" / "check_python_runtime_examples.py"
        )
        profile_distributions = {
            normalize_distribution_name(module_contract[name]["distribution"])
            for name in runtime_profile["required_modules"]
        }
    except (KeyError, OSError, SyntaxError, ValueError) as exc:
        print(f"ERROR: invalid vault-runtime dependency mapping: {exc}", file=sys.stderr)
        return 1
    expected_checker_names = (profile_distributions - {"pyyaml"}) | {
        "python",
        "java17",
    }
    if set(runtime_pins) != profile_distributions or checker_names != expected_checker_names:
        print(
            "ERROR: vault-runtime profile, direct pins, and checker requirements differ: "
            f"profile={sorted(profile_distributions)} "
            f"pins={sorted(runtime_pins)} checker={sorted(checker_names)}",
            file=sys.stderr,
        )
        return 1
    print(f"solvenotes_vault_maintainer_validator ok name={metadata['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
