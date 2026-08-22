#!/usr/bin/env python3
"""Run only explicitly marked, dependency-backed Python note examples."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import importlib.metadata
import importlib.util
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

try:
    from .run_with_timeout import run_capture
except ImportError:
    from run_with_timeout import run_capture


MARKER_PREFIX = "<!-- runnable: python-e2e"
MARKER_RE = re.compile(
    r"<!--\s*runnable:\s*python-e2e\s+"
    r"requires=([a-z0-9_.-]+(?:,[a-z0-9_.-]+)*)\s*-->\s*$",
    re.IGNORECASE,
)
FENCE_OPEN_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})[^\r\n]*$")
PYTHON_FENCE_OPEN_RE = re.compile(
    r"^[ ]{0,3}(`{3,})[ \t]*(?:python|python3|py)"
    r"(?:[ \t]+[^\r\n]*)?[ \t]*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RuntimeRequirement:
    import_name: str | None
    distribution: str | None
    minimum: str | None = None


REQUIREMENTS = {
    "python": RuntimeRequirement(None, None, "3.10"),
    "numpy": RuntimeRequirement("numpy", "numpy"),
    "torch": RuntimeRequirement("torch", "torch"),
    "onnx": RuntimeRequirement("onnx", "onnx"),
    "onnxruntime": RuntimeRequirement("onnxruntime", "onnxruntime"),
    "onnxscript": RuntimeRequirement("onnxscript", "onnxscript"),
    "pyspark": RuntimeRequirement("pyspark", "pyspark"),
    "java17": RuntimeRequirement(None, None, "17"),
}
RUNTIME_REQUIREMENTS_PATH = Path(__file__).resolve().parents[1] / "requirements-runtime.txt"
EXACT_REQUIREMENT_RE = re.compile(r"^([A-Za-z0-9_.-]+)==(\S+)$")
PASSTHROUGH_ENVIRONMENT = (
    "PATH",
    "JAVA_HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
)


def positive_timeout(value: str) -> float:
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite number greater than zero")
    return timeout


def version_tuple(value: str) -> tuple[int, ...]:
    match = re.match(r"^(\d+(?:\.\d+)*)", value)
    return tuple(int(part) for part in match.group(1).split(".")) if match else ()


def normalize_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def exact_version_matches(installed: str, expected: str) -> bool:
    """Apply PEP 440 local-version semantics for one exact public pin."""
    candidate = installed if "+" in expected else installed.split("+", 1)[0]
    return candidate == expected


def exact_requirement_versions(path: Path = RUNTIME_REQUIREMENTS_PATH) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = EXACT_REQUIREMENT_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"{path}:{line_number}: expected one exact plain name==version pin")
        name = normalize_distribution_name(match.group(1))
        if name in pins:
            raise ValueError(f"{path}:{line_number}: duplicate requirement {name}")
        pins[name] = match.group(2)
    return pins


def fence_end(lines: list[str], start: int, delimiter: str) -> int | None:
    character = delimiter[0]
    minimum_length = len(delimiter)
    for index in range(start + 1, len(lines)):
        candidate = lines[index].rstrip("\r\n").strip()
        if len(candidate) >= minimum_length and set(candidate) == {character}:
            return index
    return None


def parse_runtime_markdown(
    text: str,
) -> tuple[list[tuple[int, str]], list[tuple[int, str, tuple[str, ...]]]]:
    issues: list[tuple[int, str]] = []
    blocks: list[tuple[int, str, tuple[str, ...]]] = []
    lines = text.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        line = lines[index].rstrip("\r\n")
        if MARKER_PREFIX in line.lower():
            marker = MARKER_RE.fullmatch(line.strip())
            if marker is None:
                issues.append(
                    (
                        index + 1,
                        "invalid python-e2e marker; expected "
                        "<!-- runnable: python-e2e requires=name[,name...] -->",
                    )
                )
                index += 1
                continue
            next_index = index + 1
            if next_index >= len(lines):
                issues.append((index + 1, "python-e2e marker is not followed by a Python fence"))
                index += 1
                continue
            opening = PYTHON_FENCE_OPEN_RE.fullmatch(
                lines[next_index].rstrip("\r\n")
            )
            if opening is None:
                issues.append(
                    (index + 1, "python-e2e marker must immediately precede a Python fence")
                )
                index += 1
                continue
            end = fence_end(lines, next_index, opening.group(1))
            if end is None:
                issues.append((next_index + 1, "marked Python fence is not closed"))
                break
            requirements = tuple(marker.group(1).lower().split(","))
            blocks.append(
                (next_index + 1, "".join(lines[next_index + 1 : end]), requirements)
            )
            index = end + 1
            continue

        fence = FENCE_OPEN_RE.fullmatch(line)
        if fence is not None:
            end = fence_end(lines, index, fence.group(1))
            index = len(lines) if end is None else end + 1
            continue
        index += 1
    return issues, blocks


def marker_issues(text: str) -> list[tuple[int, str]]:
    issues, _blocks = parse_runtime_markdown(text)
    return issues


def marked_blocks(text: str) -> list[tuple[int, str, tuple[str, ...]]]:
    _issues, blocks = parse_runtime_markdown(text)
    return blocks


def java_version() -> tuple[str | None, str | None]:
    java = shutil.which("java")
    if java is None:
        return None, "java17: java command is missing; install Java 17+ and set JAVA_HOME/PATH"
    result = run_capture([java, "-version"], 15, "java version")
    detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
    if result.returncode:
        return None, f"java17: java -version exited {result.returncode}: {detail}"
    match = re.search(r'version\s+"((?:1\.)?\d+(?:\.\d+)*)', detail)
    if match is None:
        return None, f"java17: cannot parse java -version output: {detail}"
    version = match.group(1)
    major = int(version.split(".")[1] if version.startswith("1.") else version.split(".")[0])
    if major < 17:
        return version, f"java17: Java >=17 required (found {version})"
    return version, None


def probe_requirement(name: str) -> tuple[str | None, str | None]:
    requirement = REQUIREMENTS.get(name)
    if requirement is None:
        return None, f"unknown runtime requirement: {name}"
    if name == "java17":
        return java_version()
    if name == "python":
        version = ".".join(str(part) for part in sys.version_info[:3])
        assert requirement.minimum is not None
        if version_tuple(version) < version_tuple(requirement.minimum):
            return version, f"{name}: version >={requirement.minimum} required (found {version})"
        return version, None
    else:
        assert requirement.import_name is not None
        assert requirement.distribution is not None
        if importlib.util.find_spec(requirement.import_name) is None:
            return None, f"{name}: Python module {requirement.import_name!r} is missing"
        try:
            version = importlib.metadata.version(requirement.distribution)
        except importlib.metadata.PackageNotFoundError:
            return None, f"{name}: distribution {requirement.distribution!r} is missing"
    try:
        pinned_versions = exact_requirement_versions()
    except (OSError, ValueError) as exc:
        return version, f"runtime requirement pins are invalid: {exc}"
    distribution = normalize_distribution_name(requirement.distribution)
    expected = pinned_versions.get(distribution)
    if expected is None:
        return version, f"{name}: distribution {distribution!r} has no exact runtime pin"
    if not exact_version_matches(version, expected):
        return version, f"{name}: version =={expected} required (found {version})"
    return version, None


def runtime_environment(temp_root: Path) -> dict[str, str]:
    environment = {
        name: os.environ[name]
        for name in PASSTHROUGH_ENVIRONMENT
        if name in os.environ
    }
    home = temp_root / "home"
    cache = temp_root / "cache"
    home.mkdir()
    cache.mkdir()
    environment["HOME"] = str(home)
    environment["USERPROFILE"] = str(home)
    environment["XDG_CACHE_HOME"] = str(cache)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONSAFEPATH"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYSPARK_DRIVER_PYTHON"] = sys.executable
    environment["PYSPARK_PYTHON"] = sys.executable
    environment["SPARK_LOCAL_IP"] = "127.0.0.1"
    environment["NO_PROXY"] = "127.0.0.1,localhost"
    environment["SPARK_LOCAL_DIRS"] = str(temp_root / "spark-local")
    environment["TMPDIR"] = str(temp_root / "tmp")
    environment["TEMP"] = str(temp_root / "tmp")
    environment["TMP"] = str(temp_root / "tmp")
    (temp_root / "spark-local").mkdir()
    (temp_root / "tmp").mkdir()
    return environment


def diagnostic_tail(payload: bytes, limit: int = 3000) -> str:
    return payload.decode("utf-8", errors="replace").strip()[-limit:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="notes vault root")
    parser.add_argument("--timeout", type=positive_timeout, default=180.0)
    parser.add_argument(
        "--require-marked",
        action="store_true",
        help="fail when the vault contains no explicit python-e2e blocks",
    )
    parser.add_argument(
        "--reviewed-local-code",
        action="store_true",
        help="confirm that every marked block was manually reviewed and is trusted",
    )
    args = parser.parse_args(argv)

    discovered: list[tuple[Path, int, str, tuple[str, ...]]] = []
    failures: list[str] = []
    for path in sorted(args.root.rglob("*.md")):
        if ".obsidian/templates" in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8")
        label = path.relative_to(args.root)
        for line, issue in marker_issues(text):
            failures.append(f"{label}:{line}: {issue}")
        for line, code, requirements in marked_blocks(text):
            discovered.append((path, line, code, requirements))

    if args.require_marked and not discovered:
        failures.append("no explicitly marked python-e2e blocks found")
    if discovered and not args.reviewed_local_code:
        failures.append(
            "marked runtime execution requires explicit --reviewed-local-code confirmation"
        )

    for path, line, code, requirements in discovered:
        label = f"{path.relative_to(args.root)}:{line}"
        if len(requirements) != len(set(requirements)):
            failures.append(f"{label}: duplicate runtime requirement")
        try:
            ast.parse(code, filename=label, type_comments=True)
        except SyntaxError as error:
            failures.append(f"{label}: {error.msg} (line {error.lineno})")

    required_names = sorted(
        {name for _path, _line, _code, requirements in discovered for name in requirements}
    )
    versions: dict[str, str] = {}
    for name in required_names:
        version, issue = probe_requirement(name)
        if version is not None:
            versions[name] = version
        if issue is not None:
            failures.append(issue)

    for name, version in sorted(versions.items()):
        print(f"python_runtime_dependency name={name} version={version}")

    executed = 0
    if not failures:
        with tempfile.TemporaryDirectory(prefix="solvenotes-python-e2e-") as temporary:
            root = Path(temporary)
            for index, (path, line, code, requirements) in enumerate(discovered, 1):
                example_root = root / f"example-{index}"
                example_root.mkdir()
                source = example_root / "example.py"
                source.write_text(code, encoding="utf-8")
                label = f"{path.relative_to(args.root)}:{line}"
                result = run_capture(
                    [sys.executable, "-I", str(source)],
                    args.timeout,
                    f"python-e2e {label}",
                    cwd=example_root,
                    env=runtime_environment(example_root),
                )
                if result.timed_out:
                    failures.append(f"{label}: runtime timeout")
                    continue
                if result.stdout_limit_exceeded or result.stderr_limit_exceeded:
                    failures.append(f"{label}: runtime output exceeded safety limit")
                    continue
                if result.returncode:
                    detail = diagnostic_tail(result.stderr or result.stdout)
                    failures.append(f"{label}: runtime exit {result.returncode}\n{detail}")
                    continue
                executed += 1
                print(
                    f"PASS {label} requirements={','.join(requirements)}"
                )

    print(
        "python_runtime_examples "
        f"marked_blocks={len(discovered)} executed={executed} failures={len(failures)}"
    )
    for failure in failures:
        print(f"FAIL {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
