import sys
from pathlib import Path

import notes_utils
import wrap_source_coverage_blocks as wscb
from wrap_source_coverage_blocks import remove_visible_sections


def test_remove_visible_section_preserves_surrounding_course_content() -> None:
    text = "# Note\n\nIntro.\n\n## PPT/PDF 页级补充索引\n\nraw evidence\n\n## Next\n\nKeep me.\n"

    new_text, changed = remove_visible_sections(text)

    assert changed is True
    assert new_text == "# Note\n\nIntro.\n\n## Next\n\nKeep me.\n"


def test_default_cli_reports_without_deleting(tmp_path: Path, monkeypatch, capsys) -> None:
    note = tmp_path / "note.md"
    original = "# Note\n\n## PPT/PDF 页级补充索引\n\nraw evidence\n"
    note.write_text(original, encoding="utf-8")
    monkeypatch.setattr(wscb, "markdown_files", lambda: [note])
    monkeypatch.setattr(wscb, "regular_note", lambda _path: True)
    monkeypatch.setattr(wscb, "rel", lambda path: path.name)
    monkeypatch.setattr(sys, "argv", ["wrap_source_coverage_blocks.py"])

    assert wscb.main() == 0
    assert note.read_text(encoding="utf-8") == original
    assert "source_coverage_note_blocks_found 1" in capsys.readouterr().out


def test_apply_cli_is_required_for_deletion(tmp_path: Path, monkeypatch) -> None:
    note = tmp_path / "note.md"
    note.write_text("# Note\n\n## PPT/PDF 页级补充索引\n\nraw evidence\n", encoding="utf-8")
    monkeypatch.setattr(wscb, "markdown_files", lambda: [note])
    monkeypatch.setattr(wscb, "regular_note", lambda _path: True)
    monkeypatch.setattr(wscb, "rel", lambda path: path.name)
    monkeypatch.setattr(notes_utils, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["wrap_source_coverage_blocks.py", "--apply"])

    assert wscb.main() == 0
    assert note.read_text(encoding="utf-8") == "# Note\n"
