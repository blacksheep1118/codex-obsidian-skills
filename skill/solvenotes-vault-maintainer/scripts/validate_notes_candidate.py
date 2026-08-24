#!/usr/bin/env python3
"""Validate a candidate Skills commit against Notes without changing its lock."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from run_with_timeout import run as run_process
from update_notes_skill_lock import (
    resolve_commit,
    verify_repository_identity,
    verify_target_tree,
)
from vault_contract import (
    CURRENT_LOCK_SCHEMA_VERSION,
    MAINTAINER_SKILL,
    SKILLS_REPOSITORY,
)


def _run(
    command: list[str], *, cwd: Path, env: dict[str, str], timeout: int, label: str
) -> None:
    returncode = run_process(command, timeout, label, cwd=cwd, env=env)
    if returncode:
        raise ValueError(f"{label} failed with exit code {returncode}")


def _add_detached_worktree(skills_root: Path, checkout: Path, commit: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(skills_root), "worktree", "add", "--detach", str(checkout), commit],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"cannot create candidate Skills worktree: {detail}")


def _remove_worktree(skills_root: Path, checkout: Path) -> None:
    result = subprocess.run(
        ["git", "-C", str(skills_root), "worktree", "remove", str(checkout)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"cannot remove candidate Skills worktree: {detail}")


def candidate_lock(commit: str, target: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": CURRENT_LOCK_SCHEMA_VERSION,
        "repository": SKILLS_REPOSITORY,
        "commit": commit,
        "maintainer_skill": MAINTAINER_SKILL,
        "contract_version": target["contract_version"],
        "skills": target["skills"],
        "dependency_graph_digest": target["dependency_graph_digest"],
    }


def validate_candidate(
    notes_root: Path,
    skills_root: Path,
    ref: str,
    *,
    verify_level: str,
    python_bin: str,
    allow_local_source: bool,
    verify_package: bool = False,
) -> dict[str, object]:
    verify_repository_identity(skills_root, allow_local_source=allow_local_source)
    commit = resolve_commit(skills_root, ref)
    target = verify_target_tree(skills_root, commit, level=verify_level)
    lock_payload = candidate_lock(commit, target)

    with tempfile.TemporaryDirectory(prefix="solvenotes-candidate-") as temporary_raw:
        temporary = Path(temporary_raw)
        checkout = temporary / "source"
        _add_detached_worktree(skills_root, checkout, commit)
        try:
            installed = temporary / "installed"
            environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            installer = checkout / "scripts" / "install_skill.py"
            _run(
                [
                    python_bin,
                    str(installer),
                    "--skill",
                    MAINTAINER_SKILL,
                    "--destination",
                    str(installed),
                    "--self-check-level",
                    "smoke",
                ],
                cwd=temporary,
                env=environment,
                timeout=180,
                label="candidate installed smoke",
            )

            candidate_lock_path = temporary / "candidate-lock.json"
            candidate_lock_path.write_text(
                json.dumps(lock_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            environment.update(
                {
                    "SOLVENOTES_VAULT_ROOT": str(notes_root),
                    "SOLVENOTES_SKILLS_LOCK_OVERRIDE": str(candidate_lock_path),
                    "SOLVENOTES_PYTHON_BIN": python_bin,
                }
            )
            dev_check = installed / MAINTAINER_SKILL / "scripts" / "dev_check.sh"
            _run(
                ["bash", str(dev_check), "vault-full"],
                cwd=temporary,
                env=environment,
                timeout=900,
                label="candidate real Notes vault-full",
            )

            package_entries: int | None = None
            if verify_package:
                notes_zip = temporary / "notes.zip"
                notes_manifest = temporary / "notes-PACKAGE-MANIFEST.json"
                package_script = installed / MAINTAINER_SKILL / "scripts" / "package_vault.py"
                verifier_script = (
                    installed / MAINTAINER_SKILL / "scripts" / "verify_vault_package.py"
                )
                _run(
                    [
                        python_bin,
                        str(package_script),
                        "--root",
                        str(notes_root),
                        "--output",
                        str(notes_zip),
                        "--manifest-output",
                        str(notes_manifest),
                    ],
                    cwd=temporary,
                    env=environment,
                    timeout=300,
                    label="candidate Notes package",
                )
                _run(
                    [
                        python_bin,
                        str(verifier_script),
                        str(notes_zip),
                        "--sidecar",
                        str(notes_manifest),
                    ],
                    cwd=temporary,
                    env=environment,
                    timeout=120,
                    label="candidate Notes package verification",
                )
                package_entries = json.loads(notes_manifest.read_text(encoding="utf-8"))[
                    "archive_entry_count"
                ]
            return {
                "ok": True,
                "commit": commit,
                "contract_version": target["contract_version"],
                "skills": target["skills"],
                "dependency_graph_digest": target["dependency_graph_digest"],
                "package_verified": verify_package,
                "notes_package_entries": package_entries,
                "formal_lock_modified": False,
            }
        finally:
            _remove_worktree(skills_root, checkout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notes-root", type=Path, required=True)
    parser.add_argument("--skills-root", type=Path, required=True)
    parser.add_argument("--skills-ref", required=True)
    parser.add_argument("--verify-level", choices=("metadata", "smoke", "full"), default="full")
    parser.add_argument("--python-bin", default=os.environ.get("SOLVENOTES_PYTHON_BIN", sys.executable))
    parser.add_argument("--allow-local-source", action="store_true")
    parser.add_argument(
        "--verify-package",
        action="store_true",
        help=(
            "also build and verify a temporary Notes package; use only when the user "
            "requests an export and local workspace guidance permits package mode"
        ),
    )
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = validate_candidate(
            args.notes_root.expanduser().absolute(),
            args.skills_root.expanduser().absolute(),
            args.skills_ref,
            verify_level=args.verify_level,
            python_bin=args.python_bin,
            allow_local_source=args.allow_local_source,
            verify_package=args.verify_package,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
