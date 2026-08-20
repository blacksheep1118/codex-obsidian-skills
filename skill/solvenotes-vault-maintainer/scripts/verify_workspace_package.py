#!/usr/bin/env python3
"""Verify a workspace ZIP before extraction or delivery."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from vault_contract import (
    CURRENT_LOCK_SCHEMA_VERSION,
    INSTALL_EXCLUDED_PARTS,
    REQUIRED_SKILLS,
    dependency_graph_digest,
)

FORBIDDEN_PARTS = {".git", "__MACOSX", "__pycache__", ".pytest_cache", ".ruff_cache"}
FORBIDDEN_NAMES = {"workspace.json", "graph.json", ".DS_Store"}
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_REPOSITORY = "blacksheep1118/codex-obsidian-skills"
EXPECTED_MAINTAINER = "solvenotes-vault-maintainer"


def safe_entry(name: str) -> bool:
    path = PurePosixPath(name)
    windows_path = PureWindowsPath(name)
    return bool(name) and "\\" not in name and not path.is_absolute() and not windows_path.is_absolute() and not windows_path.drive and ".." not in path.parts and not any(
        part in FORBIDDEN_PARTS or part.startswith("._") or part in FORBIDDEN_NAMES
        for part in path.parts
    )


def records_digest(records: list[dict[str, object]]) -> str:
    canonical = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _skill_digest_from_manifest(files: list[dict[str, object]], name: str) -> str:
    prefix = f"skills/skill/{name}/"
    records = []
    for item in files:
        path = item.get("path") if isinstance(item, dict) else None
        if not isinstance(path, str) or not path.startswith(prefix):
            continue
        relative = path.removeprefix(prefix)
        relative_path = PurePosixPath(relative)
        if (
            relative == ".codex-skill-install.json"
            or any(part in INSTALL_EXCLUDED_PARTS for part in relative_path.parts)
        ):
            continue
        records.append(
            {"path": relative, "size": item.get("size"), "sha256": item.get("sha256")}
        )
    return records_digest(sorted(records, key=lambda item: str(item["path"])))


def verify(archive_path: Path, sidecar_path: Path | None = None) -> dict[str, object]:
    issues: list[str] = []
    archive_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            issues.append("duplicate ZIP entries")
        for info in infos:
            if not safe_entry(info.filename):
                issues.append(f"unsafe ZIP entry: {info.filename}")
            if info.is_dir():
                issues.append(f"directory ZIP entry is not allowed: {info.filename}")
            mode = (info.external_attr >> 16) & 0xFFFF
            if mode and (mode & 0o170000) == 0o120000:
                issues.append(f"symbolic-link ZIP entry: {info.filename}")
        try:
            manifest = json.loads(archive.read("BUILD-MANIFEST.json").decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            issues.append(f"invalid BUILD-MANIFEST.json: {exc}")
            manifest = None
        if not isinstance(manifest, dict):
            issues.append("BUILD-MANIFEST.json must contain a JSON object")
        else:
            if manifest.get("schema_version") != 3:
                issues.append("unsupported BUILD-MANIFEST schema_version")
            files = manifest.get("files")
            actual = [name for name in names if name != "BUILD-MANIFEST.json"]
            if not isinstance(files, list):
                issues.append("manifest files must be a list")
                files = []
            else:
                expected = [str(item.get("path")) for item in files if isinstance(item, dict)]
                if expected != actual:
                    issues.append("manifest file list does not match ZIP order")
                if manifest.get("file_count") != len(files):
                    issues.append("manifest file_count does not match file records")
                if manifest.get("archive_entry_count") != len(names):
                    issues.append("manifest archive_entry_count does not match ZIP")
                for item in files:
                    if not isinstance(item, dict):
                        issues.append("manifest file record is not an object")
                        continue
                    name = item.get("path")
                    if not isinstance(name, str) or name not in actual:
                        issues.append(f"manifest references missing entry: {name}")
                        continue
                    digest = hashlib.sha256(archive.read(name)).hexdigest()
                    if digest != item.get("sha256"):
                        issues.append(f"manifest digest mismatch: {name}")
                if manifest.get("content_digest") != records_digest(files):
                    issues.append("manifest content_digest does not match file records")

            skills_commit = manifest.get("skills_commit")
            locked_commit = manifest.get("notes_locked_skills_commit")
            contract_version = manifest.get("contract_version")
            lock_name = "notes/.github/solvenotes-skills.lock.json"
            lock_payload = None
            if lock_name not in names:
                issues.append(f"package is missing {lock_name}")
            else:
                try:
                    lock_payload = json.loads(archive.read(lock_name).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    issues.append(f"invalid {lock_name}: {exc}")
            coherent_from_content = (
                isinstance(skills_commit, str)
                and FULL_SHA_RE.fullmatch(skills_commit) is not None
                and locked_commit == skills_commit
                and isinstance(contract_version, int)
                and isinstance(lock_payload, dict)
                and lock_payload.get("schema_version") == CURRENT_LOCK_SCHEMA_VERSION
                and lock_payload.get("repository") == EXPECTED_REPOSITORY
                and lock_payload.get("maintainer_skill") == EXPECTED_MAINTAINER
                and lock_payload.get("commit") == skills_commit
                and lock_payload.get("contract_version") == contract_version
                and isinstance(lock_payload.get("skills"), dict)
                and all(
                    isinstance(lock_payload["skills"].get(name), dict)
                    and lock_payload["skills"][name].get("content_digest")
                    == _skill_digest_from_manifest(files, name)
                    for name in REQUIRED_SKILLS
                )
            )
            if isinstance(lock_payload, dict):
                graph_name = "skills/skill/dependencies.json"
                try:
                    graph_payload = json.loads(archive.read(graph_name).decode("utf-8"))
                    graph = graph_payload.get("required") if isinstance(graph_payload, dict) else None
                    graph_ok = (
                        isinstance(graph, dict)
                        and dependency_graph_digest(graph)
                        == lock_payload.get("dependency_graph_digest")
                    )
                except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
                    graph_ok = False
                coherent_from_content = coherent_from_content and graph_ok
            if manifest.get("coherent_workspace") is not coherent_from_content:
                issues.append("manifest coherent_workspace does not match lock and Skills fields")
            if not coherent_from_content:
                issues.append("package is not a coherent locked workspace")
    if sidecar_path is not None:
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(f"invalid sidecar manifest: {exc}")
            sidecar = None
        if not isinstance(sidecar, dict):
            issues.append("sidecar manifest must contain a JSON object")
        else:
            if sidecar.get("archive_sha256") != archive_sha256:
                issues.append("sidecar archive_sha256 does not match the ZIP")
            if isinstance(manifest, dict):
                comparable = dict(sidecar)
                comparable["archive_sha256"] = None
                if comparable != manifest:
                    issues.append("sidecar fields do not match BUILD-MANIFEST.json")
    return {
        "ok": not issues,
        "issues": issues,
        "entries": len(names),
        "archive_sha256": archive_sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sidecar", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = verify(
        args.archive.expanduser().absolute(),
        args.sidecar.expanduser().absolute() if args.sidecar else None,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"workspace_package_entries {payload['entries']}")
        print(f"workspace_package_issues {len(payload['issues'])}")
        print(f"workspace_package_sha256 {payload['archive_sha256']}")
        for issue in payload["issues"]:
            print(f"ISSUE {issue}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
