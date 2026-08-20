#!/usr/bin/env python3
"""Report the external validation environment before expensive checks."""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


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
        result = subprocess.run([python_bin, "-c", code], capture_output=True, text=True, check=False, timeout=15)
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


def module_versions(python_bin: str) -> tuple[dict[str, str], str | None]:
    code = (
        "import importlib.util, importlib.metadata, json; "
        "print(json.dumps({d:(importlib.metadata.version(d) if importlib.util.find_spec(m) else 'MISSING') "
        "for m,d in (('pytest','pytest'),('yaml','PyYAML'),('ruff','ruff'))}))"
    )
    try:
        result = subprocess.run([python_bin, "-c", code], capture_output=True, text=True, check=False, timeout=15)
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


def python_support(skills_root: Path | None) -> dict[str, str]:
    if skills_root is None:
        return {}
    config = skills_root / "pyproject.toml"
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return {}
    values: dict[str, str] = {}
    for key in ("python-min", "python-primary", "python-newest-validated"):
        match = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([0-9]+(?:\.[0-9]+){{1,2}})"\s*$', text, re.MULTILINE)
        if match:
            values[key] = match.group(1)
    return values


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def report(*, python_bin: str, notes_root: Path | None, skills_root: Path | None, mode: str) -> tuple[dict[str, str], list[str]]:
    probe, probe_error = python_probe(python_bin)
    modules, module_error = module_versions(python_bin) if probe_error is None else ({}, None)
    values: dict[str, str] = {
        "workspace_root": str(Path.cwd()),
        "python_bin": python_bin,
        "python_executable": probe.get("executable", python_bin),
        "python_version": probe.get("version", "UNAVAILABLE"),
        "os": platform.platform(),
        "notes_root": str(notes_root) if notes_root else "UNSET",
        "skills_root": str(skills_root) if skills_root else "UNSET",
    }
    missing: list[str] = []
    statuses: dict[str, str] = {}
    if probe_error:
        missing.append(probe_error)
        statuses["python"] = "MISSING"
    else:
        statuses["python"] = "SUPPORTED"
    if module_error:
        missing.append(module_error)
    support = python_support(skills_root)
    for key, value in support.items():
        values[f"supported_{key.replace('-', '_')}"] = value
    selected_version = probe.get("version", "0.0.0")
    if support.get("python-min") and version_tuple(selected_version) < version_tuple(support["python-min"]):
        missing.append(f"Python >= {support['python-min']}")
        statuses["python"] = "UNSUPPORTED"
    if support.get("python-newest-validated") and version_tuple(selected_version) > version_tuple(support["python-newest-validated"]):
        missing.append(f"Python <= {support['python-newest-validated']} (not validated)")
        statuses["python"] = "UNSUPPORTED"
    for command in ("git", "g++", "clang++", "unzip", "bash"):
        resolved = command_version(command)
        values[f"{command}_path"] = resolved or "MISSING"
        statuses[command] = "SUPPORTED" if resolved else "MISSING"
    for distribution in ("pytest", "PyYAML", "ruff"):
        installed_version = modules.get(distribution, "MISSING")
        values[f"{distribution}_version"] = installed_version or "MISSING"
        statuses[distribution] = "SUPPORTED" if installed_version != "MISSING" else "MISSING"
        if installed_version == "MISSING":
            missing.append(distribution)
    if not shutil.which("git"):
        missing.append("git")
    if mode == "full" and not (shutil.which("g++") or shutil.which("clang++")):
        missing.append("g++ or clang++")
    if notes_root is not None and not (notes_root / "AGENT.md").is_file():
        missing.append("Notes AGENT.md")
    if skills_root is not None and not skills_root.exists():
        missing.append("Skills root")
    for key, status in statuses.items():
        values[f"status_{key}"] = status
    return values, sorted(set(missing))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--notes-root", type=Path)
    parser.add_argument("--skills-root", type=Path)
    parser.add_argument("--mode", choices=("quick", "full"), default="quick")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    values, missing = report(
        python_bin=args.python_bin,
        notes_root=args.notes_root.resolve() if args.notes_root else None,
        skills_root=args.skills_root.resolve() if args.skills_root else None,
        mode=args.mode,
    )
    print(f"doctor_mode {args.mode}")
    for key, value in values.items():
        print(f"{key} {value}")
    print("missing " + (", ".join(missing) if missing else "none"))
    if missing:
        print("install_hint python -m pip install -r skill/solvenotes-vault-maintainer/requirements-dev.txt")
    return 1 if args.strict and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
