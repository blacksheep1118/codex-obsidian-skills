#!/usr/bin/env python3
"""Check lightweight quality issues in an Obsidian-style Markdown vault."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


TEMPLATE_RE = re.compile(r"(相关知识链接|TODO|FIXME|TBD|待补|待完善)")
SOLVENOTES_STUDY_RE = re.compile(
    r"(待补充|占位|空话|套话|泛泛|交作业式|神谕|需要注意的是|"
    r"P\(UO\)|L\(UO\)|软件工程：风险管理复习与 RMMM|"
    r"这个公式把项目状态转成可量化的控制指标|若等待图成环，则可能发生死锁|"
    r"关键不是背结论|信息如何进入价格|收益、方差、估值或技术指标)"
)
REPORT_NOTE_NAME_RE = re.compile(r"(审查|复查|报告|覆盖审查|一致性严格审查)")
BRIDGE_NOTE_RE = re.compile(r"本页保留旧路径，正文请读 \[\[[^\]]+\]\]。")
WIKI_LINK_RE = re.compile(r"\[\[[^\]]+\]\]")


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class VaultIssue:
    path: Path
    kind: str
    message: str


def markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if ".git" not in path.parts)


def relative_issue(root: Path, path: Path, kind: str, message: str) -> VaultIssue:
    return VaultIssue(path.relative_to(root), kind, message)


def is_conflict_marker(line: str, has_conflict_edges: bool) -> bool:
    stripped = line.strip()
    return stripped.startswith("<<<<<<<") or stripped.startswith(">>>>>>>") or (has_conflict_edges and stripped == "=======")


def is_bridge_note(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) > 260:
        return False
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    return bool(lines and lines[0].startswith("# ") and "旧入口" in lines[0] and BRIDGE_NOTE_RE.search(stripped))


def load_pattern_file(path: Path) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("regex:"):
            pattern_text = line.removeprefix("regex:").strip()
        elif line.startswith("re:"):
            pattern_text = line.removeprefix("re:").strip()
        elif line.startswith("text:"):
            pattern_text = re.escape(line.removeprefix("text:").strip())
        else:
            pattern_text = re.escape(line)
        try:
            patterns.append(re.compile(pattern_text))
        except re.error as exc:
            raise ValueError(f"{path}:{line_number}: invalid regex: {exc}") from exc
    return patterns


def profile_patterns(profile: str, pattern_files: list[Path] | None = None) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    if profile == "solvenotes":
        patterns.append(SOLVENOTES_STUDY_RE)
    elif profile != "generic":
        raise ValueError(f"unknown quality profile: {profile}")

    for pattern_file in pattern_files or []:
        patterns.extend(load_pattern_file(pattern_file))
    return patterns


def find_vault_issues(
    root: Path,
    allow_duplicate_stems: bool = False,
    strict_study: bool = False,
    forbid_report_notes: bool = False,
    profile: str = "generic",
    pattern_files: list[Path] | None = None,
) -> list[VaultIssue]:
    files = markdown_files(root)
    issues: list[VaultIssue] = []
    stems: dict[str, list[Path]] = {}
    residue_patterns = profile_patterns(profile, pattern_files)

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        stripped = text.strip()
        if not is_bridge_note(text):
            stems.setdefault(path.stem, []).append(path)
        has_conflict_edges = "<<<<<<<" in text and ">>>>>>>" in text
        lines = text.splitlines()

        if forbid_report_notes and REPORT_NOTE_NAME_RE.search(path.stem):
            issues.append(relative_issue(root, path, "report_note", "audit/report-style note is present in the vault"))

        if not stripped:
            issues.append(relative_issue(root, path, "empty_file", "Markdown file has no content"))
            continue

        for line_number, line in enumerate(lines, start=1):
            if is_conflict_marker(line, has_conflict_edges):
                issues.append(relative_issue(root, path, "conflict_marker", f"line {line_number} contains merge conflict marker"))
            if TEMPLATE_RE.search(line):
                issues.append(relative_issue(root, path, "template_residue", f"line {line_number} contains leftover template text"))
            for residue_pattern in residue_patterns:
                if residue_pattern.search(line):
                    issues.append(relative_issue(root, path, "strict_study_residue", f"line {line_number} contains profile or custom study-note residue"))
                    break
            if strict_study and line.strip() == "## 知识链接":
                issues.append(relative_issue(root, path, "link_dump_section", f"line {line_number} contains a tail-style knowledge-link dump heading"))
            if strict_study and line.startswith("关联阅读：") and len(WIKI_LINK_RE.findall(line)) > 4:
                issues.append(relative_issue(root, path, "dense_related_links", f"line {line_number} contains too many related links for one concept"))
            if strict_study and line.startswith("关联阅读：") and WIKI_LINK_RE.search(line):
                previous = ""
                for prior in reversed(lines[: line_number - 1]):
                    if prior.strip():
                        previous = prior.strip()
                        break
                if previous.startswith("#") or previous.startswith("相关笔记") or previous.startswith("关联阅读"):
                    issues.append(relative_issue(root, path, "poor_link_context", f"line {line_number} is not attached to a concrete concept paragraph"))

        fence_count = sum(1 for line in lines if line.strip().startswith("```"))
        if fence_count % 2:
            issues.append(relative_issue(root, path, "unbalanced_fence", "odd number of fenced code block delimiters"))

        if text.count("$$") % 2:
            issues.append(relative_issue(root, path, "unbalanced_math", "odd number of block math delimiters"))

    if not allow_duplicate_stems:
        for stem, paths in sorted(stems.items()):
            if len(paths) <= 1:
                continue
            joined = ", ".join(str(path.relative_to(root)) for path in paths)
            issues.append(VaultIssue(Path(stem), "duplicate_stem", f"duplicate note stem across files: {joined}"))

    return issues


def main() -> int:
    configure_output_encoding()
    parser = argparse.ArgumentParser(description="Check Markdown vault quality issues.")
    parser.add_argument("root", type=Path, help="Vault or notes directory")
    parser.add_argument("--allow-duplicate-stems", action="store_true")
    parser.add_argument("--strict-study", action="store_true", help="flag generic strict study-note link-placement issues")
    parser.add_argument("--profile", choices=["generic", "solvenotes"], default="generic", help="quality profile for project-specific residue patterns")
    parser.add_argument("--pattern-file", action="append", default=[], type=Path, help="custom residue pattern file; plain lines are literal text, regex:/re: lines are regular expressions")
    parser.add_argument("--forbid-report-notes", action="store_true", help="flag audit/report-style Markdown notes in the checked tree")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists():
        parser.error(f"directory does not exist: {root}")
    if not root.is_dir():
        parser.error(f"root must be a directory: {root}")

    try:
        issues = find_vault_issues(
            root,
            allow_duplicate_stems=args.allow_duplicate_stems,
            strict_study=args.strict_study,
            forbid_report_notes=args.forbid_report_notes,
            profile=args.profile,
            pattern_files=args.pattern_file,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"vault_quality_issues {len(issues)}")
    for issue in issues:
        print(f"{issue.kind.upper()}: {issue.path}: {issue.message}")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
