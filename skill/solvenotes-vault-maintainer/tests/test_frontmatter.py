import re
import sys
from pathlib import Path

import check_frontmatter
import notes_utils
import pytest
from check_frontmatter import (
    REQUIRED_KEYS,
    parse_keys,
    unquote,
    validate_frontmatter_structure,
    validate_list_field,
    validate_source_files,
)
from notes_utils import COVERAGE_VALUES, NOTE_TYPES, split_frontmatter


def collect_frontmatter_issues(text: str) -> list[str]:
    header, _ = split_frontmatter(text)
    if not header:
        return ["missing frontmatter"]

    issues: list[str] = []
    keys = parse_keys(header)
    validate_frontmatter_structure(header, "sample.md", issues)
    for key in REQUIRED_KEYS:
        if key not in keys:
            issues.append(f"missing {key}")
    if "note_type" in keys and unquote(keys["note_type"]) not in NOTE_TYPES:
        issues.append("invalid note_type")
    if "coverage" in keys and unquote(keys["coverage"]) not in COVERAGE_VALUES:
        issues.append("invalid coverage")
    if "last_checked" in keys and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", unquote(keys["last_checked"])):
        issues.append("invalid last_checked")
    validate_source_files(header, keys, "sample.md", issues)
    validate_list_field(header, keys, "aliases", "sample.md", issues)
    validate_list_field(header, keys, "tags", "sample.md", issues)
    return issues


def test_valid_frontmatter_with_empty_source_files() -> None:
    text = """---
course: "测试课程"
note_type: "course_note"
source_files: []
coverage: "checked"
last_checked: "2026-06-30"
---

# 标题
"""

    assert collect_frontmatter_issues(text) == []


def test_frontmatter_checker_rejects_invalid_utf8_with_path_and_offset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    damaged = tmp_path / "damaged.md"
    damaged.write_bytes(b"valid\n\xffdamaged\n")
    monkeypatch.setattr(check_frontmatter, "markdown_files", lambda: [damaged])
    monkeypatch.setattr(check_frontmatter, "rel", lambda path: path.name)
    monkeypatch.setattr(sys, "argv", ["check_frontmatter.py"])

    with pytest.raises(notes_utils.UnsafePathError) as captured:
        check_frontmatter.main()

    message = str(captured.value)
    assert str(damaged) in message
    assert "byte offset 6" in message


def test_valid_frontmatter_with_yaml_source_files_list() -> None:
    text = """---
course: "测试课程"
note_type: "course_note"
aliases:
  - "测试别名"
source_files:
  - "测试课程/source.pdf"
coverage: "source_mapped"
last_checked: "2026-06-30"
tags:
  - "course/测试课程"
  - "type/course_note"
---

# 标题
"""

    assert collect_frontmatter_issues(text) == []


def test_orphan_yaml_list_item_is_invalid() -> None:
    text = """---
  - "course/仓库规则"
course: "测试课程"
note_type: "course_note"
source_files: []
coverage: "checked"
last_checked: "2026-06-30"
---

# 标题
"""

    issues = collect_frontmatter_issues(text)

    assert any("YAML list item is not attached" in issue for issue in issues)


def test_non_list_key_cannot_own_yaml_list_item() -> None:
    text = """---
course:
  - "测试课程"
note_type: "course_note"
source_files: []
coverage: "checked"
last_checked: "2026-06-30"
---

# 标题
"""

    issues = collect_frontmatter_issues(text)

    assert any("YAML list item is not attached" in issue for issue in issues)


def test_duplicate_managed_keys_are_invalid() -> None:
    text = """---
course: "测试课程"
course: "重复课程"
note_type: "course_note"
note_type: "navigation"
source_files: []
coverage: "checked"
coverage: "generated"
last_checked: "2026-06-30"
last_checked: "2026-07-01"
---

# 标题
"""

    issues = collect_frontmatter_issues(text)

    assert any("duplicate managed frontmatter key course" in issue for issue in issues)
    assert any("duplicate managed frontmatter key note_type" in issue for issue in issues)
    assert any("duplicate managed frontmatter key coverage" in issue for issue in issues)
    assert any("duplicate managed frontmatter key last_checked" in issue for issue in issues)


def test_invalid_frontmatter_reports_enums_date_and_source_files() -> None:
    text = """---
course: "测试课程"
note_type: "bad_type"
source_files: "source.pdf"
coverage: "unknown"
last_checked: "2026/06/30"
---

# 标题
"""

    assert collect_frontmatter_issues(text) == [
        "invalid note_type",
        "invalid coverage",
        "invalid last_checked",
        "sample.md: source_files must be [] or a YAML list",
    ]


def test_missing_frontmatter_is_invalid() -> None:
    assert collect_frontmatter_issues("# 标题\n") == ["missing frontmatter"]


def test_parse_keys_ignores_yaml_list_items() -> None:
    keys = parse_keys(["course: 测试课程", "tags:", "  - type/course_note"])

    assert keys == {"course": "测试课程", "tags": ""}
