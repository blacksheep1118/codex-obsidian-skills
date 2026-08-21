import errno
import os
import re
import stat
from pathlib import Path

import notes_utils
import pytest
from notes_utils import (
    ROOT,
    build_note_index,
    formal_source_manifests,
    frontmatter_note_type,
    infer_note_type,
    manifest_rows,
    markdown_files,
    resolve_wikilink,
    table_split_unescaped,
    wikilink_matches,
    wikilinks,
)


def test_wikilinks_extract_targets_and_ignore_embeds() -> None:
    text = "See [[课程/第一章|第一章]] and [[课程/第二章#小节]] but not ![[图片.png]]."

    assert wikilinks(text) == [
        ("课程/第一章|第一章", "课程/第一章"),
        ("课程/第二章#小节", "课程/第二章"),
    ]


def test_wikilinks_ignore_fenced_inline_and_indented_code() -> None:
    text = (
        "`[[InlinePseudo]]` and [[Real]]\n"
        "```\n[[FencedPseudo]]\n```\n"
        "    [[IndentedPseudo]]\n"
    )
    assert wikilinks(text) == [("Real", "Real")]


def test_wikilinks_respect_long_and_multiline_inline_code_spans() -> None:
    text = (
        "``code ` [[LongInlinePseudo]]`` and [[VisibleOne]]\n"
        "``multiline [[MultilinePseudo]]\ncontinues`` and [[VisibleTwo]]\n"
        "`unclosed [[VisibleBecauseSpanIsInvalid]]\n"
    )

    assert wikilinks(text) == [
        ("VisibleOne", "VisibleOne"),
        ("VisibleTwo", "VisibleTwo"),
        ("VisibleBecauseSpanIsInvalid", "VisibleBecauseSpanIsInvalid"),
    ]


def test_wikilinks_respect_tilde_and_longer_backtick_fences() -> None:
    text = (
        "[[VisibleBefore]]\n"
        "~~~text\n[[TildePseudo]]\n~~~\n"
        "````text\n[[LongFencePseudo]]\n```\n[[StillFencedPseudo]]\n````\n"
        "[[VisibleAfter]]\n"
    )

    assert wikilinks(text) == [
        ("VisibleBefore", "VisibleBefore"),
        ("VisibleAfter", "VisibleAfter"),
    ]


def test_markdown_inventory_excludes_supporting_guidance_and_tooling() -> None:
    relative = {path.relative_to(ROOT).as_posix() for path in markdown_files()}
    assert "AGENT.md" not in relative
    assert not any(path.startswith("agent/") for path in relative)
    assert "scripts/README.md" not in relative


def test_link_target_index_excludes_guidance_and_forbidden_agent_tree() -> None:
    index = build_note_index()
    indexed_paths = {path for matches in index.values() for path in matches}

    assert ROOT / "AGENT.md" not in indexed_paths
    assert not any(path.relative_to(ROOT).parts[0] == "agent" for path in indexed_paths)


def test_nested_agent_md_cannot_enter_ordinary_inventory_or_link_index(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import notes_utils

    nested = tmp_path / "课程" / "AGENT.md"
    nested.parent.mkdir()
    nested.write_text("# Reserved guidance name\n", encoding="utf-8")
    ordinary = tmp_path / "课程" / "正文.md"
    ordinary.write_text("# 正文\n", encoding="utf-8")
    monkeypatch.setattr(notes_utils, "ROOT", tmp_path)

    assert notes_utils.markdown_files() == [ordinary]
    indexed_paths = {path for matches in notes_utils.build_note_index().values() for path in matches}
    assert nested not in indexed_paths
    assert ordinary in indexed_paths


def test_agent_casefold_variants_cannot_enter_ordinary_inventory_or_link_index(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import notes_utils

    hidden = tmp_path / "课程" / "Agent" / "隐藏.md"
    hidden.parent.mkdir(parents=True)
    hidden.write_text("# Hidden\n", encoding="utf-8")
    reserved = tmp_path / "课程" / "Agent.md"
    reserved.write_text("# Reserved guidance name\n", encoding="utf-8")
    ordinary = tmp_path / "课程" / "正文.md"
    ordinary.write_text("# 正文\n", encoding="utf-8")
    monkeypatch.setattr(notes_utils, "ROOT", tmp_path)

    assert notes_utils.markdown_files() == [ordinary]
    indexed_paths = {path for matches in notes_utils.build_note_index().values() for path in matches}
    assert hidden not in indexed_paths
    assert reserved not in indexed_paths
    assert ordinary in indexed_paths


def test_external_and_broken_symlink_notes_cannot_enter_inventory_or_link_index(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import notes_utils

    root = tmp_path / "vault"
    course = root / "课程"
    course.mkdir(parents=True)
    ordinary = course / "正文.md"
    ordinary.write_text("# 正文\n", encoding="utf-8")
    outside = tmp_path / "外部.md"
    outside.write_text("# 外部\n", encoding="utf-8")
    live = course / "外部链接.md"
    live.symlink_to(outside)
    broken = course / "悬空链接.md"
    broken.symlink_to(tmp_path / "不存在.md")
    monkeypatch.setattr(notes_utils, "ROOT", root)

    assert notes_utils.markdown_files() == [ordinary]
    indexed_paths = {path for matches in notes_utils.build_note_index().values() for path in matches}
    assert indexed_paths == {ordinary}


def test_resolve_wikilink_uses_explicit_and_sibling_candidates() -> None:
    source = ROOT / "课程/源笔记.md"
    target = ROOT / "课程/目标笔记.md"
    index: dict[str, list[Path]] = {"课程/目标笔记": [target], "跨课程/目标笔记.md": [ROOT / "跨课程/目标笔记.md"]}

    assert resolve_wikilink("目标笔记", source, index) == target
    assert resolve_wikilink("/跨课程/目标笔记.md", source, index) == ROOT / "跨课程/目标笔记.md"


def test_resolve_wikilink_rejects_external_or_empty_targets() -> None:
    source = ROOT / "课程/源笔记.md"

    assert resolve_wikilink("", source, {}) is None
    assert resolve_wikilink("https://example.com/page", source, {}) is None


def test_bare_ambiguous_link_is_not_silently_resolved() -> None:
    source = ROOT / "入口.md"
    root_readme = ROOT / "README.md"
    nested_readme = ROOT / "scripts/README.md"
    index = {"README": [root_readme, nested_readme], "/README": [root_readme]}

    assert wikilink_matches("README", source, index) == [root_readme, nested_readme]
    assert resolve_wikilink("README", source, index) is None
    assert resolve_wikilink("/README", source, index) == root_readme


def test_bare_link_prefers_unique_sibling_before_global_basename() -> None:
    source = ROOT / "课程/入口.md"
    sibling = ROOT / "课程/总览.md"
    other = ROOT / "其他/总览.md"
    index = {
        "课程/总览": [sibling],
        "总览": [sibling, other],
    }

    assert resolve_wikilink("总览", source, index) == sibling


def test_table_split_unescaped_keeps_escaped_and_code_pipes() -> None:
    line = r"| 知识点 | A \| B | `x|y` | 结论 |"

    assert table_split_unescaped(line) == ["知识点", r"A \| B", "`x|y`", "结论"]


def test_table_split_unescaped_rejects_non_table_line() -> None:
    assert table_split_unescaped("not a table") == []


def test_frontmatter_note_type_accepts_supported_explicit_type() -> None:
    text = '---\nnote_type: "source_index"\n---\n\n# Sources\n'

    assert frontmatter_note_type(text) == "source_index"


def test_frontmatter_note_type_rejects_unknown_type() -> None:
    text = '---\nnote_type: "invented_type"\n---\n\n# Note\n'

    assert frontmatter_note_type(text) is None


def test_template_path_overrides_example_frontmatter_type() -> None:
    assert infer_note_type(ROOT / ".obsidian/templates/paper_note.md") == "template"


def test_formal_source_manifests_include_nested_topics_and_exclude_support(tmp_path: Path) -> None:
    expected = tmp_path / "course" / "topic" / "source_manifest.md"
    excluded = tmp_path / "模板" / "source_manifest.md"
    expected.parent.mkdir(parents=True)
    excluded.parent.mkdir(parents=True)
    expected.write_text("# manifest\n", encoding="utf-8")
    excluded.write_text("# template\n", encoding="utf-8")

    assert formal_source_manifests(tmp_path) == [expected]


def test_formal_source_manifests_exclude_agent_casefold_directory(tmp_path: Path) -> None:
    excluded = tmp_path / "course" / "Agent" / "source_manifest.md"
    excluded.parent.mkdir(parents=True)
    excluded.write_text("# reserved\n", encoding="utf-8")

    assert formal_source_manifests(tmp_path) == []


def test_formal_source_manifests_do_not_follow_live_or_broken_symlinks(tmp_path: Path) -> None:
    course = tmp_path / "vault" / "course"
    course.mkdir(parents=True)
    outside = tmp_path / "source_manifest.md"
    outside.write_text("| `outside/file.pdf` | `.pdf` | 1 | external | x | x | x | x | x |\n", encoding="utf-8")
    (course / "source_manifest.md").symlink_to(outside)
    broken_course = tmp_path / "vault" / "broken-course"
    broken_course.mkdir()
    (broken_course / "source_manifest.md").symlink_to(tmp_path / "missing-manifest.md")

    assert formal_source_manifests(tmp_path / "vault") == []
    assert manifest_rows(tmp_path / "vault") == []


def test_manifest_rows_read_nested_formal_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "course" / "topic" / "source_manifest.md"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "| 源文件 | 类型 | 页/slide/记录数 | 抽取方式 | 对应笔记 | 覆盖状态 | 例题状态 | 限制说明 | 最后检查日期 |\n"
        "|---|---|---:|---|---|---|---|---|---|\n"
        "| `course/topic/paper.pdf` | `.pdf` | 3 | pdftotext-page | [[course/topic/note]] | 已映射：文本层 | "
        "已复核：无独立例题 | 未见空白页；未做视觉/OCR | 2026-08-08 |\n",
        encoding="utf-8",
    )

    rows = manifest_rows(tmp_path)

    assert len(rows) == 1
    assert rows[0][0] == manifest
    assert rows[0][1][0] == "`course/topic/paper.pdf`"


def test_symlink_component_check_rejects_lexical_and_absolute_escape(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    inside = root / "note.md"
    inside.write_text("inside\n", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")

    assert notes_utils.has_symlink_component(inside, root) is False
    assert notes_utils.has_symlink_component(root / ".." / "outside.md", root) is True
    assert notes_utils.has_symlink_component(outside, root) is True
    assert notes_utils.is_regular_file_without_symlinks(root / ".." / "outside.md", root) is False
    assert notes_utils.is_regular_file_without_symlinks(outside, root) is False


@pytest.mark.parametrize("kind", ["live", "broken"])
def test_atomic_text_writer_rejects_leaf_symlink_without_touching_target(
    tmp_path: Path,
    monkeypatch,
    kind: str,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    target = tmp_path / "outside.md"
    if kind == "live":
        target.write_text("outside\n", encoding="utf-8")
    link = root / "note.md"
    link.symlink_to(target)
    monkeypatch.setattr(notes_utils, "ROOT", root)

    with pytest.raises(notes_utils.UnsafePathError):
        notes_utils.write_text_if_changed(link, "changed\n")

    if kind == "live":
        assert target.read_text(encoding="utf-8") == "outside\n"
    assert link.is_symlink()
    assert list(root.glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_breaks_hardlink_and_preserves_mode(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    outside.chmod(0o640)
    note = root / "note.md"
    os.link(outside, note)
    outside_identity = (outside.stat().st_dev, outside.stat().st_ino)
    monkeypatch.setattr(notes_utils, "ROOT", root)

    assert notes_utils.write_text_if_changed(note, "changed\n") is True

    assert note.read_text(encoding="utf-8") == "changed\n"
    assert outside.read_text(encoding="utf-8") == "outside\n"
    assert (outside.stat().st_dev, outside.stat().st_ino) == outside_identity
    assert (note.stat().st_dev, note.stat().st_ino) != outside_identity
    assert stat.S_IMODE(note.stat().st_mode) == 0o640


def test_atomic_text_writer_leaves_unchanged_hardlink_shared_without_writing(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("same\n", encoding="utf-8")
    note = root / "note.md"
    os.link(outside, note)
    shared_identity = (outside.stat().st_dev, outside.stat().st_ino)
    monkeypatch.setattr(notes_utils, "ROOT", root)

    assert notes_utils.write_text_if_changed(note, "same\n") is False

    assert note.read_text(encoding="utf-8") == "same\n"
    assert outside.read_text(encoding="utf-8") == "same\n"
    assert (note.stat().st_dev, note.stat().st_ino) == shared_identity
    assert (outside.stat().st_dev, outside.stat().st_ino) == shared_identity
    assert list(root.glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_preserves_original_and_cleans_stage_on_publish_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def fail_exchange(*_args, **_kwargs) -> None:
        raise OSError("simulated publish failure")

    monkeypatch.setattr(notes_utils, "_exchange_names", fail_exchange)
    with pytest.raises(OSError, match="simulated publish failure"):
        notes_utils.write_text_if_changed(note, "changed\n")

    assert note.read_text(encoding="utf-8") == "original\n"
    assert list(root.glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_aborts_parent_identity_switch(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    course = root / "course"
    course.mkdir(parents=True)
    note = course / "note.md"
    note.write_text("original\n", encoding="utf-8")
    moved = root / "moved-course"
    outside = tmp_path / "outside-course"
    outside.mkdir()
    (outside / "note.md").write_text("outside\n", encoding="utf-8")
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def switch_parent(_path: Path) -> None:
        course.rename(moved)
        course.symlink_to(outside, target_is_directory=True)

    monkeypatch.setattr(notes_utils, "_atomic_publish_hook", switch_parent)
    with pytest.raises(notes_utils.UnsafePathError, match="parent directory"):
        notes_utils.write_text_if_changed(note, "changed\n")

    assert (moved / "note.md").read_text(encoding="utf-8") == "original\n"
    assert (outside / "note.md").read_text(encoding="utf-8") == "outside\n"
    assert list(moved.glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_aborts_ancestor_symlink_switch_even_to_same_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    parent = root / "level" / "course"
    parent.mkdir(parents=True)
    note = parent / "note.md"
    note.write_text("original\n", encoding="utf-8")
    moved = root / "moved-level"
    level = root / "level"
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def switch_ancestor(_path: Path) -> None:
        level.rename(moved)
        level.symlink_to(moved, target_is_directory=True)

    monkeypatch.setattr(notes_utils, "_atomic_publish_hook", switch_ancestor)
    with pytest.raises(notes_utils.UnsafePathError, match="unsafe parent directory"):
        notes_utils.write_text_if_changed(note, "changed\n")

    assert (moved / "course" / "note.md").read_text(encoding="utf-8") == "original\n"
    assert list((moved / "course").glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_aborts_in_place_concurrent_edit(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def concurrent_edit(_path: Path) -> None:
        note.write_text("concurrent\n", encoding="utf-8")

    monkeypatch.setattr(notes_utils, "_atomic_publish_hook", concurrent_edit)
    with pytest.raises(notes_utils.UnsafePathError, match="destination identity changed"):
        notes_utils.write_text_if_changed(note, "writer-change\n")

    assert note.read_text(encoding="utf-8") == "concurrent\n"
    assert list(root.glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_new_file_is_readable(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "new" / "note.md"
    monkeypatch.setattr(notes_utils, "ROOT", root)

    assert notes_utils.write_text_if_changed(note, "new\n") is True

    assert note.read_text(encoding="utf-8") == "new\n"
    assert stat.S_IMODE(note.stat().st_mode) & stat.S_IRUSR


def test_safe_read_rejects_same_inode_change_between_lstat_and_open(tmp_path: Path, monkeypatch) -> None:
    note = tmp_path / "note.md"
    note.write_text("original\n", encoding="utf-8")
    note.chmod(0o644)
    original_open = notes_utils.os.open
    mutated = False

    def open_after_chmod(path, flags, *args, dir_fd=None, **kwargs):
        nonlocal mutated
        reading_leaf = (
            path == "note.md"
            and dir_fd is not None
            and not flags & (os.O_WRONLY | os.O_RDWR | getattr(os, "O_DIRECTORY", 0))
        )
        if reading_leaf and not mutated:
            mutated = True
            note.chmod(0o600)
        return original_open(path, flags, *args, dir_fd=dir_fd, **kwargs)

    monkeypatch.setattr(notes_utils.os, "open", open_after_chmod)

    with pytest.raises(notes_utils.UnsafePathError, match="file identity changed during read"):
        notes_utils.read_bytes_with_metadata(note)

    assert mutated is True
    assert note.read_text(encoding="utf-8") == "original\n"
    assert stat.S_IMODE(note.stat().st_mode) == 0o600


def test_atomic_text_writer_rolls_back_edit_inside_actual_exchange_window(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    original_exchange = notes_utils._exchange_names
    mutated = False
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def exchange_after_concurrent_edit(parent_fd: int, left: str, right: str) -> None:
        nonlocal mutated
        if not mutated:
            mutated = True
            note.write_text("concurrent-after-check\n", encoding="utf-8")
        original_exchange(parent_fd, left, right)

    monkeypatch.setattr(notes_utils, "_exchange_names", exchange_after_concurrent_edit)

    with pytest.raises(notes_utils.ConcurrentWriteError) as captured:
        notes_utils.write_text_if_changed(note, "writer-change\n")

    assert captured.value.committed is False
    assert captured.value.conflict_path is None
    assert note.read_text(encoding="utf-8") == "concurrent-after-check\n"
    assert list(root.glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_restores_leaf_symlink_swapped_inside_exchange_window(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    original_exchange = notes_utils._exchange_names
    swapped = False
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def exchange_after_symlink_swap(parent_fd: int, left: str, right: str) -> None:
        nonlocal swapped
        if not swapped:
            swapped = True
            note.unlink()
            note.symlink_to(outside)
        original_exchange(parent_fd, left, right)

    monkeypatch.setattr(notes_utils, "_exchange_names", exchange_after_symlink_swap)

    with pytest.raises(notes_utils.ConcurrentWriteError):
        notes_utils.write_text_if_changed(note, "writer-change\n")

    assert note.is_symlink()
    assert note.read_text(encoding="utf-8") == "outside\n"
    assert outside.read_text(encoding="utf-8") == "outside\n"
    assert list(root.glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_preserves_prior_version_when_rollback_exchange_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    original_exchange = notes_utils._exchange_names
    calls = 0
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def fail_second_exchange(parent_fd: int, left: str, right: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            note.write_text("concurrent-before-exchange\n", encoding="utf-8")
            original_exchange(parent_fd, left, right)
            return
        raise OSError("simulated rollback exchange failure")

    monkeypatch.setattr(notes_utils, "_exchange_names", fail_second_exchange)

    with pytest.raises(notes_utils.ConcurrentWriteError) as captured:
        notes_utils.write_text_if_changed(note, "writer-change\n")

    conflict = captured.value.conflict_path
    assert captured.value.committed is True
    assert conflict is not None
    assert note.read_text(encoding="utf-8") == "writer-change\n"
    assert conflict.read_text(encoding="utf-8") == "concurrent-before-exchange\n"


def test_atomic_text_writer_no_replace_rejects_destination_appearing_inside_link(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    original_link = notes_utils.os.link
    appeared = False
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def link_after_destination_appears(*args, **kwargs) -> None:
        nonlocal appeared
        if not appeared:
            appeared = True
            note.write_text("concurrent-new\n", encoding="utf-8")
        original_link(*args, **kwargs)

    monkeypatch.setattr(notes_utils.os, "link", link_after_destination_appears)

    with pytest.raises(notes_utils.ConcurrentWriteError, match="appeared during no-replace") as captured:
        notes_utils.write_text_if_changed(note, "writer-new\n")

    assert captured.value.committed is False
    assert note.read_text(encoding="utf-8") == "concurrent-new\n"
    assert list(root.glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_preserves_both_versions_if_destination_changes_before_rollback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    original_exchange = notes_utils._exchange_names
    calls = 0
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def exchange_then_change_destination(parent_fd: int, left: str, right: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            note.write_text("concurrent-before-exchange\n", encoding="utf-8")
            original_exchange(parent_fd, left, right)
            note.write_text("third-party-after-exchange\n", encoding="utf-8")
            return
        original_exchange(parent_fd, left, right)

    monkeypatch.setattr(notes_utils, "_exchange_names", exchange_then_change_destination)

    with pytest.raises(notes_utils.ConcurrentWriteError) as captured:
        notes_utils.write_text_if_changed(note, "writer-change\n")

    conflict = captured.value.conflict_path
    assert captured.value.committed is False
    assert conflict is not None
    assert note.read_text(encoding="utf-8") == "third-party-after-exchange\n"
    assert conflict.read_text(encoding="utf-8") == "concurrent-before-exchange\n"


def test_atomic_text_writer_preserves_second_change_made_inside_rollback_exchange(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    original_exchange = notes_utils._exchange_names
    calls = 0
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def exchange_with_two_concurrent_edits(parent_fd: int, left: str, right: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            note.write_text("concurrent-before-exchange\n", encoding="utf-8")
        elif calls == 2:
            note.write_text("third-party-during-rollback\n", encoding="utf-8")
        original_exchange(parent_fd, left, right)

    monkeypatch.setattr(notes_utils, "_exchange_names", exchange_with_two_concurrent_edits)

    with pytest.raises(notes_utils.ConcurrentWriteError) as captured:
        notes_utils.write_text_if_changed(note, "writer-change\n")

    conflict = captured.value.conflict_path
    assert captured.value.committed is False
    assert conflict is not None
    assert note.read_text(encoding="utf-8") == "concurrent-before-exchange\n"
    assert conflict.read_text(encoding="utf-8") == "third-party-during-rollback\n"


def test_atomic_text_writer_rolls_back_parent_switch_inside_exchange_primitive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    parent = root / "course"
    parent.mkdir(parents=True)
    note = parent / "note.md"
    note.write_text("original\n", encoding="utf-8")
    moved = root / "moved-course"
    outside = tmp_path / "outside-course"
    outside.mkdir()
    (outside / "note.md").write_text("outside\n", encoding="utf-8")
    original_exchange = notes_utils._exchange_names
    switched = False
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def exchange_after_parent_switch(parent_fd: int, left: str, right: str) -> None:
        nonlocal switched
        if not switched:
            switched = True
            parent.rename(moved)
            parent.symlink_to(outside, target_is_directory=True)
        original_exchange(parent_fd, left, right)

    monkeypatch.setattr(notes_utils, "_exchange_names", exchange_after_parent_switch)

    with pytest.raises(notes_utils.UnsafePathError, match="unsafe parent directory"):
        notes_utils.write_text_if_changed(note, "writer-change\n")

    assert (moved / "note.md").read_text(encoding="utf-8") == "original\n"
    assert (outside / "note.md").read_text(encoding="utf-8") == "outside\n"
    assert list(moved.glob(".note.md.conflict-*")) == []


@pytest.mark.parametrize("platform_name", ["darwin", "linux"])
def test_native_exchange_dispatch_uses_swap_flag_and_preserves_errno(
    monkeypatch,
    platform_name: str,
) -> None:
    calls: list[tuple[object, ...]] = []

    class FakeFunction:
        argtypes = None
        restype = None

        def __call__(self, *args):
            calls.append(args)
            notes_utils.ctypes.set_errno(errno.ENOSYS)
            return -1

    function = FakeFunction()

    class FakeLibrary:
        renameatx_np = function
        renameat2 = function

    monkeypatch.setattr(notes_utils.sys, "platform", platform_name)
    monkeypatch.setattr(notes_utils.ctypes, "CDLL", lambda *_args, **_kwargs: FakeLibrary())

    with pytest.raises(OSError) as captured:
        notes_utils._platform_exchange_names(9, "left", "right")

    assert captured.value.errno == errno.ENOSYS
    assert calls == [(9, b"left", 9, b"right", 0x00000002)]


def test_atomic_text_writer_missing_exchange_primitive_fails_without_replace_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(notes_utils, "ROOT", root)
    monkeypatch.setattr(
        notes_utils,
        "_platform_exchange_names",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AttributeError("missing primitive")),
    )
    monkeypatch.setattr(
        notes_utils.os,
        "replace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unsafe fallback used")),
    )

    with pytest.raises(notes_utils.UnsafePathError, match="atomic name exchange is unavailable"):
        notes_utils.write_text_if_changed(note, "writer-change\n")

    assert note.read_text(encoding="utf-8") == "original\n"
    assert list(root.glob(".note.md.conflict-*")) == []


@pytest.mark.parametrize(
    "error_number",
    [errno.ENOSYS, errno.EINVAL, getattr(errno, "EOPNOTSUPP", errno.EINVAL)],
)
def test_atomic_text_writer_exchange_errno_fails_closed_without_fallback(
    tmp_path: Path,
    monkeypatch,
    error_number: int,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def fail_native_exchange(*_args, **_kwargs) -> None:
        raise OSError(error_number, os.strerror(error_number))

    monkeypatch.setattr(notes_utils, "_platform_exchange_names", fail_native_exchange)

    with pytest.raises(notes_utils.UnsafePathError, match="atomic name exchange is unavailable"):
        notes_utils.write_text_if_changed(note, "writer-change\n")

    assert note.read_text(encoding="utf-8") == "original\n"
    assert list(root.glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_reports_committed_when_directory_fsync_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    original_fsync = notes_utils.os.fsync
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def fail_directory_fsync(descriptor: int) -> None:
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError("simulated directory fsync failure")
        original_fsync(descriptor)

    monkeypatch.setattr(notes_utils.os, "fsync", fail_directory_fsync)

    with pytest.raises(notes_utils.DurabilityUncertainError) as captured:
        notes_utils.write_text_if_changed(note, "writer-change\n")

    assert captured.value.committed is True
    assert captured.value.conflict_path is None
    assert note.read_text(encoding="utf-8") == "writer-change\n"
    assert list(root.glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_preserves_old_version_if_post_exchange_check_raises_baseexception(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    original_assert = notes_utils._assert_directory_identity
    checks = 0
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def crash_after_exchange(directory: Path, expected: os.stat_result) -> None:
        nonlocal checks
        checks += 1
        if checks == 3:
            raise KeyboardInterrupt("unexpected post-exchange interruption")
        original_assert(directory, expected)

    monkeypatch.setattr(notes_utils, "_assert_directory_identity", crash_after_exchange)

    with pytest.raises(KeyboardInterrupt, match="unexpected post-exchange interruption") as captured:
        notes_utils.write_text_if_changed(note, "writer-change\n")

    conflicts = list(root.glob(".note.md.conflict-*"))
    assert captured.value.committed is True
    assert captured.value.conflict_path == conflicts[0]
    assert note.read_text(encoding="utf-8") == "writer-change\n"
    assert len(conflicts) == 1
    assert conflicts[0].read_text(encoding="utf-8") == "original\n"


def test_atomic_text_writer_reports_commit_if_no_replace_link_then_interrupts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    original_link = notes_utils.os.link
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def link_then_interrupt(*args, **kwargs) -> None:
        original_link(*args, **kwargs)
        raise KeyboardInterrupt("interrupted after link")

    monkeypatch.setattr(notes_utils.os, "link", link_then_interrupt)

    with pytest.raises(KeyboardInterrupt, match="interrupted after link") as captured:
        notes_utils.write_text_if_changed(note, "writer-new\n")

    assert captured.value.committed is True
    assert captured.value.conflict_path is None
    assert note.read_text(encoding="utf-8") == "writer-new\n"
    assert list(root.glob(".note.md.conflict-*")) == []


def test_atomic_text_writer_reports_commit_and_recovery_if_exchange_then_interrupts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    original_exchange = notes_utils._exchange_names
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def exchange_then_interrupt(parent_fd: int, left: str, right: str) -> None:
        original_exchange(parent_fd, left, right)
        raise KeyboardInterrupt("interrupted after exchange")

    monkeypatch.setattr(notes_utils, "_exchange_names", exchange_then_interrupt)

    with pytest.raises(KeyboardInterrupt, match="interrupted after exchange") as captured:
        notes_utils.write_text_if_changed(note, "writer-change\n")

    conflict = captured.value.conflict_path
    assert captured.value.committed is True
    assert conflict is not None
    assert note.read_text(encoding="utf-8") == "writer-change\n"
    assert conflict.read_text(encoding="utf-8") == "original\n"


def test_explicit_text_version_rejects_old_input_and_accepts_fresh_input(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("version one\n", encoding="utf-8")
    monkeypatch.setattr(notes_utils, "ROOT", root)

    _old_text, old_version = notes_utils.read_text_with_version(note)
    note.write_text("version two\n", encoding="utf-8")
    current_text, current_version = notes_utils.read_text_with_version(note)

    with pytest.raises(notes_utils.ConcurrentWriteError) as captured:
        notes_utils.write_text_if_changed(note, "derived from old\n", expected_version=old_version)

    assert captured.value.committed is False
    assert note.read_text(encoding="utf-8") == "version two\n"
    assert notes_utils.write_text_if_changed(
        note,
        current_text.upper(),
        expected_version=current_version,
    )
    assert note.read_text(encoding="utf-8") == "VERSION TWO\n"


def test_interrupted_publication_works_without_add_note_method(tmp_path: Path) -> None:
    class LegacyInterrupt(BaseException):
        add_note = None

    cause = LegacyInterrupt("legacy runtime")
    path = tmp_path / "note.md"

    with pytest.raises(LegacyInterrupt) as captured:
        notes_utils._raise_interrupted_publication(cause, path=path, committed=False)

    assert captured.value is cause
    assert captured.value.committed is False
    assert captured.value.conflict_path is None


def test_atomic_text_writer_new_destination_parent_switch_never_unlinks_public_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    parent = root / "course"
    parent.mkdir(parents=True)
    note = parent / "note.md"
    moved = root / "moved-course"
    outside = tmp_path / "outside-course"
    outside.mkdir()
    original_link = notes_utils.os.link
    original_unlink = notes_utils.os.unlink
    public_unlink_attempts = 0
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def link_then_switch_parent(*args, **kwargs) -> None:
        original_link(*args, **kwargs)
        original_unlink("note.md", dir_fd=kwargs["dst_dir_fd"])
        note.write_text("third-party-after-link\n", encoding="utf-8")
        parent.rename(moved)
        parent.symlink_to(outside, target_is_directory=True)

    def reject_public_unlink(name, *args, **kwargs) -> None:
        nonlocal public_unlink_attempts
        if name == "note.md":
            public_unlink_attempts += 1
            raise AssertionError("public destination must not be unlinked after parent mismatch")
        original_unlink(name, *args, **kwargs)

    monkeypatch.setattr(notes_utils.os, "link", link_then_switch_parent)
    monkeypatch.setattr(notes_utils.os, "unlink", reject_public_unlink)

    with pytest.raises(notes_utils.ConcurrentWriteError) as captured:
        notes_utils.write_text_if_changed(note, "writer-new\n")

    conflict = captured.value.conflict_path
    assert captured.value.committed is True
    assert conflict is not None
    assert conflict.parent == moved
    assert public_unlink_attempts == 0
    assert (moved / "note.md").read_text(encoding="utf-8") == "third-party-after-link\n"
    assert conflict.read_text(encoding="utf-8") == "writer-new\n"
    assert not (outside / "note.md").exists()


def test_atomic_writer_does_not_unlink_replaced_internal_sidecar_on_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    displaced_stage = root / "displaced-stage"
    replaced_sidecar: Path | None = None

    def fail_after_replacing_sidecar(stream) -> None:
        nonlocal replaced_sidecar
        stream.write(b"partial-writer-output\n")
        replaced_sidecar = next(root.glob(".note.md.conflict-*"))
        replaced_sidecar.rename(displaced_stage)
        replaced_sidecar.write_text("third-party-sidecar\n", encoding="utf-8")
        raise OSError("simulated writer failure after sidecar replacement")

    with pytest.raises(OSError, match="simulated writer failure"):
        notes_utils.atomic_write_file(note, fail_after_replacing_sidecar, root=root)

    assert replaced_sidecar is not None
    assert re.fullmatch(r"\.note\.md\.conflict-\d+-[0-9a-f]{32}", replaced_sidecar.name)
    assert note.read_text(encoding="utf-8") == "original\n"
    assert replaced_sidecar.read_text(encoding="utf-8") == "third-party-sidecar\n"
    assert displaced_stage.read_text(encoding="utf-8") == "partial-writer-output\n"


def test_atomic_writer_preserves_replaced_sidecar_at_success_cleanup_boundary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("original\n", encoding="utf-8")
    displaced_old = root / "displaced-old-version"
    original_cleanup = notes_utils._unlink_verified_sidecar
    replaced = False
    monkeypatch.setattr(notes_utils, "ROOT", root)

    def cleanup_after_sidecar_replacement(
        parent_fd: int,
        path: Path,
        name: str,
        expected: os.stat_result,
        expected_digest: bytes,
        *,
        staged: bool,
        committed: bool,
    ) -> None:
        nonlocal replaced
        if not replaced:
            replaced = True
            sidecar = notes_utils._sidecar_path(parent_fd, path, name)
            sidecar.rename(displaced_old)
            sidecar.write_text("third-party-sidecar\n", encoding="utf-8")
        original_cleanup(
            parent_fd,
            path,
            name,
            expected,
            expected_digest,
            staged=staged,
            committed=committed,
        )

    monkeypatch.setattr(notes_utils, "_unlink_verified_sidecar", cleanup_after_sidecar_replacement)

    with pytest.raises(notes_utils.AtomicPublishError) as captured:
        notes_utils.write_text_if_changed(note, "writer-change\n")

    conflict = captured.value.conflict_path
    assert captured.value.committed is True
    assert conflict is not None
    assert note.read_text(encoding="utf-8") == "writer-change\n"
    assert conflict.read_text(encoding="utf-8") == "third-party-sidecar\n"
    assert displaced_old.read_text(encoding="utf-8") == "original\n"
