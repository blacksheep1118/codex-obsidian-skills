#!/usr/bin/env python3
"""Create a deterministic, independently verifiable Notes learning package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO


def _bootstrap_vault_root_from_argv() -> None:
    """Let the standalone packager honor ``--root`` before importing vault helpers."""

    if os.environ.get("SOLVENOTES_VAULT_ROOT"):
        return
    for index, argument in enumerate(sys.argv[1:], start=1):
        if argument == "--root" and index + 1 < len(sys.argv):
            os.environ["SOLVENOTES_VAULT_ROOT"] = sys.argv[index + 1]
            return
        if argument.startswith("--root="):
            os.environ["SOLVENOTES_VAULT_ROOT"] = argument.split("=", 1)[1]
            return
    if any(argument in {"-h", "--help"} for argument in sys.argv[1:]):
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "solvenotes-mini-vault"
        if fixture.is_dir():
            # Import-time vault helpers still need a valid root, even though
            # argparse exits before any package input is read.
            os.environ["SOLVENOTES_VAULT_ROOT"] = str(fixture)


_bootstrap_vault_root_from_argv()

from archive_contract import portable_path_collision_issues, records_digest, safe_entry  # noqa: E402
from notes_utils import (  # noqa: E402
    ROOT,
    UnsafePathError,
    atomic_write_file,
    is_directory_without_symlinks,
    is_regular_file_without_symlinks,
    lexical_absolute_path,
    read_bytes_with_metadata,
)

DEFAULT_OUTPUT = Path(
    os.environ.get("SOLVENOTES_VAULT_EXPORT", "/tmp/solvenotes-notes-clean.zip")
)
MANIFEST_NAME = "PACKAGE-MANIFEST.json"
MANIFEST_SCHEMA_VERSION = 1
MINIMUM_ZIP_EPOCH = 315532800
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXCLUDE_DIRS = {
    ".git",
    ".github",
    ".pytest_cache",
    ".ruff_cache",
    "__MACOSX",
    "__pycache__",
    "dist",
}
EXCLUDE_FILE_NAMES = {
    ".DS_Store",
    ".DS_store",
    "workspace.json",
    "graph.json",
    MANIFEST_NAME,
}
EXCLUDE_SUFFIXES = {".pyc"}
RECOVERY_SIDECAR_RE = re.compile(
    r"^\..+\.conflict-\d+-(?:[0-9a-f]{16}|[0-9a-f]{32})$"
)


def output_path(raw: str | None) -> Path:
    if raw is None:
        return DEFAULT_OUTPUT
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    candidate = lexical_absolute_path(ROOT / path)
    try:
        candidate.relative_to(lexical_absolute_path(ROOT))
    except ValueError as exc:
        raise UnsafePathError(f"relative output escapes vault root: {raw}") from exc
    return candidate


def excluded(path: Path, outputs: set[Path]) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    parts = relative.parts
    if not parts:
        return True
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    if lexical_absolute_path(path) in outputs:
        return True
    name = path.name
    if name in EXCLUDE_FILE_NAMES:
        if name in {"workspace.json", "graph.json"}:
            return len(parts) >= 2 and parts[-2] == ".obsidian"
        return True
    if name.startswith("._"):
        return True
    if RECOVERY_SIDECAR_RE.fullmatch(name):
        return True
    return path.suffix in EXCLUDE_SUFFIXES


def _git_value(*args: str) -> str | None:
    if not (ROOT / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip()


def git_commit() -> str | None:
    value = _git_value("rev-parse", "HEAD")
    return value if value and FULL_SHA_RE.fullmatch(value) else None


def git_is_clean() -> bool | None:
    value = _git_value("status", "--porcelain", "--untracked-files=all")
    return None if value is None else not bool(value)


def deterministic_epoch() -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw is not None:
        try:
            return max(int(raw), MINIMUM_ZIP_EPOCH)
        except ValueError as exc:
            raise UnsafePathError(f"invalid SOURCE_DATE_EPOCH: {raw}") from exc
    value = _git_value("show", "-s", "--format=%ct", "HEAD")
    if value:
        try:
            return max(int(value), MINIMUM_ZIP_EPOCH)
        except ValueError:
            pass
    return MINIMUM_ZIP_EPOCH


def archive_timestamp(epoch: int) -> tuple[int, int, int, int, int, int]:
    value = datetime.fromtimestamp(max(epoch, MINIMUM_ZIP_EPOCH), tz=timezone.utc)
    return (value.year, value.month, value.day, value.hour, value.minute, value.second)


def lock_metadata() -> dict[str, object]:
    lock_path = ROOT / ".github" / "solvenotes-skills.lock.json"
    try:
        lock_path.lstat()
    except FileNotFoundError:
        return {"locked_skills_commit": None, "contract_version": None}
    try:
        lock_bytes, _metadata = read_bytes_with_metadata(lock_path, root=ROOT)
        payload = json.loads(lock_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnsafePathError(f"invalid Notes Skills lock: {lock_path}: {exc}") from exc
    commit = payload.get("commit") if isinstance(payload, dict) else None
    contract = payload.get("contract_version") if isinstance(payload, dict) else None
    if not isinstance(commit, str) or FULL_SHA_RE.fullmatch(commit) is None:
        raise UnsafePathError("Notes Skills lock commit must be a full lower-case SHA")
    if isinstance(contract, bool) or not isinstance(contract, int) or contract < 1:
        raise UnsafePathError("Notes Skills lock contract_version must be a positive integer")
    return {"locked_skills_commit": commit, "contract_version": contract}


def _normalized_mode(mode: int) -> int:
    return 0o100755 if mode & 0o111 else 0o100644


def _entry_record(relative: Path, data: bytes) -> dict[str, object]:
    return {
        "path": relative.as_posix(),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _add_archive_entry(
    archive: zipfile.ZipFile,
    relative: Path,
    data: bytes,
    mode: int,
    timestamp: tuple[int, int, int, int, int, int],
) -> None:
    name = relative.as_posix()
    if not safe_entry(name):
        raise UnsafePathError(f"unsafe cross-platform ZIP entry: {name}")
    info = zipfile.ZipInfo(name, date_time=timestamp)
    info.create_system = 3
    info.external_attr = _normalized_mode(mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data, compresslevel=9)


def _manifest(
    records: list[dict[str, object]],
    *,
    epoch: int,
) -> dict[str, object]:
    generated = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "package_type": "solvenotes-notes",
        "generated_at": generated.isoformat().replace("+00:00", "Z"),
        "source_date_epoch": epoch,
        "notes_commit": git_commit(),
        "source_clean": git_is_clean(),
        **lock_metadata(),
        "file_count": len(records),
        "archive_entry_count": len(records) + 1,
        "content_digest": records_digest(records),
        "archive_sha256": None,
        "files": records,
    }


def package(
    output: Path,
    manifest_output: Path | None = None,
) -> tuple[int, int]:
    if not is_directory_without_symlinks(ROOT, ROOT):
        raise UnsafePathError(
            f"vault root must be a regular non-symlink directory: {ROOT}"
        )
    if not output.is_absolute():
        output = output_path(os.fspath(output))
    output = lexical_absolute_path(output)
    sidecar = lexical_absolute_path(manifest_output) if manifest_output else None
    if sidecar == output:
        raise UnsafePathError("ZIP output and manifest output must be different files")
    output_set = {output}
    if sidecar is not None:
        output_set.add(sidecar)

    input_entries: list[tuple[Path, bytes, int]] = []
    for path in sorted(ROOT.rglob("*")):
        if not is_regular_file_without_symlinks(path, ROOT) or excluded(path, output_set):
            continue
        data, metadata = read_bytes_with_metadata(path, root=ROOT)
        relative = path.relative_to(ROOT)
        if not safe_entry(relative.as_posix()):
            raise UnsafePathError(
                f"unsafe cross-platform package path: {relative.as_posix()}"
            )
        input_entries.append((relative, data, metadata.st_mode))

    records = [_entry_record(relative, data) for relative, data, _mode in input_entries]
    collisions = portable_path_collision_issues(
        [str(record["path"]) for record in records] + [MANIFEST_NAME]
    )
    if collisions:
        raise UnsafePathError("; ".join(collisions))
    epoch = deterministic_epoch()
    manifest = _manifest(records, epoch=epoch)
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    timestamp = archive_timestamp(epoch)

    def build_archive(stream: BinaryIO) -> None:
        with zipfile.ZipFile(
            stream,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for relative, data, mode in input_entries:
                _add_archive_entry(archive, relative, data, mode, timestamp)
            info = zipfile.ZipInfo(MANIFEST_NAME, date_time=timestamp)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, manifest_bytes, compresslevel=9)
        expected_names = [str(item["path"]) for item in records] + [MANIFEST_NAME]
        stream.flush()
        stream.seek(0)
        try:
            with zipfile.ZipFile(stream, "r") as archive:
                if archive.namelist() != expected_names:
                    raise UnsafePathError(
                        "staged archive inventory differs from frozen input inventory"
                    )
                corrupt_name = archive.testzip()
                if corrupt_name is not None:
                    raise UnsafePathError(
                        f"staged archive failed CRC validation: {corrupt_name}"
                    )
        except zipfile.BadZipFile as exc:
            raise UnsafePathError(f"staged archive is not a readable ZIP: {exc}") from exc
        finally:
            stream.seek(0, os.SEEK_END)

    metadata = atomic_write_file(output, build_archive)
    if sidecar is not None:
        archive_bytes, _archive_metadata = read_bytes_with_metadata(output)
        sidecar_payload = dict(manifest)
        sidecar_payload["archive_sha256"] = hashlib.sha256(archive_bytes).hexdigest()
        sidecar_bytes = (
            json.dumps(sidecar_payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")

        def write_sidecar(stream: BinaryIO) -> None:
            stream.write(sidecar_bytes)

        atomic_write_file(sidecar, write_sidecar)
    return len(input_entries), metadata.st_size


def main() -> int:
    global ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="external notes vault root",
    )
    parser.add_argument(
        "--output",
        help="zip output path; defaults to /tmp/solvenotes-notes-clean.zip",
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        help="optional sidecar manifest containing the archive SHA-256",
    )
    args = parser.parse_args()

    ROOT = lexical_absolute_path(args.root)
    output = output_path(args.output)
    manifest_output = (
        lexical_absolute_path(args.manifest_output)
        if args.manifest_output is not None
        else None
    )
    count, size = package(output, manifest_output)
    print(f"package_path {output}")
    print(f"package_files {count}")
    print(f"package_size_bytes {size}")
    if manifest_output is not None:
        print(f"package_manifest_path {manifest_output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
