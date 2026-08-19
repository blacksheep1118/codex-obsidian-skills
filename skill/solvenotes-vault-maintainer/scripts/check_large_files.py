#!/usr/bin/env python3
"""Check tracked files and Git history for oversized blobs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from notes_utils import ROOT

KIB = 1024
MIB = 1024 * 1024


def run_git(args: list[str], *, input_text: str | None = None, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        input=input_text,
        capture_output=True,
        text=not binary,
    )
    if result.returncode:
        stderr = result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else result.stderr
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return result.stdout


def format_size(size: int) -> str:
    if size >= MIB:
        return f"{size / MIB:.2f} MiB"
    return f"{size / KIB:.1f} KiB"


def tracked_files() -> list[str]:
    output = run_git(["ls-files", "-z"], binary=True)
    assert isinstance(output, bytes)
    return [item.decode("utf-8", errors="surrogateescape") for item in output.split(b"\0") if item]


def collect_current_files(max_bytes: int, warn_bytes: int) -> dict[str, object]:
    warnings: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    missing: list[str] = []
    largest: dict[str, object] | None = None
    files = tracked_files()

    for file_path in files:
        path = ROOT / file_path
        try:
            size = path.lstat().st_size
        except FileNotFoundError:
            missing.append(file_path)
            continue
        row = {"path": file_path, "size_bytes": size, "size": format_size(size)}
        if largest is None or size > int(largest["size_bytes"]):
            largest = row
        if size > max_bytes:
            failures.append(row)
        elif size > warn_bytes:
            warnings.append(row)

    warnings.sort(key=lambda row: (-int(row["size_bytes"]), str(row["path"])))
    failures.sort(key=lambda row: (-int(row["size_bytes"]), str(row["path"])))
    return {
        "tracked_file_count": len(files),
        "largest_current_file": largest,
        "current_warnings": warnings,
        "current_failures": failures,
        "missing_tracked_files": missing,
    }


def history_object_paths() -> dict[str, str]:
    output = run_git(["rev-list", "--objects", "--all"])
    assert isinstance(output, str)
    paths: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split(" ", 1)
        oid = parts[0]
        path = parts[1] if len(parts) > 1 else ""
        paths.setdefault(oid, path)
    return paths


def collect_history_blobs(max_bytes: int, warn_bytes: int) -> dict[str, object]:
    object_paths = history_object_paths()
    warnings: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    largest: dict[str, object] | None = None
    blob_count = 0
    if not object_paths:
        return {
            "history_blob_count": 0,
            "largest_history_blob": None,
            "history_warnings": [],
            "history_failures": [],
        }

    output = run_git(
        ["cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        input_text="\n".join(object_paths) + "\n",
    )
    assert isinstance(output, str)
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        oid, object_type, size_text = parts
        if object_type != "blob":
            continue
        blob_count += 1
        size = int(size_text)
        row = {
            "oid": oid,
            "path": object_paths.get(oid, ""),
            "size_bytes": size,
            "size": format_size(size),
        }
        if largest is None or size > int(largest["size_bytes"]):
            largest = row
        if size > max_bytes:
            failures.append(row)
        elif size > warn_bytes:
            warnings.append(row)

    warnings.sort(key=lambda row: (-int(row["size_bytes"]), str(row["path"]), str(row["oid"])))
    failures.sort(key=lambda row: (-int(row["size_bytes"]), str(row["path"]), str(row["oid"])))
    return {
        "history_blob_count": blob_count,
        "largest_history_blob": largest,
        "history_warnings": warnings,
        "history_failures": failures,
    }


def build_payload(args: argparse.Namespace) -> dict[str, object]:
    max_current_bytes = int(args.max_current_mib * MIB)
    warn_current_bytes = int(args.warn_current_kib * KIB)
    max_history_bytes = int(args.max_history_mib * MIB)
    warn_history_bytes = int(args.warn_history_mib * MIB)
    current = collect_current_files(max_current_bytes, warn_current_bytes)
    history = collect_history_blobs(max_history_bytes, warn_history_bytes)
    failures = len(current["current_failures"]) + len(history["history_failures"])
    return {
        "thresholds": {
            "max_current_bytes": max_current_bytes,
            "warn_current_bytes": warn_current_bytes,
            "max_history_bytes": max_history_bytes,
            "warn_history_bytes": warn_history_bytes,
        },
        **current,
        **history,
        "large_file_issues": failures,
    }


def print_human(payload: dict[str, object]) -> None:
    print(f"tracked_files {payload['tracked_file_count']}")
    print(f"history_blobs {payload['history_blob_count']}")
    largest_current = payload.get("largest_current_file")
    if largest_current:
        print(f"largest_current {largest_current['size']} {largest_current['path']}")
    largest_history = payload.get("largest_history_blob")
    if largest_history:
        print(f"largest_history {largest_history['size']} {largest_history['path']} {largest_history['oid']}")
    print(f"current_warnings {len(payload['current_warnings'])}")
    print(f"current_failures {len(payload['current_failures'])}")
    print(f"history_warnings {len(payload['history_warnings'])}")
    print(f"history_failures {len(payload['history_failures'])}")
    for row in payload["current_warnings"]:
        print(f"WARN current {row['size']} {row['path']}")
    for row in payload["history_warnings"]:
        print(f"WARN history {row['size']} {row['path']} {row['oid']}")
    for row in payload["current_failures"]:
        print(f"FAIL current {row['size']} {row['path']}")
    for row in payload["history_failures"]:
        print(f"FAIL history {row['size']} {row['path']} {row['oid']}")
    for item in payload["missing_tracked_files"]:
        print(f"WARN missing_tracked_file {item}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--max-current-mib", type=float, default=1, help="fail tracked files above this size")
    parser.add_argument("--warn-current-kib", type=float, default=512, help="warn tracked files above this size")
    parser.add_argument("--max-history-mib", type=float, default=50, help="fail history blobs above this size")
    parser.add_argument("--warn-history-mib", type=float, default=10, help="warn history blobs above this size")
    args = parser.parse_args()

    payload = build_payload(args)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_human(payload)
    return 1 if payload["large_file_issues"] else 0


if __name__ == "__main__":
    sys.exit(main())
