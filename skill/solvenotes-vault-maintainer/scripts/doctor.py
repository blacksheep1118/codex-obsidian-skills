#!/usr/bin/env python3
"""Validate one declared Solvenotes execution profile before expensive work."""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROFILE_PATH = Path(__file__).resolve().parents[1] / "references" / "validation-profiles.json"
LEGACY_PROFILE_ALIASES = {"quick": "vault-quick", "full": "vault-full"}


def load_contract(path: Path = PROFILE_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid validation profile contract: {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError(f"unsupported validation profile contract: {path}")
    for key in ("python", "modules", "commands", "profiles"):
        if not isinstance(payload.get(key), dict):
            raise ValueError(f"validation profile contract is missing object: {key}")
    return payload


def command_version(command: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    version_args = ["-v"] if command == "unzip" else ["--version"]
    try:
        result = subprocess.run(
            [command, *version_args],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return path
    detail = (result.stdout or result.stderr).strip().splitlines()
    return f"{path} ({detail[0]})" if detail else path


def python_probe(python_bin: str) -> tuple[dict[str, str], str | None]:
    code = (
        "import json, sys; "
        "print(json.dumps({'executable':sys.executable,'version':'.'.join(map(str,sys.version_info[:3]))}))"
    )
    try:
        result = subprocess.run(
            [python_bin, "-c", code],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, f"target Python probe failed: {exc}"
    if result.returncode:
        return {}, (result.stderr or result.stdout).strip() or f"probe exited {result.returncode}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {}, f"target Python probe returned invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return {}, "target Python probe returned a non-object"
    return {str(key): str(value) for key, value in payload.items()}, None


def module_versions(
    python_bin: str,
    module_contract: dict[str, dict[str, str]],
) -> tuple[dict[str, str], str | None]:
    probe_items = [
        [name, details["import_name"], details["distribution"]]
        for name, details in sorted(module_contract.items())
    ]
    code = (
        "import importlib.util, importlib.metadata, json; "
        f"items={probe_items!r}; "
        "print(json.dumps({name:(importlib.metadata.version(dist) "
        "if importlib.util.find_spec(module) else 'MISSING') "
        "for name,module,dist in items}))"
    )
    try:
        result = subprocess.run(
            [python_bin, "-c", code],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, f"target Python module probe failed: {exc}"
    if result.returncode:
        return {}, (result.stderr or result.stdout).strip() or f"module probe exited {result.returncode}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {}, f"target Python module probe returned invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return {}, "target Python module probe returned a non-object"
    return {str(key): str(value) for key, value in payload.items()}, None


def version_tuple(value: str) -> tuple[int, ...]:
    match = re.match(r"^(\d+(?:\.\d+)*)", value)
    return tuple(int(part) for part in match.group(1).split(".")) if match else ()


def python_support(_skills_root: Path | None = None) -> dict[str, str]:
    python_contract = load_contract()["python"]
    validated = python_contract.get("validated", [])
    return {
        "python-min": str(python_contract["minimum"]),
        "python-primary": str(python_contract["primary"]),
        "python-newest-validated": str(max(validated, key=version_tuple)),
    }


def version_in_range(value: str, requirement: dict[str, str]) -> bool:
    actual = version_tuple(value)
    minimum = version_tuple(requirement.get("minimum", "0"))
    maximum = version_tuple(requirement.get("maximum_exclusive", ""))
    return bool(actual) and actual >= minimum and (not maximum or actual < maximum)


def requirement_text(name: str, requirement: dict[str, str]) -> str:
    text = name
    if requirement.get("minimum"):
        text += f">={requirement['minimum']}"
    if requirement.get("maximum_exclusive"):
        text += f",<{requirement['maximum_exclusive']}"
    return text


def report(
    *,
    python_bin: str,
    notes_root: Path | None,
    skills_root: Path | None,
    profile: str | None = None,
    mode: str | None = None,
) -> tuple[dict[str, str], list[str]]:
    contract = load_contract()
    selected = profile or LEGACY_PROFILE_ALIASES.get(mode or "", mode or "vault-quick")
    profiles = contract["profiles"]
    if selected not in profiles:
        raise ValueError(f"unknown validation profile: {selected}")
    profile_contract = profiles[selected]
    probe, probe_error = python_probe(python_bin)
    modules, module_error = (
        module_versions(python_bin, contract["modules"]) if probe_error is None else ({}, None)
    )
    values: dict[str, str] = {
        "profile": selected,
        "profile_allows_network": str(bool(profile_contract.get("allows_network"))).lower(),
        "workspace_root": str(Path.cwd()),
        "python_bin": python_bin,
        "python_executable": probe.get("executable", python_bin),
        "python_version": probe.get("version", "UNAVAILABLE"),
        "os": platform.platform(),
        "notes_root": str(notes_root) if notes_root else "UNSET",
        "skills_root": str(skills_root) if skills_root else "UNSET",
    }
    issues: list[str] = []
    statuses: dict[str, str] = {}
    if probe_error:
        issues.append(probe_error)
        statuses["python"] = "MISSING"
    else:
        python_minor = ".".join(probe["version"].split(".")[:2])
        validated = {str(item) for item in contract["python"].get("validated", [])}
        minimum = str(contract["python"]["minimum"])
        if version_tuple(python_minor) < version_tuple(minimum):
            statuses["python"] = "UNSUPPORTED"
            issues.append(f"Python >= {minimum} required (found {probe['version']})")
        elif python_minor not in validated:
            statuses["python"] = "UNTESTED"
            validated_text = ", ".join(sorted(validated, key=version_tuple))
            issues.append(f"Python {python_minor} is outside the validated set: {validated_text}")
        else:
            statuses["python"] = "SUPPORTED"
    if module_error:
        issues.append(module_error)

    support = python_support(skills_root)
    for key, value in support.items():
        values[f"supported_{key.replace('-', '_')}"] = value

    required_modules = set(profile_contract.get("required_modules", []))
    for name, requirement in contract["modules"].items():
        installed_version = modules.get(name, "MISSING")
        values[f"{name}_version"] = installed_version or "MISSING"
        if installed_version == "MISSING":
            status = "MISSING" if name in required_modules else "OPTIONAL_MISSING"
            if name in required_modules:
                issues.append(requirement_text(name, requirement))
        elif not version_in_range(installed_version, requirement):
            status = "VERSION_MISMATCH" if name in required_modules else "UNTESTED"
            if name in required_modules:
                issues.append(
                    f"{requirement_text(name, requirement)} required (found {installed_version})"
                )
        else:
            status = "SUPPORTED"
        statuses[name] = status

    required_commands = set(profile_contract.get("required_commands", []))
    optional_commands = set(profile_contract.get("optional_commands", []))
    command_results: dict[str, str | None] = {}
    for alternatives in contract["commands"].values():
        for command in alternatives:
            if command not in command_results:
                command_results[command] = command_version(command)
                values[f"{command}_path"] = command_results[command] or "MISSING"
                statuses[command] = (
                    "SUPPORTED" if command_results[command] else "OPTIONAL_MISSING"
                )
    for group in required_commands | optional_commands:
        alternatives = contract["commands"].get(group, [])
        available = any(command_results.get(command) for command in alternatives)
        statuses[group] = (
            "SUPPORTED"
            if available
            else ("MISSING" if group in required_commands else "OPTIONAL_MISSING")
        )
        if not available and group in required_commands:
            issues.append(" or ".join(alternatives) or group)

    if profile_contract.get("requires_notes_root") and (
        notes_root is None or not (notes_root / "AGENT.md").is_file()
    ):
        issues.append("Notes root with AGENT.md")
        statuses["notes_root"] = "MISSING"
    else:
        statuses["notes_root"] = "SUPPORTED" if notes_root else "OPTIONAL_MISSING"
    if profile_contract.get("requires_skills_root") and (
        skills_root is None or not skills_root.exists()
    ):
        issues.append("Skills root")
        statuses["skills_root"] = "MISSING"
    else:
        statuses["skills_root"] = "SUPPORTED" if skills_root else "OPTIONAL_MISSING"

    for key, status in statuses.items():
        values[f"status_{key}"] = status
    return values, sorted(set(issues))


def python_bin_for_hint(python_bin: str) -> str:
    return str(Path(python_bin).expanduser()) if "/" in python_bin else python_bin


def main(argv: list[str] | None = None) -> int:
    contract = load_contract()
    profile_choices = tuple(sorted(contract["profiles"]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--notes-root", type=Path)
    parser.add_argument("--skills-root", type=Path)
    profile_group = parser.add_mutually_exclusive_group()
    profile_group.add_argument("--profile", choices=profile_choices)
    profile_group.add_argument(
        "--mode",
        choices=(*profile_choices, *LEGACY_PROFILE_ALIASES),
        help="compatibility alias for --profile",
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    selected = args.profile or LEGACY_PROFILE_ALIASES.get(
        args.mode or "", args.mode or "vault-quick"
    )
    try:
        values, issues = report(
            python_bin=args.python_bin,
            notes_root=args.notes_root.resolve() if args.notes_root else None,
            skills_root=args.skills_root.resolve() if args.skills_root else None,
            profile=selected,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(f"doctor_profile {selected}")
    print(f"doctor_mode {selected}")
    for key, value in values.items():
        print(f"{key} {value}")
    print("issues " + (", ".join(issues) if issues else "none"))
    if issues:
        requirements = (
            (args.skills_root.resolve() if args.skills_root else Path.cwd())
            / "requirements-dev.txt"
        )
        print(
            f"install_hint {python_bin_for_hint(args.python_bin)} "
            f"-m pip install -r {requirements}"
        )
    return 1 if args.strict and issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
