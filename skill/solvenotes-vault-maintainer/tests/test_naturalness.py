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


def test_repeated_language_like_list_items_are_review_candidates(monkeypatch, tmp_path: Path) -> None:
    note = tmp_path / "repeated.md"
    note.write_text(
        "# Demo\n\n"
        "- 说明问题、条件和失败边界，避免只背名词，还要写出技术前提。\n"
        "- 说明问题、条件和失败边界，避免只背名词，还要写出技术前提。\n"
        "- 说明问题、条件和失败边界，避免只背名词，还要写出技术前提。\n"
        "- 说明问题、条件和失败边界，避免只背名词，还要写出技术前提。\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_naturalness, "markdown_files", lambda: [note])
    monkeypatch.setattr(check_naturalness, "rel", lambda path: path.name)
    monkeypatch.setattr(check_naturalness, "read_text", lambda path: path.read_text(encoding="utf-8"))

    payload = check_naturalness.scan()

    assert any(item["kind"] == "repeated_list_item" for item in payload["review_candidates"])


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
    assert any(item["kind"] == "structure_reuse" for item in payload["review_candidates"])
    assert payload["review_groups"]["structure_reuse"]["count"] == 1


def test_source_manifests_templates_and_repeated_citations_are_not_prose_candidates(
    monkeypatch, tmp_path: Path
) -> None:
    manifest = tmp_path / "source_manifest.md"
    manifest.write_text(
        "---\nnote_type: source_manifest\n---\n\n在此填写来源。\n",
        encoding="utf-8",
    )
    notes = []
    for index in range(4):
        note = tmp_path / f"note-{index}.md"
        note.write_text(
            "---\nnote_type: course_note\n---\n\n# 标题\n\n"
            "- [NIST 标准入口](https://example.invalid/nist)\n",
            encoding="utf-8",
        )
        notes.append(note)
    monkeypatch.setattr(check_naturalness, "markdown_files", lambda: [manifest, *notes])
    monkeypatch.setattr(check_naturalness, "rel", lambda path: path.name)
    monkeypatch.setattr(
        check_naturalness, "read_text", lambda path: path.read_text(encoding="utf-8")
    )

    payload = check_naturalness.scan()

    assert payload["files_checked"] == 4
    assert payload["files_excluded"] == 1
    assert payload["naturalness_high_confidence"] == 0
    assert not any(item["kind"] == "repeated_list_item" for item in payload["review_candidates"])


def test_learning_path_heading_schema_is_reported_as_intentional_structure(
    monkeypatch, tmp_path: Path
) -> None:
    notes = []
    for index in range(4):
        note = tmp_path / "学习路径" / f"route-{index}.md"
        note.parent.mkdir(exist_ok=True)
        note.write_text(
            "# 路线\n\n不同目标。\n\n## 起点\n\n内容。\n\n## 阶段\n\n内容。\n\n## 验收\n\n内容。\n",
            encoding="utf-8",
        )
        notes.append(note)
    monkeypatch.setattr(check_naturalness, "markdown_files", lambda: notes)
    monkeypatch.setattr(
        check_naturalness, "rel", lambda path: path.relative_to(tmp_path).as_posix()
    )
    monkeypatch.setattr(
        check_naturalness, "read_text", lambda path: path.read_text(encoding="utf-8")
    )

    payload = check_naturalness.scan()

    assert payload["naturalness_review_candidates"] == 0
    assert payload["intentional_structure"][0]["kind"] == "intentional_heading_schema"
