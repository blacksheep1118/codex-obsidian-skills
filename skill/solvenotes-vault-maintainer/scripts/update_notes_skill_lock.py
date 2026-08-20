#!/usr/bin/env python3
"""Update the Notes-to-Skills lock after validating a local Skills ref.

The command is deliberately dry-run by default. It never commits or pushes.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from vault_contract import (
    ALGORITHM_JOB_SKILL,
    CURRENT_LOCK_SCHEMA_VERSION,
    CURRENT_VAULT_CONTRACT_VERSION,
    FULL_SHA_RE,
    MAINTAINER_SKILL,
    REQUIRED_SKILLS,
    SKILLS_REPOSITORY,
    dependency_graph_digest,
    lock_path,
)

REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
TARGET_FILES = (
    "skill/dependencies.json",
    "skill/solvenotes-vault-maintainer/SKILL.md",
    "skill/solvenotes-vault-maintainer/scripts/dev_check.sh",
    "skill/solvenotes-vault-maintainer/scripts/check_skills_lock.py",
    "skill/solvenotes-vault-maintainer/scripts/validate_skill.py",
    "skill/solvenotes-vault-maintainer/scripts/validate_notes_candidate.py",
    "skill/solvenotes-vault-maintainer/scripts/vault_contract.py",
    "skill/solvenotes-vault-maintainer/scripts/package_vault.py",
    "skill/solvenotes-vault-maintainer/scripts/package_workspace.py",
    "skill/solvenotes-vault-maintainer/scripts/verify_workspace_package.py",
    "skill/solvenotes-vault-maintainer/scripts/run_with_timeout.py",
    "skill/solvenotes-vault-maintainer/requirements-dev.txt",
    "skill/algorithm-job-notes-for-obsidian/SKILL.md",
    "skill/algorithm-job-notes-for-obsidian/scripts/check_algorithm_job_vault.py",
    "skill/algorithm-job-notes-for-obsidian/scripts/check_cpp_examples.py",
    "skill/algorithm-job-notes-for-obsidian/scripts/validate_skill.py",
)
TARGET_FIXTURE_PREFIX = "skill/solvenotes-vault-maintainer/fixtures/solvenotes-mini-vault/"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def normalize_repository_url(value: str) -> str:
    """Return a comparable ``owner/repository`` identity for common Git URLs."""

    raw = value.strip()
    if raw.startswith("git@") and ":" in raw:
        raw = raw.split(":", 1)[1]
    else:
        parsed = urlsplit(raw)
        if parsed.netloc:
            raw = parsed.path.lstrip("/")
    return raw.rstrip("/").removesuffix(".git").lower()


def git_origin_url(skills_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(skills_root), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"cannot inspect Skills origin URL: {exc}") from exc
    if result.returncode:
        return None
    return result.stdout.strip() or None


def verify_repository_identity(skills_root: Path, *, allow_local_source: bool = False) -> None:
    origin = git_origin_url(skills_root)
    if origin is None:
        if allow_local_source:
            return
        raise ValueError(
            f"Skills repository has no remote.origin.url; expected {SKILLS_REPOSITORY} "
            "(use --allow-local-source only for an explicit isolated local test)"
        )
    actual = normalize_repository_url(origin)
    if actual != SKILLS_REPOSITORY:
        if allow_local_source and (origin.startswith(("/", "./", "../")) or origin.startswith("file://")):
            return
        raise ValueError(
            f"Skills origin does not match {SKILLS_REPOSITORY}: {origin!r}"
        )


def safe_extract_tar(tar: tarfile.TarFile, destination: Path) -> None:
    """Extract a Git archive only after rejecting traversal and link members."""

    seen: set[str] = set()
    members = tar.getmembers()
    for member in members:
        name = member.name
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or ".." in path.parts
            or name in seen
        ):
            raise ValueError(f"unsafe Skills archive member: {name!r}")
        seen.add(name)
        if member.issym() or member.islnk():
            raise ValueError(f"link member is not allowed in Skills archive: {name!r}")
        if not (member.isdir() or member.isreg()):
            raise ValueError(f"unsupported Skills archive member: {name!r}")
        target = destination.joinpath(*path.parts)
        try:
            target.relative_to(destination)
        except ValueError as exc:
            raise ValueError(f"Skills archive member escapes extraction root: {name!r}") from exc
    for member in members:
        tar.extract(member, path=destination, set_attrs=False)


def resolve_commit(skills_root: Path, ref: str) -> str:
    if not ref or not REF_RE.fullmatch(ref) or ref.startswith("-"):
        raise ValueError("skills-ref must be a non-empty Git ref without shell punctuation")
    try:
        result = subprocess.run(
            ["git", "-C", str(skills_root), "rev-parse", "--verify", f"{ref}^{{commit}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"cannot resolve Skills ref: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or f"git exited {result.returncode}"
        raise ValueError(f"Skills ref does not resolve to a commit: {detail}")
    commit = result.stdout.strip()
    if not FULL_SHA_RE.fullmatch(commit):
        raise ValueError(f"resolved Skills ref is not a full SHA: {commit!r}")
    return commit


def current_lock(notes_root: Path) -> dict[str, object] | None:
    path = lock_path(notes_root)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"existing lock is not a JSON object: {path}")
    return value


def target_blob_bytes(skills_root: Path, commit: str, relative: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(skills_root), "show", f"{commit}:{relative}"],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"cannot read {relative} from target commit {commit}: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip() or f"git exited {result.returncode}"
        raise ValueError(f"target commit {commit} is missing {relative}: {detail}")
    return result.stdout


def target_blob(skills_root: Path, commit: str, relative: str) -> str:
    try:
        return target_blob_bytes(skills_root, commit, relative).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"target commit {commit} has non-UTF-8 text: {relative}: {exc}") from exc


def target_paths(skills_root: Path, commit: str) -> list[str]:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(skills_root),
                "-c",
                "core.quotePath=false",
                "ls-tree",
                "-r",
                "--name-only",
                "-z",
                commit,
            ],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"cannot inspect target Git tree {commit}: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip() or f"git exited {result.returncode}"
        raise ValueError(f"target commit cannot be listed: {detail}")
    try:
        return [
            item.decode("utf-8")
            for item in result.stdout.split(b"\0")
            if item
        ]
    except UnicodeDecodeError as exc:
        raise ValueError(f"target commit contains a non-UTF-8 path: {exc}") from exc


def target_content_digest(
    skills_root: Path, commit: str, paths: list[str], skill_name: str
) -> str:
    records: list[dict[str, object]] = []
    prefix = f"skill/{skill_name}/"
    for relative in paths:
        if not relative.startswith(prefix) or relative.endswith("/"):
            continue
        data = target_blob_bytes(skills_root, commit, relative)
        records.append(
            {
                "path": relative.removeprefix(prefix),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    canonical = json.dumps(
        sorted(records, key=lambda item: item["path"]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify_target_tree(skills_root: Path, commit: str, *, level: str) -> dict[str, object]:
    paths = target_paths(skills_root, commit)
    path_set = set(paths)
    missing = [relative for relative in TARGET_FILES if relative not in path_set]
    if not any(path.startswith(TARGET_FIXTURE_PREFIX) for path in paths):
        missing.append(TARGET_FIXTURE_PREFIX + "<directory>")
    if missing:
        raise ValueError(
            f"target commit {commit} does not contain the required maintainer tree: "
            + ", ".join(missing)
        )
    dependency_payload = json.loads(target_blob(skills_root, commit, "skill/dependencies.json"))
    required = dependency_payload.get("required") if isinstance(dependency_payload, dict) else None
    if not isinstance(required, dict):
        raise ValueError(f"target commit {commit} has no valid required dependency graph")
    graph: dict[str, list[str]] = {}
    for name in REQUIRED_SKILLS:
        values = required.get(name, [])
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise ValueError(f"target commit {commit} has invalid dependencies for {name}")
        graph[name] = sorted(dict.fromkeys(values))
    if graph.get(MAINTAINER_SKILL) != [ALGORITHM_JOB_SKILL] or graph.get(ALGORITHM_JOB_SKILL):
        raise ValueError(
            f"target commit {commit} does not expose the required maintainer dependency closure"
        )
    skill_text = target_blob(
        skills_root, commit, "skill/solvenotes-vault-maintainer/SKILL.md"
    )
    if not re.search(r"^name:\s*solvenotes-vault-maintainer\s*$", skill_text, re.MULTILINE):
        raise ValueError(f"target commit {commit} has invalid maintainer SKILL.md metadata")
    contract_text = target_blob(
        skills_root,
        commit,
        "skill/solvenotes-vault-maintainer/scripts/vault_contract.py",
    )
    match = re.search(r"^CURRENT_VAULT_CONTRACT_VERSION\s*=\s*(\d+)\s*$", contract_text, re.MULTILINE)
    if not match:
        raise ValueError(f"target commit {commit} has no readable vault contract version")
    contract_version = int(match.group(1))
    for relative in (
        "skill/solvenotes-vault-maintainer/scripts/check_skills_lock.py",
        "skill/solvenotes-vault-maintainer/scripts/validate_skill.py",
        "skill/solvenotes-vault-maintainer/scripts/validate_notes_candidate.py",
        "skill/solvenotes-vault-maintainer/scripts/vault_contract.py",
        "skill/solvenotes-vault-maintainer/scripts/package_vault.py",
        "skill/solvenotes-vault-maintainer/scripts/package_workspace.py",
        "skill/solvenotes-vault-maintainer/scripts/verify_workspace_package.py",
        "skill/solvenotes-vault-maintainer/scripts/run_with_timeout.py",
        "skill/algorithm-job-notes-for-obsidian/scripts/check_algorithm_job_vault.py",
        "skill/algorithm-job-notes-for-obsidian/scripts/check_cpp_examples.py",
        "skill/algorithm-job-notes-for-obsidian/scripts/validate_skill.py",
    ):
        try:
            ast.parse(target_blob(skills_root, commit, relative), filename=relative)
        except SyntaxError as exc:
            raise ValueError(f"target commit {commit} has invalid Python: {relative}: {exc}") from exc
    report: dict[str, object] = {
        "commit": commit,
        "contract_version": contract_version,
        "skills": {
            name: {
                "content_digest": target_content_digest(skills_root, commit, paths, name)
            }
            for name in REQUIRED_SKILLS
        },
        "dependency_graph_digest": dependency_graph_digest(graph),
        "tree_paths": len(paths),
        "level": level,
    }
    if level in {"smoke", "full"}:
        with tempfile.TemporaryDirectory(prefix="solvenotes-lock-target-") as temporary:
            extracted = Path(temporary) / "repo"
            extracted.mkdir()
            archive = subprocess.check_output(
                ["git", "-C", str(skills_root), "archive", commit], timeout=60
            )
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
                safe_extract_tar(tar, extracted)
            installer = extracted / "scripts" / "install_skill.py"
            if not installer.is_file():
                raise ValueError(f"target commit {commit} has no install_skill.py for installed smoke")
            destination = Path(temporary) / "installed"
            python_bin = os.fspath(Path(os.environ.get("SOLVENOTES_PYTHON_BIN", sys.executable)))
            result = subprocess.run(
                [
                    python_bin,
                    str(installer),
                    "--skill",
                    MAINTAINER_SKILL,
                    "--destination",
                    str(destination),
                    "--self-check",
                ],
                cwd=temporary,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
            )
            if result.returncode:
                detail = (result.stderr or result.stdout).strip()
                raise ValueError(f"target commit {commit} install smoke failed: {detail}")
            validator = destination / MAINTAINER_SKILL / "scripts" / "validate_skill.py"
            if not validator.is_file():
                raise ValueError(f"target commit {commit} did not install its maintainer validator")
            result = subprocess.run(
                [python_bin, str(validator)],
                cwd=temporary,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
            )
            if result.returncode:
                detail = (result.stderr or result.stdout).strip()
                raise ValueError(f"target commit {commit} installed validator smoke failed: {detail}")
    if level == "full":
        with tempfile.TemporaryDirectory(prefix="solvenotes-lock-tests-") as temporary:
            extracted = Path(temporary) / "repo"
            extracted.mkdir()
            archive = subprocess.check_output(
                ["git", "-C", str(skills_root), "archive", commit], timeout=60
            )
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
                safe_extract_tar(tar, extracted)
            result = subprocess.run(
                [os.fspath(Path(os.environ.get("SOLVENOTES_PYTHON_BIN", sys.executable))), "-m", "pytest", "-q", "tests"],
                cwd=extracted / "skill" / MAINTAINER_SKILL,
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
                env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
            )
            if result.returncode:
                detail = (result.stderr or result.stdout).strip()
                raise ValueError(f"target commit {commit} tests failed: {detail}")
    return report


def write_lock(notes_root: Path, payload: dict[str, object]) -> None:
    destination = lock_path(notes_root)
    if destination.parent.exists() and destination.parent.is_symlink():
        raise ValueError(f"lock directory must not be a symlink: {destination.parent}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.parent.is_dir():
        raise ValueError(f"lock directory must be a regular directory: {destination.parent}")
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notes-root", type=Path, required=True)
    parser.add_argument("--skills-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--skills-ref", required=True)
    parser.add_argument("--verify-level", choices=("metadata", "smoke", "full"), default="smoke")
    parser.add_argument("--require-ancestor-of", default=None, help="require target to be an ancestor of this ref")
    parser.add_argument(
        "--allow-local-source",
        action="store_true",
        help="allow an isolated local clone without the expected GitHub origin; never use for a published lock",
    )
    parser.add_argument("--dry-run", action="store_true", help="validate and print the proposed lock without writing")
    parser.add_argument("--write", action="store_true", help="write the validated lock; default is dry-run")
    args = parser.parse_args(argv)
    if args.write and args.dry_run:
        parser.error("--write and --dry-run are mutually exclusive")
    notes_root = args.notes_root.resolve()
    skills_root = args.skills_root.resolve()
    try:
        verify_repository_identity(skills_root, allow_local_source=args.allow_local_source)
        commit = resolve_commit(skills_root, args.skills_ref)
        if args.require_ancestor_of:
            result = subprocess.run(
                ["git", "-C", str(skills_root), "merge-base", "--is-ancestor", commit, args.require_ancestor_of],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode:
                raise ValueError(f"target commit is not an ancestor of {args.require_ancestor_of}")
        target = verify_target_tree(skills_root, commit, level=args.verify_level)
        contract_version = int(target["contract_version"])
        if contract_version != CURRENT_VAULT_CONTRACT_VERSION:
            raise ValueError(
                f"source contract mismatch: expected {CURRENT_VAULT_CONTRACT_VERSION}, got {contract_version}"
            )
        old = current_lock(notes_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    payload = {
        "schema_version": CURRENT_LOCK_SCHEMA_VERSION,
        "repository": SKILLS_REPOSITORY,
        "commit": commit,
        "maintainer_skill": MAINTAINER_SKILL,
        "contract_version": contract_version,
        "skills": target["skills"],
        "dependency_graph_digest": target["dependency_graph_digest"],
    }
    print(f"lock_path {lock_path(notes_root)}")
    print("current_lock " + (json.dumps(old, ensure_ascii=False, sort_keys=True) if old else "MISSING"))
    print("proposed_lock " + json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if not args.write:
        print("mode dry-run")
        return 0
    write_lock(notes_root, payload)
    print("mode write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
