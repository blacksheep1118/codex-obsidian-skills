#!/usr/bin/env python3
"""Report the external validation environment before expensive checks."""

from __future__ import annotations

import argparse
import importlib.util
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
    try:
        result = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return path
    detail = (result.stdout or result.stderr).strip().splitlines()
    return f"{path} ({detail[0]})" if detail else path


def module_version(module_name: str, distribution: str) -> str | None:
    if importlib.util.find_spec(module_name) is None:
        return None
    try:
        from importlib.metadata import version

        return version(distribution)
    except Exception:  # pragma: no cover - broken optional metadata is diagnostic output
        return "available"


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
    values: dict[str, str] = {
        "workspace_root": str(Path.cwd()),
        "python_bin": python_bin,
        "python_version": platform.python_version(),
        "os": platform.platform(),
        "notes_root": str(notes_root) if notes_root else "UNSET",
        "skills_root": str(skills_root) if skills_root else "UNSET",
    }
    missing: list[str] = []
    support = python_support(skills_root)
    for key, value in support.items():
        values[f"supported_{key.replace('-', '_')}"] = value
    selected_version = platform.python_version()
    if support.get("python-min") and version_tuple(selected_version) < version_tuple(support["python-min"]):
        missing.append(f"Python >= {support['python-min']}")
    if support.get("python-newest-validated") and version_tuple(selected_version) > version_tuple(support["python-newest-validated"]):
        missing.append(f"Python <= {support['python-newest-validated']} (not validated)")
    for command in ("git", "g++", "clang++", "unzip", "bash"):
        resolved = command_version(command)
        values[f"{command}_path"] = resolved or "MISSING"
    for module, distribution in (("pytest", "pytest"), ("yaml", "PyYAML"), ("ruff", "ruff")):
        installed_version = module_version(module, distribution)
        values[f"{distribution}_version"] = installed_version or "MISSING"
        if installed_version is None:
            missing.append(distribution)
    if not shutil.which("git"):
        missing.append("git")
    if mode == "full" and not (shutil.which("g++") or shutil.which("clang++")):
        missing.append("g++ or clang++")
    if notes_root is not None and not (notes_root / "AGENT.md").is_file():
        missing.append("Notes AGENT.md")
    if skills_root is not None and not skills_root.exists():
        missing.append("Skills root")
    if python_bin != sys.executable:
        values["doctor_interpreter"] = sys.executable
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
