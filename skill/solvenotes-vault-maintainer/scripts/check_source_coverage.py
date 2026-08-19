#!/usr/bin/env python3
"""Validate authoritative source manifests and reject learner-side audit artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from notes_utils import (
    ROOT,
    build_note_index,
    formal_source_manifests,
    frontmatter_note_type,
    markdown_files,
    read_text,
    rel,
    split_frontmatter,
    split_table_row,
)

EXPECTED_HEADER = "| 源文件 | 类型 | 页/slide/记录数 | 抽取方式 | 对应笔记 | 覆盖状态 | 例题状态 | 限制说明 | 最后检查日期 |"
WEB_SOURCE_HEADER = "| 来源 | URL | 类型 | 访问状态 | 用途 |"
DEPRECATED_EXAMPLE_STATUS = "已在章节笔记配置源资料例题或生成补充题"
FORBIDDEN_LEARNER_AUDIT_TYPES = {
    "audit_record",
    "coverage_audit",
    "global_coverage_audit",
    "source_manifest_history",
    "vault_audit",
}
NON_LEARNER_TOP_LEVEL = {".github", "agent", "scripts", "tests"}
STALE_AUDIT_TERMS = ("99_内容覆盖审查", "覆盖审查页", "覆盖审查表", "逐页审查表", "审查表", "审查页")
STRONG_SEMANTIC_CLAIMS = ("可抽取文本已覆盖", "语义覆盖完成", "完整覆盖", "已全部覆盖")
ISSUE_CODE_MARKERS = (
    ("FORBIDDEN_AUDIT_ARTIFACT", "forbidden legacy audit artifact"),
    ("FORBIDDEN_AUDIT_NOTE_TYPE", "learner note cannot use note_type"),
    ("STALE_AUDIT_REFERENCE", "stale audit-page reference"),
    ("AGGREGATE_NOT_SEMANTIC_PROOF", "aggregate/range mapping does not prove per-unit semantic coverage"),
    ("SOURCE_IDENTITY_INVALID", "full root-relative identity"),
    ("SOURCE_DUPLICATE", "duplicate source identity"),
    ("SOURCE_TYPE_INVALID", "file type"),
    ("SOURCE_COUNT_INVALID", "count must be a positive integer"),
    ("EXTRACTION_METHOD_MISSING", "empty extraction method"),
    ("MAPPING_LINK_MISSING", "missing corresponding note wikilink"),
    ("MAPPING_LINK_BROKEN", "broken corresponding note"),
    ("APPLICABLE_MANIFEST_MISSING", "non-empty source_files has no applicable formal source_manifest"),
    ("SOURCE_NOT_IN_APPLICABLE_MANIFEST", "source_files entry is absent from applicable formal manifests"),
    ("SOURCE_NOTE_MAPPING_MISSING", "source_files entry is not mapped back to its declaring note"),
    ("COVERAGE_STATE_INVALID", "coverage status must use an explicit evidence state"),
    ("EXAMPLE_STATE_INVALID", "example status"),
    ("LIMITATIONS_MISSING", "empty limitations field"),
    ("LIMITATIONS_INCOMPLETE", "limitations must explicitly state"),
    ("CHECKED_DATE_INVALID", "last checked date"),
    ("MANIFEST_COLUMNS_INVALID", "expected 9 columns"),
    ("MANIFEST_HEADER_INVALID", "source_manifest table header"),
    ("MANIFEST_HEADER_INVALID", "non-standard header"),
    ("MANIFEST_ROWS_MISSING", "must contain at least one source row"),
    ("WEB_SOURCE_COLUMNS_INVALID", "expected 5 web-source columns"),
    ("WEB_SOURCE_URL_INVALID", "web-source URL must use http or https"),
    ("MANIFEST_NOTE_TYPE_INVALID", "note_type source_manifest"),
    ("SUPPLEMENT_DUPLICATE", "duplicate supplement row"),
)


@dataclass(frozen=True)
class ManifestRecord:
    line_no: int
    source: str
    source_is_exact: bool
    kind: str
    count: int | None
    method: str
    note_cell: str
    status: str
    example_status: str
    limitations: str
    checked: str


def issue_code(issue: str) -> str:
    for code, marker in ISSUE_CODE_MARKERS:
        if marker in issue:
            return code
    return "OTHER_CONTRACT_ISSUE"


def _contract_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_support_path(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if relative == Path("AGENT.md"):
        return True
    return bool(relative.parts and relative.parts[0] in NON_LEARNER_TOP_LEVEL)


def _wikilink_targets(cell: str) -> set[str]:
    return {
        raw.split("|", 1)[0].split("#", 1)[0].strip()
        for raw in re.findall(r"\[\[([^\]]+)\]\]", cell)
        if raw.split("|", 1)[0].split("#", 1)[0].strip()
    }


def _resolve_contract_wikilink(
    target: str,
    source: Path,
    index: dict[str, list[Path]],
    root: Path,
) -> Path | None:
    clean = target.strip().lstrip("/")
    if not clean or "://" in clean:
        return None
    candidates: list[str] = []
    if "/" in clean or target.startswith("/"):
        candidates.extend((clean, f"{clean}.md"))
    else:
        sibling = source.parent.relative_to(root).as_posix()
        if sibling != ".":
            candidates.extend((f"{sibling}/{clean}", f"{sibling}/{clean}.md"))
        candidates.extend((clean, f"{clean}.md"))
    for candidate in dict.fromkeys(candidates):
        matches = list(dict.fromkeys(index.get(candidate, [])))
        if len(matches) == 1:
            return matches[0]
        if matches:
            return None
    return None


def _source_identity(cell: str) -> str | None:
    match = re.fullmatch(r"`([^`]+)`", cell)
    return match.group(1) if match else None


def _valid_source_identity(source: str) -> bool:
    path = PurePosixPath(source)
    return not path.is_absolute() and len(path.parts) >= 2 and ".." not in path.parts and "." not in path.parts


def _valid_checked_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        return dt.date.fromisoformat(value) <= dt.date.today()
    except ValueError:
        return False


def _local_source_rows(text: str) -> list[tuple[int, list[str]]]:
    rows: list[tuple[int, list[str]]] = []
    in_table = False
    for line_no, line in enumerate(text.splitlines(), 1):
        if line.startswith("| 源文件 |"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|---"):
            continue
        if not line.startswith("|"):
            break
        rows.append((line_no, split_table_row(line)))
    return rows


def _manifest_records(text: str) -> list[ManifestRecord]:
    records: list[ManifestRecord] = []
    for line_no, cells in _local_source_rows(text):
        if len(cells) != 9:
            continue
        source = _source_identity(cells[0])
        count = int(cells[2]) if cells[2].isdigit() and int(cells[2]) > 0 else None
        records.append(
            ManifestRecord(
                line_no=line_no,
                source=source or cells[0],
                source_is_exact=source is not None,
                kind=cells[1],
                count=count,
                method=cells[3],
                note_cell=cells[4],
                status=cells[5],
                example_status=cells[6],
                limitations=cells[7],
                checked=cells[8],
            )
        )
    return records


def _web_source_rows(text: str) -> list[tuple[int, list[str]]]:
    rows: list[tuple[int, list[str]]] = []
    in_table = False
    for line_no, line in enumerate(text.splitlines(), 1):
        if line == WEB_SOURCE_HEADER:
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|---"):
            continue
        if not line.startswith("|"):
            break
        cells = split_table_row(line)
        if cells:
            rows.append((line_no, cells))
    return rows


def _frontmatter_source_files(text: str) -> list[str]:
    header, _body = split_frontmatter(text)
    for index, line in enumerate(header):
        if not line.startswith("source_files:"):
            continue
        inline = line.split(":", 1)[1].strip()
        if inline == "[]" or not inline:
            values: list[str] = []
            for following in header[index + 1 :]:
                if not following.startswith("  - "):
                    break
                values.append(following[4:].strip().strip('"\''))
            return values
        if inline.startswith("[") and inline.endswith("]"):
            return [item.strip().strip('"\'') for item in inline[1:-1].split(",") if item.strip()]
        return []
    return []


def _source_file_closure_issues(root: Path, note_paths: list[Path], manifests: list[Path]) -> list[str]:
    issues: list[str] = []
    records_by_dir = {
        manifest.parent: {record.source: record for record in _manifest_records(read_text(manifest))}
        for manifest in manifests
    }
    for note in sorted(note_paths):
        if not note.exists() or _is_support_path(note, root) or note.name == "source_manifest.md":
            continue
        sources = _frontmatter_source_files(read_text(note))
        if not sources:
            continue
        relative = _contract_rel(note, root)
        ancestor_dirs: list[Path] = []
        current = note.parent
        while current == root or root in current.parents:
            if current in records_by_dir:
                ancestor_dirs.append(current)
            if current == root:
                break
            current = current.parent
        if not ancestor_dirs:
            issues.append(f"{relative}: non-empty source_files has no applicable formal source_manifest")
            continue
        target = note.relative_to(root).as_posix().removesuffix(".md")
        for source in sources:
            matched = next(
                (records_by_dir[directory][source] for directory in ancestor_dirs if source in records_by_dir[directory]),
                None,
            )
            if matched is None:
                issues.append(
                    f"{relative}: source_files entry is absent from applicable formal manifests: {source}"
                )
                continue
            if target not in _wikilink_targets(matched.note_cell):
                issues.append(
                    f"{relative}: source_files entry is not mapped back to its declaring note: {source}"
                )
    return issues


def _aggregate_boundary_issue(manifest_rel: str, record: ManifestRecord) -> str | None:
    aggregate = (
        "legacy-ppt" in record.method.lower()
        or "aggregate" in record.method.lower()
        or any(marker in record.status + record.limitations for marker in ("聚合", "范围级", "汇总"))
    )
    if aggregate and any(claim in record.status for claim in STRONG_SEMANTIC_CLAIMS):
        return (
            f"{manifest_rel}:{record.line_no}: aggregate/range mapping does not prove per-unit semantic coverage "
            f"for {record.source}"
        )
    return None


def _limitation_contract_issue(manifest_rel: str, record: ManifestRecord) -> str | None:
    method = record.method.lower()
    if "legacy-ppt" in method:
        required_groups = (("聚合", "范围"), ("OCR", "视觉", "图片", "图表", "图示", "版式"))
    elif any(marker in method for marker in ("pdftotext", "pptx", "slide")):
        required_groups = (("OCR", "视觉", "图片", "图表", "图示", "版式", "流程箭头"),)
    else:
        return None
    if all(any(marker in record.limitations for marker in group) for group in required_groups):
        return None
    return (
        f"{manifest_rel}:{record.line_no}: limitations must explicitly state text-unit and OCR/visual boundaries "
        f"for {record.source}"
    )


def coverage_contract_issues(root: Path, note_paths: list[Path]) -> list[str]:
    """Reject legacy audit artifacts and enforce formal manifest note types."""

    issues: list[str] = []
    manifest_list = formal_source_manifests(root)
    formal_manifests = set(manifest_list)
    for path in sorted(note_paths):
        if not path.exists():
            continue
        relative = _contract_rel(path, root)
        note_type = frontmatter_note_type(read_text(path))
        if path.name == "99_内容覆盖审查.md" and not _is_support_path(path, root):
            issues.append(f"{relative}: forbidden legacy audit artifact 99_内容覆盖审查.md")
        if note_type in FORBIDDEN_LEARNER_AUDIT_TYPES and not _is_support_path(path, root):
            issues.append(f"{relative}: learner note cannot use note_type {note_type}")
        if path in formal_manifests and note_type != "source_manifest":
            issues.append(f"{relative}: manifest must declare note_type source_manifest")
    issues.extend(_source_file_closure_issues(root, note_paths, manifest_list))
    return issues


def manifest_issues(
    root: Path,
    manifest: Path,
    index: dict[str, list[Path]],
) -> tuple[list[str], int]:
    """Validate one authoritative nine-column source manifest."""

    issues: list[str] = []
    manifest_rel = _contract_rel(manifest, root)
    text = read_text(manifest)
    lines = text.splitlines()
    headers = [line for line in lines if line.startswith("| 源文件 |")]
    web_rows = _web_source_rows(text)
    if headers and headers[0] != EXPECTED_HEADER:
        issues.append(f"{manifest_rel}: non-standard header: {headers[0]}")
    elif not headers and WEB_SOURCE_HEADER not in lines:
        issues.append(f"{manifest_rel}: missing source_manifest table header")
    if any(term in text for term in STALE_AUDIT_TERMS):
        issues.append(f"{manifest_rel}: stale audit-page reference; source_manifest must be self-contained")

    for line_no, cells in _local_source_rows(text):
        if len(cells) != 9:
            issues.append(f"{manifest_rel}:{line_no}: expected 9 columns, got {len(cells)}")

    records = _manifest_records(text)
    if headers and not records:
        issues.append(f"{manifest_rel}: source_manifest must contain at least one source row")
    if WEB_SOURCE_HEADER in lines:
        if not web_rows:
            issues.append(f"{manifest_rel}: source_manifest must contain at least one source row")
        for line_no, cells in web_rows:
            if len(cells) != 5:
                issues.append(f"{manifest_rel}:{line_no}: expected 5 web-source columns, got {len(cells)}")
                continue
            if not re.fullmatch(r"https?://\S+", cells[1]):
                issues.append(f"{manifest_rel}:{line_no}: web-source URL must use http or https")
            if not cells[0] or not cells[2] or not cells[3] or not cells[4]:
                issues.append(f"{manifest_rel}:{line_no}: web-source metadata fields must be non-empty")
    by_source: dict[str, ManifestRecord] = {}
    for record in records:
        if not record.source_is_exact or not _valid_source_identity(record.source):
            issues.append(f"{manifest_rel}:{record.line_no}: source must use a full root-relative identity")
        elif record.source in by_source:
            issues.append(f"{manifest_rel}:{record.line_no}: duplicate source identity: {record.source}")
        by_source[record.source] = record
        if not re.fullmatch(r"`\.[A-Za-z0-9]+`", record.kind):
            issues.append(f"{manifest_rel}:{record.line_no}: file type must be a backticked extension")
        elif _valid_source_identity(record.source) and record.kind.strip("`").lower() != Path(record.source).suffix.lower():
            issues.append(f"{manifest_rel}:{record.line_no}: file type does not match source suffix")
        if record.count is None:
            issues.append(f"{manifest_rel}:{record.line_no}: page/slide/record count must be a positive integer")
        if not record.method:
            issues.append(f"{manifest_rel}:{record.line_no}: empty extraction method")
        if not _wikilink_targets(record.note_cell):
            issues.append(f"{manifest_rel}:{record.line_no}: missing corresponding note wikilink")
        for target in _wikilink_targets(record.note_cell):
            if not _resolve_contract_wikilink(target, manifest, index, root):
                issues.append(f"{manifest_rel}:{record.line_no}: broken corresponding note [[{target}]]")
        if not record.status.startswith(("已映射：", "仅映射：", "未核验：")):
            issues.append(f"{manifest_rel}:{record.line_no}: coverage status must use an explicit evidence state")
        if "例题" not in record.example_status and "补充题" not in record.example_status:
            issues.append(f"{manifest_rel}:{record.line_no}: example status should mention 例题 or 补充题")
        if record.example_status == DEPRECATED_EXAMPLE_STATUS:
            issues.append(f"{manifest_rel}:{record.line_no}: example status is an unverified blanket claim")
        if not record.limitations:
            issues.append(f"{manifest_rel}:{record.line_no}: empty limitations field")
        if not _valid_checked_date(record.checked):
            issues.append(f"{manifest_rel}:{record.line_no}: last checked date must be a real, non-future YYYY-MM-DD date")
        if issue := _aggregate_boundary_issue(manifest_rel, record):
            issues.append(issue)
        if record.limitations and (issue := _limitation_contract_issue(manifest_rel, record)):
            issues.append(issue)
    return issues, len(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    index = build_note_index()
    manifests = formal_source_manifests()
    note_paths = markdown_files()
    issues = coverage_contract_issues(ROOT, note_paths)
    source_rows = 0
    web_source_rows = 0
    supplement_seen: dict[tuple[str, str, str], str] = {}

    for manifest in manifests:
        current_issues, current_rows = manifest_issues(ROOT, manifest, index)
        issues.extend(current_issues)
        source_rows += current_rows
        web_source_rows += len(_web_source_rows(read_text(manifest)))
        for note in sorted(path for path in note_paths if path.parent == manifest.parent):
            for line_no, line in enumerate(read_text(note).splitlines(), 1):
                if not line.startswith("- 来源："):
                    continue
                source_match = re.search(r"来源：`([^`]+)`", line)
                page_match = re.search(r"页/slide：([^；]+)", line)
                topic_match = re.search(r"主题：([^；]+)", line)
                if not source_match or not page_match:
                    continue
                key = (
                    rel(note),
                    source_match.group(1).strip(),
                    f"{page_match.group(1).strip()}::{topic_match.group(1).strip() if topic_match else ''}",
                )
                location = f"{rel(note)}:{line_no}"
                if key in supplement_seen:
                    issues.append(f"{location}: duplicate supplement row also at {supplement_seen[key]}")
                else:
                    supplement_seen[key] = location

    payload = {
        "course_manifests": len(manifests),
        "manifest_source_rows": source_rows,
        "web_manifest_rows": web_source_rows,
        "coverage_issues": len(issues),
        "issue_counts": dict(sorted(Counter(issue_code(issue) for issue in issues).items())),
        "coded_issues": [{"code": issue_code(issue), "message": issue} for issue in issues[:100]],
        "issues": issues[:100],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"course_manifests {len(manifests)}")
        print(f"manifest_source_rows {source_rows}")
        print(f"web_manifest_rows {web_source_rows}")
        print(f"coverage_issues {len(issues)}")
        for issue in issues[:100]:
            print(f"ISSUE {issue_code(issue)} {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
