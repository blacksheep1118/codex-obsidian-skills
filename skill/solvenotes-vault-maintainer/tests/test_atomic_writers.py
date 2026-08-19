from __future__ import annotations

import os
import sys
from pathlib import Path

import normalize_source_manifests as nsm
import notes_utils
import pytest
import sync_note_frontmatter as snf
import wrap_source_coverage_blocks as wscb


def test_sync_entry_breaks_hardlink_without_modifying_external_name(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    course = root / "course"
    course.mkdir(parents=True)
    external = tmp_path / "sync-external.md"
    original = "# Note\n"
    external.write_text(original, encoding="utf-8")
    note = course / "note.md"
    os.link(external, note)
    external_identity = (external.stat().st_dev, external.stat().st_ino)
    monkeypatch.setattr(notes_utils, "ROOT", root)
    monkeypatch.setattr(snf, "ROOT", root)
    monkeypatch.setattr(snf, "source_mapping", lambda: {})
    monkeypatch.setattr(sys, "argv", ["sync_note_frontmatter.py", "--date", "2026-08-09"])

    assert snf.main() == 0

    assert external.read_text(encoding="utf-8") == original
    assert (external.stat().st_dev, external.stat().st_ino) == external_identity
    assert (note.stat().st_dev, note.stat().st_ino) != external_identity
    assert note.read_text(encoding="utf-8").startswith("---\n")


def test_sync_entry_propagates_exchange_window_conflict_without_losing_concurrent_edit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    course = root / "course"
    course.mkdir(parents=True)
    note = course / "note.md"
    note.write_text("# Original\n", encoding="utf-8")
    original_exchange = notes_utils._exchange_names
    edited = False
    monkeypatch.setattr(notes_utils, "ROOT", root)
    monkeypatch.setattr(snf, "ROOT", root)
    monkeypatch.setattr(snf, "source_mapping", lambda: {})
    monkeypatch.setattr(sys, "argv", ["sync_note_frontmatter.py", "--date", "2026-08-09"])

    def exchange_after_concurrent_edit(parent_fd: int, left: str, right: str) -> None:
        nonlocal edited
        if not edited:
            edited = True
            note.write_text("# Concurrent\n", encoding="utf-8")
        original_exchange(parent_fd, left, right)

    monkeypatch.setattr(notes_utils, "_exchange_names", exchange_after_concurrent_edit)

    with pytest.raises(notes_utils.ConcurrentWriteError) as captured:
        snf.main()

    assert captured.value.committed is False
    assert note.read_text(encoding="utf-8") == "# Concurrent\n"
    assert list(course.glob(".note.md.conflict-*")) == []


def test_normalize_entry_breaks_hardlink_without_modifying_external_name(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    manifest = root / "course" / "source_manifest.md"
    manifest.parent.mkdir(parents=True)
    original = (
        "| 源文件 | 类型 | 页/slide/记录数 | 抽取方式 | 对应笔记 | 覆盖状态 | 例题状态 | 限制说明 | 最后检查日期 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    external = tmp_path / "manifest-external.md"
    external.write_text(original, encoding="utf-8")
    os.link(external, manifest)
    external_identity = (external.stat().st_dev, external.stat().st_ino)
    monkeypatch.setattr(notes_utils, "ROOT", root)
    monkeypatch.setattr(nsm, "ROOT", root)
    monkeypatch.setattr(nsm, "source_manifest_paths", lambda: [manifest])
    monkeypatch.setattr(sys, "argv", ["normalize_source_manifests.py", "--date", "2026-08-09"])

    assert nsm.main() == 0

    assert external.read_text(encoding="utf-8") == original
    assert (external.stat().st_dev, external.stat().st_ino) == external_identity
    assert (manifest.stat().st_dev, manifest.stat().st_ino) != external_identity
    assert "|---|---|---:|---|---|---|---|---|---|" in manifest.read_text(encoding="utf-8")


def test_wrap_entry_breaks_hardlink_without_modifying_external_name(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    original = "# Note\n\n## PPT/PDF 页级补充索引\n\nraw evidence\n"
    external = tmp_path / "wrap-external.md"
    external.write_text(original, encoding="utf-8")
    note = root / "note.md"
    os.link(external, note)
    external_identity = (external.stat().st_dev, external.stat().st_ino)
    monkeypatch.setattr(notes_utils, "ROOT", root)
    monkeypatch.setattr(wscb, "markdown_files", lambda: [note])
    monkeypatch.setattr(wscb, "regular_note", lambda _path: True)
    monkeypatch.setattr(wscb, "rel", lambda path: path.name)
    monkeypatch.setattr(sys, "argv", ["wrap_source_coverage_blocks.py", "--apply"])

    assert wscb.main() == 0

    assert external.read_text(encoding="utf-8") == original
    assert (external.stat().st_dev, external.stat().st_ino) == external_identity
    assert (note.stat().st_dev, note.stat().st_ino) != external_identity
    assert note.read_text(encoding="utf-8") == "# Note\n"


def test_sync_rejects_change_since_transformation_read(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    note = root / "course" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Original\n", encoding="utf-8")
    original_normalized_text = snf.normalized_text
    raced = False
    monkeypatch.setattr(notes_utils, "ROOT", root)
    monkeypatch.setattr(snf, "ROOT", root)
    monkeypatch.setattr(snf, "markdown_files", lambda: [note])
    monkeypatch.setattr(snf, "source_mapping", lambda: {})
    monkeypatch.setattr(sys, "argv", ["sync_note_frontmatter.py", "--date", "2026-08-09"])

    def normalize_then_race(
        path: Path,
        checked_date: str | None,
        source_map: dict[str, list[str]],
        text: str | None = None,
    ) -> str:
        nonlocal raced
        result = original_normalized_text(path, checked_date, source_map, text)
        if not raced:
            raced = True
            note.write_text("# Concurrent\n", encoding="utf-8")
        return result

    monkeypatch.setattr(snf, "normalized_text", normalize_then_race)

    with pytest.raises(notes_utils.ConcurrentWriteError, match="since transformation input") as captured:
        snf.main()

    assert captured.value.committed is False
    assert note.read_text(encoding="utf-8") == "# Concurrent\n"


def test_normalize_rejects_change_since_transformation_read(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    manifest = root / "course" / "source_manifest.md"
    manifest.parent.mkdir(parents=True)
    original = (
        "| 源文件 | 类型 | 页/slide/记录数 | 抽取方式 | 对应笔记 | 覆盖状态 | 例题状态 | 限制说明 | 最后检查日期 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    concurrent = "# Concurrent manifest update\n"
    manifest.write_text(original, encoding="utf-8")
    original_inode = (manifest.stat().st_dev, manifest.stat().st_ino)
    original_normalized_text = nsm.normalized_text
    raced = False
    monkeypatch.setattr(notes_utils, "ROOT", root)
    monkeypatch.setattr(nsm, "ROOT", root)
    monkeypatch.setattr(nsm, "source_manifest_paths", lambda: [manifest])
    monkeypatch.setattr(sys, "argv", ["normalize_source_manifests.py", "--date", "2026-08-09"])

    def normalize_then_race(text: str, checked_date: str) -> str:
        nonlocal raced
        result = original_normalized_text(text, checked_date)
        if not raced:
            raced = True
            manifest.write_text(concurrent, encoding="utf-8")
            assert (manifest.stat().st_dev, manifest.stat().st_ino) == original_inode
        return result

    monkeypatch.setattr(nsm, "normalized_text", normalize_then_race)

    with pytest.raises(notes_utils.ConcurrentWriteError, match="since transformation input") as captured:
        nsm.main()

    assert captured.value.committed is False
    assert manifest.read_text(encoding="utf-8") == concurrent


def test_wrap_rejects_change_since_transformation_read(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    original = "# Note\n\n## PPT/PDF 页级补充索引\n\nraw evidence\n"
    note.write_text(original, encoding="utf-8")
    original_remove = wscb.remove_visible_sections
    raced = False
    monkeypatch.setattr(notes_utils, "ROOT", root)
    monkeypatch.setattr(wscb, "markdown_files", lambda: [note])
    monkeypatch.setattr(wscb, "regular_note", lambda _path: True)
    monkeypatch.setattr(wscb, "rel", lambda path: path.name)
    monkeypatch.setattr(sys, "argv", ["wrap_source_coverage_blocks.py", "--apply"])

    def remove_then_race(text: str) -> tuple[str, bool]:
        nonlocal raced
        result = original_remove(text)
        if not raced:
            raced = True
            note.write_text("# Concurrent\n", encoding="utf-8")
        return result

    monkeypatch.setattr(wscb, "remove_visible_sections", remove_then_race)

    with pytest.raises(notes_utils.ConcurrentWriteError, match="since transformation input") as captured:
        wscb.main()

    assert captured.value.committed is False
    assert note.read_text(encoding="utf-8") == "# Concurrent\n"


@pytest.mark.parametrize("entry", ["normalize", "sync", "wrap"])
def test_write_entries_reject_invalid_utf8_with_path_and_offset(
    tmp_path: Path,
    monkeypatch,
    entry: str,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    damaged = root / ("source_manifest.md" if entry == "normalize" else "note.md")
    damaged.write_bytes(b"valid\n\xffdamaged\n")
    monkeypatch.setattr(notes_utils, "ROOT", root)

    if entry == "normalize":
        monkeypatch.setattr(nsm, "ROOT", root)
        monkeypatch.setattr(nsm, "source_manifest_paths", lambda: [damaged])
        monkeypatch.setattr(sys, "argv", ["normalize_source_manifests.py"])
        invoke = nsm.main
    elif entry == "sync":
        monkeypatch.setattr(snf, "ROOT", root)
        monkeypatch.setattr(snf, "markdown_files", lambda: [damaged])
        monkeypatch.setattr(snf, "source_mapping", lambda: {})
        monkeypatch.setattr(sys, "argv", ["sync_note_frontmatter.py", "--date", "2026-08-09"])
        invoke = snf.main
    else:
        monkeypatch.setattr(wscb, "markdown_files", lambda: [damaged])
        monkeypatch.setattr(wscb, "regular_note", lambda _path: True)
        monkeypatch.setattr(sys, "argv", ["wrap_source_coverage_blocks.py", "--apply"])
        invoke = wscb.main

    with pytest.raises(notes_utils.UnsafePathError) as captured:
        invoke()

    message = str(captured.value)
    assert str(damaged) in message
    assert "byte offset 6" in message
    assert damaged.read_bytes() == b"valid\n\xffdamaged\n"
