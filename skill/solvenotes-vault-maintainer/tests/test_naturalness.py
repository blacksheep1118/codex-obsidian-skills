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
