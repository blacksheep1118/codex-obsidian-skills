from __future__ import annotations

import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SHARED = ROOT / "scripts" / "shared"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

import safe_io  # noqa: E402
import validate_all  # noqa: E402


def platform_top_level_component(path: Path) -> Path:
    absolute = Path(os.path.abspath(path.expanduser()))
    anchor = Path(absolute.anchor)
    return anchor / absolute.relative_to(anchor).parts[0]


def make_input_root_shape(tmp_path: Path, kind: str) -> tuple[Path, Path]:
    regular = tmp_path / "regular-root"
    regular.mkdir()
    sentinel = regular / "sentinel.md"
    sentinel.write_text("keep\n", encoding="utf-8")
    if kind == "regular-dir":
        return regular, sentinel
    if kind == "missing":
        return tmp_path / "missing-root", sentinel

    regular_file = tmp_path / "root.md"
    regular_file.write_text("file\n", encoding="utf-8")
    if kind == "file":
        return regular_file, sentinel
    alias = tmp_path / kind
    if kind == "symlink-file":
        alias.symlink_to(regular_file)
    elif kind == "leaf-same-inode":
        alias.symlink_to(regular, target_is_directory=True)
    elif kind == "ancestor-same-inode":
        real_parent = tmp_path / "real-parent"
        nested = real_parent / "nested"
        nested.mkdir(parents=True)
        alias.symlink_to(real_parent, target_is_directory=True)
        return alias / "nested", sentinel
    elif kind == "external-leaf":
        boundary = tmp_path / "boundary"
        boundary.mkdir()
        alias = boundary / "external-alias"
        alias.symlink_to(regular, target_is_directory=True)
    elif kind == "broken-leaf":
        alias.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    elif kind == "broken-ancestor":
        alias.symlink_to(tmp_path / "missing-parent", target_is_directory=True)
        return alias / "nested", sentinel
    else:
        raise AssertionError(kind)
    return alias, sentinel


@pytest.mark.parametrize(
    "kind",
    (
        "regular-dir",
        "missing",
        "file",
        "symlink-file",
        "leaf-same-inode",
        "ancestor-same-inode",
        "external-leaf",
        "broken-leaf",
        "broken-ancestor",
    ),
)
def test_validate_input_root_preserves_lexical_boundary_and_rejects_aliases(
    tmp_path: Path,
    kind: str,
) -> None:
    root, sentinel = make_input_root_shape(tmp_path, kind)

    if kind == "regular-dir":
        assert safe_io.validate_input_root(root) == root
    else:
        with pytest.raises(safe_io.InputRootError) as caught:
            safe_io.validate_input_root(root)
        assert str(caught.value) == (
            f"{root}: root must be an existing directory without symlink components"
        )
        assert caught.value.path == root

    assert sentinel.read_text(encoding="utf-8") == "keep\n"


def test_atomic_writer_aborts_if_parent_identity_changes(monkeypatch, tmp_path: Path) -> None:
    if not safe_io._supports_dir_fd():
        pytest.skip("directory-relative file operations are unavailable")
    output = tmp_path / "result.md"
    output.write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(safe_io, "_directory_identity_matches", lambda parent_fd, parent: False)

    with pytest.raises(ValueError, match="parent directory changed"):
        safe_io.safe_write_text(output, "replacement\n")

    assert output.read_text(encoding="utf-8") == "original\n"
    assert list(tmp_path.glob(".result.md.*.tmp")) == []


@pytest.mark.parametrize("kind", ["final", "parent", "ancestor"])
def test_safe_write_text_rejects_symlink_components(tmp_path: Path, kind: str) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    sentinel.write_text("keep\n", encoding="utf-8")
    if kind == "final":
        output = tmp_path / "result.md"
        output.symlink_to(sentinel)
    elif kind == "parent":
        parent = tmp_path / "linked-parent"
        parent.symlink_to(outside, target_is_directory=True)
        output = parent / "result.md"
    else:
        ancestor = tmp_path / "linked-ancestor"
        ancestor.symlink_to(outside, target_is_directory=True)
        output = ancestor / "nested" / "result.md"

    with pytest.raises(ValueError, match="symlink"):
        safe_io.safe_write_text(output, "replacement\n")

    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert not (outside / "result.md").exists()
    assert not (outside / "nested" / "result.md").exists()


def test_safe_io_rejects_non_whitelisted_top_level_symlink(monkeypatch) -> None:
    original_lstat = Path.lstat
    output = Path("/untrusted/output.md")
    untrusted_top_level = platform_top_level_component(output)

    def fake_lstat(path: Path):
        if path == untrusted_top_level:
            return SimpleNamespace(st_mode=stat.S_IFLNK)
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)

    with pytest.raises(ValueError, match="untrusted top-level"):
        safe_io._normalize_top_level_alias(output)


def test_subprocess_environment_always_disables_bytecode(monkeypatch) -> None:
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "0")

    environment = validate_all.subprocess_env({"EXTRA_VALIDATION_FLAG": "1"})

    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert environment["EXTRA_VALIDATION_FLAG"] == "1"
