#!/usr/bin/env python3
"""Verify a Solvenotes Notes learning package without extracting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from io import BytesIO
from pathlib import Path

from archive_contract import (
    MAX_ARCHIVE_INPUT_BYTES,
    MAX_MANIFEST_BYTES,
    archive_budget_issues,
    is_symlink_entry,
    member_digest,
    portable_path_collision_issues,
    read_member_limited,
    records_digest,
    safe_entry,
)
from safe_io import ensure_safe_input_file, read_bytes_no_follow

MANIFEST_NAME = "PACKAGE-MANIFEST.json"
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _read_json(data: bytes, label: str, issues: list[str]) -> object | None:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        issues.append(f"invalid {label}: {exc}")
        return None


def verify(archive_path: Path, sidecar_path: Path | None = None) -> dict[str, object]:
    issues: list[str] = []
    try:
        archive_bytes = read_bytes_no_follow(
            ensure_safe_input_file(archive_path), max_bytes=MAX_ARCHIVE_INPUT_BYTES
        )
    except (OSError, ValueError) as exc:
        return {"ok": False, "issues": [str(exc)], "entries": 0, "archive_sha256": ""}
    archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    names: list[str] = []
    manifest: object | None = None
    try:
        with zipfile.ZipFile(BytesIO(archive_bytes), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            budget_issues = archive_budget_issues(infos)
            if budget_issues:
                return {
                    "ok": False,
                    "issues": budget_issues,
                    "entries": len(names),
                    "archive_sha256": archive_sha256,
                }
            if len(names) != len(set(names)):
                issues.append("duplicate ZIP entries")
            issues.extend(portable_path_collision_issues(names))
            for info in infos:
                if not safe_entry(info.filename):
                    issues.append(f"unsafe ZIP entry: {info.filename}")
                if info.is_dir():
                    issues.append(f"directory ZIP entry is not allowed: {info.filename}")
                if is_symlink_entry(info):
                    issues.append(f"symbolic-link ZIP entry: {info.filename}")
            try:
                manifest = _read_json(
                    read_member_limited(archive, MANIFEST_NAME), MANIFEST_NAME, issues
                )
            except KeyError:
                issues.append(f"package is missing {MANIFEST_NAME}")

            if not isinstance(manifest, dict):
                issues.append(f"{MANIFEST_NAME} must contain a JSON object")
            else:
                if manifest.get("schema_version") != 1:
                    issues.append("unsupported Notes package manifest schema_version")
                if manifest.get("package_type") != "solvenotes-notes":
                    issues.append("unexpected Notes package_type")
                files = manifest.get("files")
                actual = [name for name in names if name != MANIFEST_NAME]
                if not isinstance(files, list):
                    issues.append("manifest files must be a list")
                    files = []
                expected = [
                    str(item.get("path"))
                    for item in files
                    if isinstance(item, dict)
                ]
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
                    size, digest = member_digest(archive, name)
                    if size != item.get("size"):
                        issues.append(f"manifest size mismatch: {name}")
                    if digest != item.get("sha256"):
                        issues.append(f"manifest digest mismatch: {name}")
                if manifest.get("content_digest") != records_digest(files):
                    issues.append("manifest content_digest does not match file records")
                notes_commit = manifest.get("notes_commit")
                if notes_commit is not None and (
                    not isinstance(notes_commit, str)
                    or FULL_SHA_RE.fullmatch(notes_commit) is None
                ):
                    issues.append("manifest notes_commit is not a full lower-case SHA")
                locked_commit = manifest.get("locked_skills_commit")
                if locked_commit is not None and (
                    not isinstance(locked_commit, str)
                    or FULL_SHA_RE.fullmatch(locked_commit) is None
                ):
                    issues.append("manifest locked_skills_commit is invalid")
                contract = manifest.get("contract_version")
                if contract is not None and (
                    isinstance(contract, bool) or not isinstance(contract, int) or contract < 1
                ):
                    issues.append("manifest contract_version is invalid")
            corrupt_name = archive.testzip()
            if corrupt_name is not None:
                issues.append(f"ZIP CRC validation failed: {corrupt_name}")
    except (zipfile.BadZipFile, EOFError, RuntimeError, ValueError) as exc:
        issues.append(f"archive is not a readable ZIP: {exc}")

    if sidecar_path is not None:
        try:
            sidecar_bytes = read_bytes_no_follow(
                ensure_safe_input_file(sidecar_path), max_bytes=MAX_MANIFEST_BYTES
            )
            sidecar = _read_json(sidecar_bytes, "sidecar manifest", issues)
        except (OSError, ValueError) as exc:
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
                    issues.append("sidecar fields do not match PACKAGE-MANIFEST.json")

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
        print(f"notes_package_entries {payload['entries']}")
        print(f"notes_package_issues {len(payload['issues'])}")
        print(f"notes_package_sha256 {payload['archive_sha256']}")
        for issue in payload["issues"]:
            print(f"ISSUE {issue}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
