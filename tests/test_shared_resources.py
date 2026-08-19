from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest

from scripts.check_obsidian_links import (
    LinkRootError,
    build_stem_index,
    check_links,
    resolve_target,
)
from scripts.shared.safe_io import atomic_binary_writer
from scripts.sync_shared_resources import apply_write_plan


ROOT = Path(__file__).resolve().parents[1]
LINK_CHECKER_ENTRYPOINTS = (
    "scripts/check_obsidian_links.py",
    "skill/notes-to-scientific-ppt/scripts/check_obsidian_links.py",
    "skill/obsidian-vault-organizer/scripts/check_obsidian_links.py",
    "skill/ppt-to-md-for-obsidian/scripts/check_obsidian_links.py",
    "skill/web-course-notes-for-obsidian/scripts/check_obsidian_links.py",
)
LINK_ROOT_ERROR_REASON = "root must be an existing directory without symlink components"


def make_link_checker_root(tmp_path: Path, kind: str) -> Path:
    regular_dir = tmp_path / "regular-vault"
    regular_dir.mkdir()
    (regular_dir / "note.md").write_text(
        "# Note\n\n[missing](missing.md)\n",
        encoding="utf-8",
    )
    if kind == "regular-dir":
        return regular_dir
    if kind == "missing":
        return tmp_path / "missing-vault"

    regular_file = tmp_path / "root.md"
    regular_file.write_text("# Root\n\n[missing](missing.md)\n", encoding="utf-8")
    if kind == "file":
        return regular_file

    alias = tmp_path / f"{kind}-root"
    try:
        if kind == "symlink-dir":
            alias.symlink_to(regular_dir, target_is_directory=True)
        elif kind == "symlink-file":
            alias.symlink_to(regular_file)
        elif kind == "broken-symlink":
            alias.symlink_to(tmp_path / "missing-target", target_is_directory=True)
        else:
            raise AssertionError(f"unknown link-root fixture kind: {kind}")
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    return alias


def test_shared_resource_write_plan_accepts_regular_outputs(tmp_path: Path):
    first = tmp_path / "regular" / "first.py"
    second = tmp_path / "regular" / "second.py"
    first.parent.mkdir()

    apply_write_plan([(first, "first\n"), (second, "second\n")])

    assert first.read_text(encoding="utf-8") == "first\n"
    assert second.read_text(encoding="utf-8") == "second\n"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are unavailable")
def test_shared_resource_write_plan_preserves_existing_output_mode(tmp_path: Path):
    executable = tmp_path / "executable.py"
    executable.write_text("old\n", encoding="utf-8")
    executable.chmod(0o755)

    apply_write_plan([(executable, "new\n")])

    assert stat.S_IMODE(executable.stat().st_mode) == 0o755


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are unavailable")
def test_shared_resource_write_plan_gives_new_data_file_regular_mode(tmp_path: Path):
    new_file = tmp_path / "new.py"

    apply_write_plan([(new_file, "new\n")])

    assert stat.S_IMODE(new_file.stat().st_mode) == 0o644
    assert not new_file.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_atomic_publish_failure_preserves_existing_content_and_mode(tmp_path: Path):
    target = tmp_path / "target.py"
    target.write_text("old\n", encoding="utf-8")
    target.chmod(0o755)
    before_mode = stat.S_IMODE(target.stat().st_mode)

    with pytest.raises(RuntimeError, match="fixture failure"):
        with atomic_binary_writer(target, mode=0o644) as handle:
            handle.write(b"new\n")
            raise RuntimeError("fixture failure")

    assert target.read_text(encoding="utf-8") == "old\n"
    assert stat.S_IMODE(target.stat().st_mode) == before_mode


@pytest.mark.parametrize(
    "kind",
    ("root", "ancestor", "leaf", "broken-leaf", "broken-ancestor"),
)
def test_shared_resource_write_plan_rejects_symlink_paths_before_writing(
    tmp_path: Path,
    kind: str,
):
    good = tmp_path / "good" / "first.py"
    good.parent.mkdir()
    good.write_text("original good\n", encoding="utf-8")
    referent = tmp_path / "referent.py"
    referent.write_text("original referent\n", encoding="utf-8")
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    if kind == "root":
        alias = tmp_path / "root-alias"
        alias.symlink_to(outside_dir, target_is_directory=True)
        bad = alias / "target.py"
    elif kind == "ancestor":
        parent = tmp_path / "target-root"
        parent.mkdir()
        (parent / "alias").symlink_to(outside_dir, target_is_directory=True)
        bad = parent / "alias" / "target.py"
    elif kind == "broken-ancestor":
        parent = tmp_path / "target-root"
        parent.mkdir()
        (parent / "alias").symlink_to(tmp_path / "missing-dir", target_is_directory=True)
        bad = parent / "alias" / "target.py"
    else:
        parent = tmp_path / "target-root"
        parent.mkdir()
        bad = parent / "target.py"
        bad.symlink_to(referent if kind == "leaf" else tmp_path / "missing.py")

    with pytest.raises(ValueError, match="symlink"):
        apply_write_plan([(good, "replacement good\n"), (bad, "replacement referent\n")])

    assert good.read_text(encoding="utf-8") == "original good\n"
    assert referent.read_text(encoding="utf-8") == "original referent\n"


def test_shared_resources_are_in_sync():
    result = subprocess.run(
        [sys.executable, "scripts/sync_shared_resources.py", "--check"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "shared_resource_sync ok" in result.stdout


def test_all_skills_keep_local_validator_copy():
    expected = {
        "notes-to-scientific-ppt": "scripts/validate_skill.py",
        "web-course-notes-for-obsidian": "scripts/validate_skill.py",
        "obsidian-vault-organizer": "scripts/validate_skill.py",
        "ppt-to-md-for-obsidian": "scripts/validate_skill_repo.py",
        "algorithm-job-notes-for-obsidian": "scripts/validate_skill.py",
        "solvenotes-vault-maintainer": "scripts/validate_skill.py",
    }

    for skill_name, validator in expected.items():
        assert (ROOT / "skill" / skill_name / validator).exists(), skill_name


def test_shared_link_checker_rejects_markdown_symlink_outside_root(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    try:
        (vault / "linked.md").symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    result = subprocess.run(
        [sys.executable, "scripts/check_obsidian_links.py", str(vault)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    assert result.returncode == 1
    assert "OUTSIDE_ROOT" in result.stdout


def test_shared_link_checker_keeps_list_continuations_but_masks_top_level_code(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text(
        "    [hidden](hidden.md)\n\n- Body item\n    [visible](visible.md)\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "scripts/check_obsidian_links.py", str(vault)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    assert result.returncode == 1
    assert "checked_links 1" in result.stdout
    assert "visible.md" in result.stdout
    assert "hidden.md" not in result.stdout


@pytest.mark.parametrize(
    "root_kind",
    ("missing", "file", "symlink-dir", "symlink-file", "broken-symlink", "regular-dir"),
)
def test_shared_link_checker_api_validates_root_shape(
    tmp_path: Path,
    root_kind: str,
) -> None:
    root = make_link_checker_root(tmp_path, root_kind)

    if root_kind == "regular-dir":
        broken, self_links, checked = check_links(root)
        assert checked == 1
        assert [issue.target for issue in broken] == ["missing.md"]
        assert self_links == []
        return

    with pytest.raises(LinkRootError) as caught:
        check_links(root)
    assert str(caught.value) == f"{root}: {LINK_ROOT_ERROR_REASON}"


@pytest.mark.parametrize(
    "entrypoint",
    LINK_CHECKER_ENTRYPOINTS,
    ids=("root", "notes", "vault", "ppt", "web"),
)
@pytest.mark.parametrize(
    "root_kind",
    ("missing", "file", "symlink-dir", "symlink-file", "broken-symlink", "regular-dir"),
)
def test_all_shared_link_checker_clis_validate_root_shape(
    tmp_path: Path,
    entrypoint: str,
    root_kind: str,
) -> None:
    root = make_link_checker_root(tmp_path, root_kind)

    result = subprocess.run(
        [sys.executable, entrypoint, str(root)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    if root_kind == "regular-dir":
        assert result.returncode == 1
        assert result.stderr == ""
        assert result.stdout == (
            "checked_links 1\n"
            "broken_links 1\n"
            "self_links 0\n"
            "BROKEN: note.md -> missing.md\n"
        )
        return

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == f"ERROR: {root}: {LINK_ROOT_ERROR_REASON}\n"
    assert "Traceback" not in result.stderr


def write_link_target_matrix(vault: Path, tmp_path: Path) -> tuple[Path, list[Path]]:
    source = vault / "index.md"
    regular = vault / "regular.md"
    regular.write_text("# Regular\n", encoding="utf-8")
    (vault / "directory.md").mkdir()
    (vault / "leaf.md").symlink_to(regular.name)
    real_dir = vault / "real"
    real_dir.mkdir()
    nested = real_dir / "nested.md"
    nested.write_text("# Nested\n", encoding="utf-8")
    (vault / "ancestor").symlink_to(real_dir.name, target_is_directory=True)
    (vault / "broken.md").symlink_to(vault / "missing.md")
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    (vault / "external.md").symlink_to(outside)
    return source, [regular, nested]


def test_shared_link_resolver_requires_regular_nonsymlink_target(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    try:
        source, regular_files = write_link_target_matrix(vault, tmp_path)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    source.write_text("# Index\n", encoding="utf-8")
    by_stem = build_stem_index([source, *regular_files])

    assert resolve_target(vault, source, "regular.md", by_stem) == [
        regular_files[0].resolve()
    ]
    for invalid in (
        "directory.md",
        "leaf.md",
        "ancestor/nested.md",
        "broken.md",
        "external.md",
    ):
        assert resolve_target(vault, source, invalid, by_stem) == []


def test_shared_link_checker_cli_rejects_nonregular_and_symlink_targets(
    tmp_path: Path,
):
    vault = tmp_path / "vault"
    vault.mkdir()
    try:
        source, _regular_files = write_link_target_matrix(vault, tmp_path)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    source.write_text(
        "[regular](regular.md)\n"
        "[directory](directory.md)\n"
        "[leaf](leaf.md)\n"
        "[ancestor](ancestor/nested.md)\n"
        "[broken](broken.md)\n"
        "[external](external.md)\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "scripts/check_obsidian_links.py", str(vault)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    assert result.returncode == 1
    assert "checked_links 6" in result.stdout
    assert "broken_links 6" in result.stdout
    assert "OUTSIDE_ROOT" in result.stdout
    for target in (
        "directory.md",
        "leaf.md",
        "ancestor/nested.md",
        "broken.md",
        "external.md",
    ):
        assert target in result.stdout
