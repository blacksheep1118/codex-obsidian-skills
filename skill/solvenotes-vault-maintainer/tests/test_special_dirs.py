from __future__ import annotations

from pathlib import Path

from check_special_dirs import required_entry_issues, required_note_contract_issues


def test_algorithm_job_notes_require_learning_map(tmp_path: Path) -> None:
    directory = "算法岗学习笔记"
    base = tmp_path / directory
    base.mkdir()

    assert required_entry_issues(tmp_path, directory) == [
        "算法岗学习笔记/00_算法岗学习地图.md: missing required special-directory entry"
    ]

    (base / "00_算法岗学习地图.md").write_text("# 学习地图\n", encoding="utf-8")

    assert required_entry_issues(tmp_path, directory) == []


def test_symlinked_learning_map_does_not_satisfy_required_entry(tmp_path: Path) -> None:
    directory = "算法岗学习笔记"
    base = tmp_path / directory
    base.mkdir()
    outside = tmp_path / "outside-map.md"
    outside.write_text("# Outside map\n", encoding="utf-8")
    (base / "00_算法岗学习地图.md").symlink_to(outside)

    assert required_entry_issues(tmp_path, directory) == [
        "算法岗学习笔记/00_算法岗学习地图.md: missing required special-directory entry"
    ]


def test_machine_learning_exam_review_requires_explicit_frontmatter_contract(tmp_path: Path) -> None:
    relative_path = "机器学习26/机器学习26考试复习笔记_按考点范围.md"
    path = tmp_path / relative_path
    path.parent.mkdir()
    path.write_text(
        """---
course: "机器学习26"
note_type: "course_note"
source_files: []
coverage: "checked"
last_checked: "2026-08-02"
tags:
  - "course/机器学习26"
  - "type/course_note"
---
""",
        encoding="utf-8",
    )

    assert required_note_contract_issues(tmp_path, relative_path) == [
        f"{relative_path}: note_type must be 'exam_review', got 'course_note'",
        f"{relative_path}: type tags must be ['type/exam_review'], got ['type/course_note']",
    ]

    text = path.read_text(encoding="utf-8").replace('note_type: "course_note"', 'note_type: "exam_review"')
    text = text.replace('  - "type/course_note"', '  - "type/exam_review"')
    path.write_text(text, encoding="utf-8")

    assert required_note_contract_issues(tmp_path, relative_path) == []


def test_symlinked_exam_review_is_not_read_as_required_contract(tmp_path: Path) -> None:
    relative_path = "机器学习26/机器学习26考试复习笔记_按考点范围.md"
    path = tmp_path / relative_path
    path.parent.mkdir()
    outside = tmp_path / "outside-review.md"
    outside.write_text('---\nnote_type: "exam_review"\n---\n', encoding="utf-8")
    path.symlink_to(outside)

    assert required_note_contract_issues(tmp_path, relative_path) == [
        f"{relative_path}: missing required contract note"
    ]
