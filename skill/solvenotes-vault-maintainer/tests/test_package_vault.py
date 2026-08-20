from __future__ import annotations

import os
import stat
import zipfile
from pathlib import Path

import notes_utils
import package_vault as pv
import pytest


def test_package_does_not_follow_external_symlink_file(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("# External\n", encoding="utf-8")
    (root / "linked.md").symlink_to(outside)
    output = tmp_path / "notes.zip"
    monkeypatch.setattr(pv, "ROOT", root)

    count, _size = pv.package(output)

    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["note.md"]
    assert count == 1


def test_package_does_not_follow_external_symlink_directory(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    outside = tmp_path / "outside-directory"
    outside.mkdir()
    (outside / "hidden.md").write_text("# External\n", encoding="utf-8")
    (root / "linked-directory").symlink_to(outside, target_is_directory=True)
    output = tmp_path / "notes.zip"
    monkeypatch.setattr(pv, "ROOT", root)

    count, _size = pv.package(output)

    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["note.md"]
    assert count == 1


@pytest.mark.parametrize("kind", ["live", "broken"])
def test_package_rejects_symlink_vault_root_without_reading_target(tmp_path, monkeypatch, kind: str) -> None:
    outside = tmp_path / "outside-vault"
    if kind == "live":
        outside.mkdir()
        (outside / "hidden.md").write_text("# External\n", encoding="utf-8")
    root = tmp_path / "vault-link"
    root.symlink_to(outside, target_is_directory=True)
    output = tmp_path / "output.zip"
    monkeypatch.setattr(pv, "ROOT", root)

    with pytest.raises(notes_utils.UnsafePathError, match="vault root"):
        pv.package(output)

    assert not output.exists()


def test_relative_output_cannot_escape_vault_root(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    monkeypatch.setattr(pv, "ROOT", root)

    with pytest.raises(notes_utils.UnsafePathError, match="relative output escapes vault root"):
        pv.package(Path("../outside.zip"))

    assert not (tmp_path / "outside.zip").exists()


@pytest.mark.parametrize("kind", ["live", "broken"])
def test_package_rejects_output_leaf_symlink_without_touching_target(tmp_path, monkeypatch, kind: str) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    outside = tmp_path / "outside.zip"
    if kind == "live":
        outside.write_bytes(b"outside")
    output = tmp_path / "output.zip"
    output.symlink_to(outside)
    monkeypatch.setattr(pv, "ROOT", root)

    with pytest.raises(notes_utils.UnsafePathError):
        pv.package(output)

    if kind == "live":
        assert outside.read_bytes() == b"outside"
    assert output.is_symlink()
    assert list(tmp_path.glob(".output.zip.conflict-*")) == []


def test_package_breaks_output_hardlink_and_preserves_external_inode_and_mode(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    outside = tmp_path / "outside.zip"
    outside.write_bytes(b"outside-hardlink")
    outside.chmod(0o640)
    output = tmp_path / "output.zip"
    os.link(outside, output)
    outside_identity = (outside.stat().st_dev, outside.stat().st_ino)
    monkeypatch.setattr(pv, "ROOT", root)

    count, _size = pv.package(output)

    assert count == 1
    assert outside.read_bytes() == b"outside-hardlink"
    assert (outside.stat().st_dev, outside.stat().st_ino) == outside_identity
    assert (output.stat().st_dev, output.stat().st_ino) != outside_identity
    assert stat.S_IMODE(output.stat().st_mode) == 0o640
    with zipfile.ZipFile(output) as archive:
        assert archive.read("note.md") == b"# Local\n"


def test_package_rejects_symlinked_output_parent(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    outside = tmp_path / "outside-directory"
    outside.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(pv, "ROOT", root)

    with pytest.raises(OSError):
        pv.package(linked_parent / "output.zip")

    assert not (outside / "output.zip").exists()
    assert list(outside.glob(".output.zip.conflict-*")) == []


def test_package_archive_failure_preserves_old_output_and_cleans_stage(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    output = tmp_path / "output.zip"
    output.write_bytes(b"old-package")
    monkeypatch.setattr(pv, "ROOT", root)

    def fail_entry(*_args, **_kwargs) -> None:
        raise OSError("simulated archive failure")

    monkeypatch.setattr(pv, "_add_archive_entry", fail_entry)
    with pytest.raises(OSError, match="simulated archive failure"):
        pv.package(output)

    assert output.read_bytes() == b"old-package"
    assert list(tmp_path.glob(".output.zip.conflict-*")) == []


def test_package_publish_failure_preserves_old_output_and_cleans_stage(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    output = tmp_path / "output.zip"
    output.write_bytes(b"old-package")
    monkeypatch.setattr(pv, "ROOT", root)

    def fail_exchange(*_args, **_kwargs) -> None:
        raise OSError("simulated publish failure")

    monkeypatch.setattr(notes_utils, "_exchange_names", fail_exchange)
    with pytest.raises(OSError, match="simulated publish failure"):
        pv.package(output)

    assert output.read_bytes() == b"old-package"
    assert list(tmp_path.glob(".output.zip.conflict-*")) == []


def test_package_replaces_stale_output_and_new_output_is_readable(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    output = tmp_path / "new" / "output.zip"
    monkeypatch.setattr(pv, "ROOT", root)

    pv.package(output)

    assert stat.S_IMODE(output.stat().st_mode) & stat.S_IRUSR
    with zipfile.ZipFile(output) as archive:
        assert archive.read("note.md") == b"# Local\n"


def test_package_preserves_executable_input_mode(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    hook = root / ".githooks" / "pre-push"
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/bin/sh\n", encoding="utf-8")
    hook.chmod(0o755)
    output = tmp_path / "output.zip"
    monkeypatch.setattr(pv, "ROOT", root)

    pv.package(output)

    with zipfile.ZipFile(output) as archive:
        archived_mode = archive.getinfo(".githooks/pre-push").external_attr >> 16
    assert stat.S_ISREG(archived_mode)
    assert stat.S_IMODE(archived_mode) == 0o755


def test_package_excludes_hidden_ci_infrastructure(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    workflow = root / ".github" / "workflows" / "quality.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: quality\n", encoding="utf-8")
    output = tmp_path / "output.zip"
    monkeypatch.setattr(pv, "ROOT", root)

    pv.package(output)

    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["note.md"]


@pytest.mark.parametrize("relative", ["bundle.zip", "exports/bundle.zip"])
def test_package_inside_vault_excludes_output_and_atomic_stage(tmp_path, monkeypatch, relative: str) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    output = root / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"stale-package")
    monkeypatch.setattr(pv, "ROOT", root)

    count, _size = pv.package(output)

    assert count == 1
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["note.md"]
        assert not any(".conflict-" in name for name in archive.namelist())


def test_package_inside_vault_failure_preserves_old_output_and_cleans_stage(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    output = root / "bundle.zip"
    output.write_bytes(b"old-package")
    monkeypatch.setattr(pv, "ROOT", root)

    def fail_entry(*_args, **_kwargs) -> None:
        raise OSError("simulated archive failure")

    monkeypatch.setattr(pv, "_add_archive_entry", fail_entry)
    with pytest.raises(OSError, match="simulated archive failure"):
        pv.package(output)

    assert output.read_bytes() == b"old-package"
    assert list(root.glob(".bundle.zip.conflict-*")) == []


def test_package_input_change_between_lstat_and_open_preserves_old_output(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    note.write_text("# Local\n", encoding="utf-8")
    note.chmod(0o644)
    output = tmp_path / "output.zip"
    output.write_bytes(b"old-package")
    monkeypatch.setattr(pv, "ROOT", root)
    original_open = notes_utils.os.open
    mutated = False

    def open_after_chmod(path, flags, *args, dir_fd=None, **kwargs):
        nonlocal mutated
        reading_note = (
            path == "note.md"
            and dir_fd is not None
            and not flags & (os.O_WRONLY | os.O_RDWR | getattr(os, "O_DIRECTORY", 0))
        )
        if reading_note and not mutated:
            mutated = True
            note.chmod(0o600)
        return original_open(path, flags, *args, dir_fd=dir_fd, **kwargs)

    monkeypatch.setattr(notes_utils.os, "open", open_after_chmod)

    with pytest.raises(notes_utils.UnsafePathError, match="file identity changed during read"):
        pv.package(output)

    assert mutated is True
    assert output.read_bytes() == b"old-package"
    assert list(tmp_path.glob(".output.zip.conflict-*")) == []


def test_package_rolls_back_output_edit_inside_actual_exchange_window(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    output = tmp_path / "output.zip"
    output.write_bytes(b"old-package")
    original_exchange = notes_utils._exchange_names
    mutated = False
    monkeypatch.setattr(pv, "ROOT", root)

    def exchange_after_concurrent_edit(parent_fd: int, left: str, right: str) -> None:
        nonlocal mutated
        if not mutated:
            mutated = True
            output.write_bytes(b"concurrent-package")
        original_exchange(parent_fd, left, right)

    monkeypatch.setattr(notes_utils, "_exchange_names", exchange_after_concurrent_edit)

    with pytest.raises(notes_utils.ConcurrentWriteError) as captured:
        pv.package(output)

    assert captured.value.committed is False
    assert output.read_bytes() == b"concurrent-package"
    assert list(tmp_path.glob(".output.zip.conflict-*")) == []


def test_package_reports_committed_when_directory_fsync_fails(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    output = tmp_path / "output.zip"
    output.write_bytes(b"old-package")
    original_fsync = notes_utils.os.fsync
    monkeypatch.setattr(pv, "ROOT", root)

    def fail_directory_fsync(descriptor: int) -> None:
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError("simulated directory fsync failure")
        original_fsync(descriptor)

    monkeypatch.setattr(notes_utils.os, "fsync", fail_directory_fsync)

    with pytest.raises(notes_utils.DurabilityUncertainError) as captured:
        pv.package(output)

    assert captured.value.committed is True
    assert captured.value.conflict_path is None
    with zipfile.ZipFile(output) as archive:
        assert archive.read("note.md") == b"# Local\n"
    assert list(tmp_path.glob(".output.zip.conflict-*")) == []


def test_package_excludes_tool_caches_and_current_or_legacy_recovery_sidecars(
    tmp_path,
    monkeypatch,
) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    for cache in (".pytest_cache", ".ruff_cache"):
        (root / cache).mkdir()
        (root / cache / "state").write_text(cache, encoding="utf-8")
    recovery_names = (
        ".bundle.zip.conflict-12-0123456789abcdef",
        ".bundle.zip.conflict-12-0123456789abcdef0123456789abcdef",
    )
    for name in recovery_names:
        (root / name).write_bytes(b"recovery")
    (root / ".bundle.zip.conflict-not-owned").write_bytes(b"ordinary-hidden-file")
    output = tmp_path / "output.zip"
    monkeypatch.setattr(pv, "ROOT", root)

    count, _size = pv.package(output)

    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == [".bundle.zip.conflict-not-owned", "note.md"]
    assert count == 2


def test_package_rejects_corrupt_staged_archive_and_preserves_old_output(tmp_path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Local\n", encoding="utf-8")
    output = tmp_path / "output.zip"
    output.write_bytes(b"old-package")
    original_add = pv._add_archive_entry
    monkeypatch.setattr(pv, "ROOT", root)

    def add_then_corrupt(archive: zipfile.ZipFile, path: Path) -> None:
        original_add(archive, path)
        assert archive.fp is not None
        end = archive.fp.tell()
        archive.fp.seek(0)
        archive.fp.write(b"\0" * end)
        archive.fp.seek(end)

    monkeypatch.setattr(pv, "_add_archive_entry", add_then_corrupt)

    with pytest.raises(notes_utils.UnsafePathError, match="staged archive"):
        pv.package(output)

    assert output.read_bytes() == b"old-package"
    assert list(tmp_path.glob(".output.zip.conflict-*")) == []
