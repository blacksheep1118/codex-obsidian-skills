import sys
from pathlib import Path

import notes_utils
import pytest
import sync_note_frontmatter as snf


def test_parse_scalar_value_unquotes_existing_date() -> None:
    header = ['course: "测试"', 'last_checked: "2026-07-29"']

    assert snf.parse_scalar_value(header, "last_checked") == "2026-07-29"


def test_checked_date_preserves_existing_date_by_default() -> None:
    header = ['last_checked: "2026-07-29"']

    assert snf.checked_date_for(header, None) == "2026-07-29"
    assert snf.checked_date_for(header, "2026-08-01") == "2026-08-01"


def test_checked_date_requires_explicit_date_when_missing() -> None:
    with pytest.raises(ValueError, match="pass --date"):
        snf.checked_date_for(['course: "测试"'], None)


def test_tags_replace_stale_managed_course_and_type() -> None:
    path = snf.ROOT / Path("算法岗学习笔记/98_网络资源与原始论文索引.md")

    tags = snf.tags_for(
        path,
        "算法岗学习笔记",
        "source_index",
        ["course/旧课程", "type/course_note", "topic/sources"],
    )

    assert tags == [
        "topic/sources",
        "course/算法岗学习笔记",
        "type/source_index",
    ]


def test_algorithm_source_index_has_source_index_type() -> None:
    path = snf.ROOT / Path("算法岗学习笔记/98_网络资源与原始论文索引.md")

    assert snf.infer_note_type(path) == "source_index"


def test_only_root_agent_uses_repository_rule_course() -> None:
    assert snf.course_for(snf.ROOT / "AGENT.md") == "仓库规则"
    assert snf.course_for(snf.ROOT / "Agent.md") == "仓库规则"
    assert snf.course_for(snf.ROOT / "课程" / "AGENT.md") == "课程"


def test_sync_does_not_write_through_external_markdown_symlink(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    course = root / "课程"
    course.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    original = "# External target\n"
    outside.write_text(original, encoding="utf-8")
    (course / "linked.md").symlink_to(outside)
    monkeypatch.setattr(notes_utils, "ROOT", root)
    monkeypatch.setattr(snf, "ROOT", root)
    monkeypatch.setattr(snf, "source_mapping", lambda: {})
    monkeypatch.setattr(sys, "argv", ["sync_note_frontmatter.py", "--date", "2026-08-09"])

    assert snf.main() == 0
    assert outside.read_text(encoding="utf-8") == original


def test_normalized_text_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    path = root / Path("算法岗学习笔记/98_网络资源与原始论文索引.md")
    path.parent.mkdir(parents=True)
    path.write_text(
        '---\nlast_checked: "2026-08-19"\n---\n\n# 网络资源与原始论文索引\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(notes_utils, "ROOT", root)
    monkeypatch.setattr(snf, "ROOT", root)
    source_map = {"算法岗学习笔记/98_网络资源与原始论文索引.md": []}
    first = snf.normalized_text(path, None, source_map)
    original_read_text = snf.read_text

    def read_once_normalized(candidate: Path) -> str:
        if candidate == path:
            return first
        return original_read_text(candidate)

    monkeypatch.setattr(snf, "read_text", read_once_normalized)

    assert snf.normalized_text(path, None, source_map) == first
