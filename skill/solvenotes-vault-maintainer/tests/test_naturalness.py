from pathlib import Path

import check_naturalness


def test_placeholder_is_high_confidence(monkeypatch, tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("# 标题\n\n<!-- no -->\n在此填写实验边界。\n", encoding="utf-8")
    monkeypatch.setattr(check_naturalness, "markdown_files", lambda: [note])
    monkeypatch.setattr(check_naturalness, "rel", lambda path: path.name)
    monkeypatch.setattr(check_naturalness, "read_text", lambda path: path.read_text(encoding="utf-8"))

    payload = check_naturalness.scan()

    assert payload["naturalness_high_confidence"] == 1
    assert payload["high_confidence"][0]["kind"] == "placeholder"


def test_formal_word_and_topic_specific_prose_are_not_naturalness_errors(
    monkeypatch, tmp_path: Path
) -> None:
    note = tmp_path / "note.md"
    note.write_text(
        "# 定理\n\n在给定前提下，该不变量保证算法返回最短路。\n"
        "强化学习在具身策略学习中是支撑技术，不是岗位分类。\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_naturalness, "markdown_files", lambda: [note])
    monkeypatch.setattr(check_naturalness, "rel", lambda path: path.name)
    monkeypatch.setattr(check_naturalness, "read_text", lambda path: path.read_text(encoding="utf-8"))

    payload = check_naturalness.scan()

    assert payload["naturalness_high_confidence"] == 0


def test_learning_outcome_variants_are_review_candidates(monkeypatch, tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(
        "# 标题\n\n学完本篇，应能解释边界。\n\n"
        "## 学习目标、前置知识与适用边界\n\n"
        "学完本页后，应能复现代码。\n\n"
        "## 项目验收与面试表达\n\n"
        "## 学完检查\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_naturalness, "markdown_files", lambda: [note])
    monkeypatch.setattr(check_naturalness, "rel", lambda path: path.name)
    monkeypatch.setattr(check_naturalness, "read_text", lambda path: path.read_text(encoding="utf-8"))

    payload = check_naturalness.scan()

    kinds = {item["kind"] for item in payload["review_candidates"]}
    assert "learning_outcome" in kinds
    assert "generic_section" in kinds


def test_repeated_h2_skeleton_is_a_candidate_not_a_failure(monkeypatch, tmp_path: Path) -> None:
    notes = []
    for index in range(4):
        note = tmp_path / f"note-{index}.md"
        note.write_text(
            "# 标题\n\n独立的开头内容。\n\n"
            "## 问题背景\n\n具体问题。\n\n"
            "## 核心机制\n\n具体机制。\n\n"
            "## 失败边界\n\n具体边界。\n\n",
            encoding="utf-8",
        )
        notes.append(note)
    monkeypatch.setattr(check_naturalness, "markdown_files", lambda: notes)
    monkeypatch.setattr(check_naturalness, "rel", lambda path: path.name)
    monkeypatch.setattr(check_naturalness, "read_text", lambda path: path.read_text(encoding="utf-8"))

    payload = check_naturalness.scan()

    assert payload["naturalness_high_confidence"] == 0
    assert payload["files_checked"] == 4
    assert any(item["kind"] == "repeated_h2_skeleton" for item in payload["review_candidates"])
    assert payload["review_groups"]["repeated_h2_skeleton"]["count"] == 1
