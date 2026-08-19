#!/usr/bin/env python3
"""Report legacy PPT files whose source_manifest rows have no readable text."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from notes_utils import ROOT, manifest_rows, rel

GAP_MARKER = "未抽到可读文本记录"

TOOL_CANDIDATES = [
    ("soffice", "LibreOffice/OpenOffice conversion entry point"),
    ("libreoffice", "LibreOffice conversion entry point"),
    ("textutil", "macOS text conversion probe"),
    ("catppt", "catdoc legacy PPT text extractor"),
    ("antiword", "legacy Office text extractor helper"),
    ("strings", "binary text probe for diagnostics"),
]


def strip_code_span(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        return value[1:-1]
    return value


def source_root_from_env(arg_value: str | None) -> Path:
    if arg_value:
        return Path(arg_value).expanduser().resolve()
    env_value = os.environ.get("SOLVENOTES_SOURCE_ROOT")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return ROOT.parent


def available_tools() -> list[dict[str, str]]:
    tools: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for name, role in TOOL_CANDIDATES:
        path = shutil.which(name)
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        tools.append({"name": name, "path": path, "role": role})
    return tools


def source_file_status(source_root: Path, source_file: str) -> tuple[str, bool | None, str]:
    source_path = source_root / source_file
    course = source_file.split("/", 1)[0]
    if not source_root.exists():
        return "source_root_missing", None, str(source_path)
    if not (source_root / course).exists():
        return "course_source_dir_missing", None, str(source_path)
    if source_path.exists():
        return "present", True, str(source_path)
    return "missing", False, str(source_path)


def suggested_action(source_status: str, tools: list[dict[str, str]]) -> str:
    tool_names = {tool["name"] for tool in tools}
    if source_status in {"source_root_missing", "course_source_dir_missing"}:
        return "源文件目录不可见时保留文件级映射；在有源文件的本机环境重新运行本脚本。"
    if source_status == "missing":
        return "先核对本机源资料路径；不移动、不重命名源 PPT。"
    if {"soffice", "libreoffice"} & tool_names:
        return "优先尝试 LibreOffice 将旧 PPT 转为 PPTX 或 PDF，再抽取文本并更新覆盖审查。"
    if "catppt" in tool_names:
        return "可尝试 catppt 抽取旧 PPT 文本；抽取成功后再补充页级覆盖，不覆盖图片文字结论。"
    if "textutil" in tool_names or "strings" in tool_names:
        return "仅有轻量文本探测工具；可先验证是否存在可读字符串，视觉题仍需单独 OCR。"
    return "未检测到合适转换工具；保留限制说明，后续在具备转换或 OCR 工具后复查。"


def collect_gaps(source_root: Path) -> dict:
    tools = available_tools()
    gaps: list[dict[str, object]] = []

    for manifest, cells in manifest_rows():
        if len(cells) < 9:
            continue
        source, kind, records, extraction, note, status, example_status, limitation, checked_date = cells[:9]
        if GAP_MARKER not in limitation:
            continue

        source_file = strip_code_span(source)
        source_status, exists, source_path = source_file_status(source_root, source_file)
        gaps.append(
            {
                "course": manifest.parent.name,
                "source_file": source_file,
                "kind": strip_code_span(kind),
                "records": strip_code_span(records),
                "extraction": strip_code_span(extraction),
                "corresponding_note": note,
                "coverage_status": status,
                "example_status": example_status,
                "limitation": limitation,
                "last_checked": checked_date,
                "manifest": rel(manifest),
                "source_status": source_status,
                "source_exists": exists,
                "source_path": source_path,
                "recommended_action": suggested_action(source_status, tools),
            }
        )

    gaps.sort(key=lambda row: (str(row["course"]), str(row["source_file"])))
    present_count = sum(1 for row in gaps if row["source_exists"] is True)
    skipped_count = sum(1 for row in gaps if row["source_exists"] is None)
    return {
        "source_root": str(source_root),
        "available_conversion_tools": tools,
        "high_limit_source_files": len(gaps),
        "source_files_present": present_count,
        "source_file_checks_skipped": skipped_count,
        "gaps": gaps,
    }


def print_human(payload: dict) -> None:
    print(f"source_root {payload['source_root']}")
    print(f"available_conversion_tools {len(payload['available_conversion_tools'])}")
    for tool in payload["available_conversion_tools"]:
        print(f"TOOL {tool['name']} {tool['path']} | {tool['role']}")
    print(f"high_limit_source_files {payload['high_limit_source_files']}")
    print(f"source_files_present {payload['source_files_present']}")
    print(f"source_file_checks_skipped {payload['source_file_checks_skipped']}")
    for row in payload["gaps"]:
        print(
            "GAP "
            f"{row['course']} | {row['source_file']} | {row['corresponding_note']} | "
            f"{row['source_status']} | {row['limitation']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="print machine-readable report")
    parser.add_argument(
        "--source-root",
        help="source material root; defaults to SOLVENOTES_SOURCE_ROOT or the notes repo parent",
    )
    args = parser.parse_args()

    payload = collect_gaps(source_root_from_env(args.source_root))
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_human(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
