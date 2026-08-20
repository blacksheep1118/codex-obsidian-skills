#!/usr/bin/env python3
"""Create a clean shareable zip package of the Obsidian vault."""

from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import BinaryIO

from notes_utils import (
    ROOT,
    UnsafePathError,
    atomic_write_file,
    is_directory_without_symlinks,
    is_regular_file_without_symlinks,
    lexical_absolute_path,
    read_bytes_with_metadata,
)

DEFAULT_OUTPUT = Path(os.environ.get("SOLVENOTES_VAULT_EXPORT", "/tmp/solvenotes-notes-clean.zip"))
EXCLUDE_DIRS = {
    ".git",
    ".github",
    ".pytest_cache",
    ".ruff_cache",
    "__MACOSX",
    "__pycache__",
    "dist",
}
EXCLUDE_FILE_NAMES = {".DS_Store", ".DS_store", "workspace.json", "graph.json"}
EXCLUDE_SUFFIXES = {".pyc"}
RECOVERY_SIDECAR_RE = re.compile(r"^\..+\.conflict-\d+-(?:[0-9a-f]{16}|[0-9a-f]{32})$")


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


def excluded(path: Path, output: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    parts = relative.parts
    if not parts:
        return True
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    if lexical_absolute_path(path) == lexical_absolute_path(output):
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


def _add_archive_entry(archive: zipfile.ZipFile, path: Path) -> None:
    """Add one safely opened vault file to an archive."""

    data, metadata = read_bytes_with_metadata(path, root=ROOT)
    info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix())
    info.create_system = 3
    info.external_attr = (metadata.st_mode & 0xFFFF) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def package(output: Path) -> tuple[int, int]:
    if not is_directory_without_symlinks(ROOT, ROOT):
        raise UnsafePathError(f"vault root must be a regular non-symlink directory: {ROOT}")
    if not output.is_absolute():
        output = output_path(os.fspath(output))
    file_count = 0
    # Freeze the source inventory before atomic publication creates its hidden
    # same-directory staging file.  Every frozen path is still reopened safely
    # while writing, so a later path swap fails rather than following a link.
    input_paths = [
        path
        for path in sorted(ROOT.rglob("*"))
        if is_regular_file_without_symlinks(path, ROOT) and not excluded(path, output)
    ]

    def build_archive(stream: BinaryIO) -> None:
        nonlocal file_count
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in input_paths:
                _add_archive_entry(archive, path)
                file_count += 1
        expected_names = [path.relative_to(ROOT).as_posix() for path in input_paths]
        stream.flush()
        stream.seek(0)
        try:
            with zipfile.ZipFile(stream, "r") as archive:
                if archive.namelist() != expected_names:
                    raise UnsafePathError("staged archive inventory differs from frozen input inventory")
                corrupt_name = archive.testzip()
                if corrupt_name is not None:
                    raise UnsafePathError(f"staged archive failed CRC validation: {corrupt_name}")
        except zipfile.BadZipFile as exc:
            raise UnsafePathError(f"staged archive is not a readable ZIP: {exc}") from exc
        finally:
            stream.seek(0, os.SEEK_END)

    metadata = atomic_write_file(output, build_archive)
    return file_count, metadata.st_size


def main() -> int:
    global ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT, help="external notes vault root")
    parser.add_argument("--output", help="zip output path; defaults to /tmp/solvenotes-notes-clean.zip")
    args = parser.parse_args()

    ROOT = lexical_absolute_path(args.root)
    output = output_path(args.output)
    count, size = package(output)
    print(f"package_path {output}")
    print(f"package_files {count}")
    print(f"package_size_bytes {size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
