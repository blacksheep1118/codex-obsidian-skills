#!/usr/bin/env python3
"""Create a clean release zip for this skill collection."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "__MACOSX",
    "__pycache__",
    "build",
    "converted_pptx",
}
EXCLUDED_FILE_NAMES = {".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc"}


def should_exclude(path: Path, is_dir: bool) -> bool:
    parts = path.parts
    if any(part in EXCLUDED_DIR_NAMES for part in parts):
        return True
    if not is_dir and path.name in EXCLUDED_FILE_NAMES:
        return True
    if not is_dir and path.name.startswith("._"):
        return True
    if not is_dir and path.suffix in EXCLUDED_SUFFIXES:
        return True
    return False


def iter_release_files(source: Path, output: Path) -> list[Path]:
    files: list[Path] = []
    output = output.resolve()
    for directory, dirnames, filenames in os.walk(source):
        directory_path = Path(directory)
        relative_directory = directory_path.relative_to(source)
        dirnames[:] = sorted(
            dirname for dirname in dirnames if not should_exclude(relative_directory / dirname, is_dir=True)
        )
        for filename in sorted(filenames):
            path = directory_path / filename
            relative = path.relative_to(source)
            if path.resolve() == output:
                continue
            if should_exclude(relative, is_dir=False):
                continue
            files.append(path)
    return files


def create_release_zip(source: Path, output: Path) -> int:
    source = source.resolve()
    output = output.resolve()
    if not source.is_dir():
        raise SystemExit(f"source is not a directory: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    files = iter_release_files(source, output)

    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(source).as_posix())

    print(f"wrote {output}")
    print(f"files {len(files)}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="Release zip path to create.")
    parser.add_argument("--source", default=ROOT, type=Path, help="Source directory to package. Defaults to the repository root.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    return create_release_zip(args.source, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
