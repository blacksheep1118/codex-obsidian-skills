from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from create_web_notes import choose_category_dir, safe_path_name  # noqa: E402


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    # Existing tests exercise the explicit publication path.  The production
    # CLI defaults to external staging; the dedicated test below covers that
    # default without hiding it behind this compatibility helper.
    if "--publish" not in args:
        args = (*args, "--publish")
    return subprocess.run(
        [sys.executable, "scripts/create_web_notes.py", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
    )


def run_script_unchecked(*args: str) -> subprocess.CompletedProcess[str]:
    if "--publish" not in args:
        args = (*args, "--publish")
    return subprocess.run(
        [sys.executable, "scripts/create_web_notes.py", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
    )


def write_local_course(path: Path, title: str = "Audit Course") -> None:
    path.write_text(
        f"<html><head><title>{title}</title></head><body><h1>{title}</h1></body></html>",
        encoding="utf-8",
    )


def run_script_raw(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/create_web_notes.py", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
    )


def test_create_web_notes_defaults_to_external_staging(tmp_path: Path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    result = run_script_raw(
        "https://example.com/readings/staged.pdf",
        "--notes-dir",
        str(notes_dir),
        "--title",
        "Staged Course",
    )

    assert "staged_web_notes" in result.stdout
    assert not (notes_dir / "Web Resources" / "Staged Course").exists()
    staged_path = Path(next(line for line in result.stdout.splitlines() if line.startswith("staged_web_notes ")).split(" ", 1)[1])
    assert staged_path.is_dir()
    assert (staged_path / "00_Learning_Map.md").exists()


def test_create_web_notes_defaults_to_english_for_english_source(tmp_path: Path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    result = run_script(
        "https://example.com/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf",
        "--notes-dir",
        str(notes_dir),
    )

    collection_dir = notes_dir / "Web Resources" / "Zhu From Noise Modeling CVPR 2016 paper"
    assert f"published_web_notes {collection_dir}" in result.stdout
    assert (collection_dir / "00_Learning_Map.md").exists()
    assert not (notes_dir / "网络资源").exists()
    assert not (collection_dir / "00_学习地图.md").exists()
    assert (collection_dir / "source_manifest.md").exists()
    note = collection_dir / "01_Zhu From Noise Modeling CVPR 2016 paper.md"
    assert note.exists()
    note_text = note.read_text(encoding="utf-8")
    assert "source_type: pdf" in note_text
    assert "status: scaffold" in note_text
    assert "## Problem Background" in note_text
    assert "## Formulas Or Evidence" in note_text
    assert "## Comparison" in note_text
    assert "## Quick Review" in note_text
    assert "To complete:" in note_text
    assert "## 问题背景" not in note_text
    assert "待补充" not in note_text
    assert "[[00_Learning_Map]]" in note_text
    assert "[[00_学习地图]]" not in note_text

    map_text = (collection_dir / "00_Learning_Map.md").read_text(encoding="utf-8")
    assert "## Completion Standard" in map_text
    assert "Scaffolds are not final deliverables" in map_text


def test_create_web_notes_defaults_to_chinese_for_chinese_source(tmp_path: Path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    run_script("https://example.com/课程/机器学习.pdf", "--notes-dir", str(notes_dir))

    note = notes_dir / "网络资源" / "机器学习" / "01_机器学习.md"
    assert (notes_dir / "网络资源" / "机器学习" / "00_学习地图.md").exists()
    assert note.exists()
    note_text = note.read_text(encoding="utf-8")
    assert "source_type: pdf" in note_text
    assert "status: scaffold" in note_text
    assert "## 问题背景" in note_text
    assert "## 关键公式与变量" in note_text
    assert "## 方法比较" in note_text
    assert "## 精简复习" in note_text
    assert "待补充" in note_text
    assert "## Problem Background" not in note_text
    assert "[[00_学习地图]]" in note_text
    assert "[[00_Learning_Map]]" not in note_text


def test_create_web_notes_uses_english_resource_folder_when_no_category_matches(tmp_path: Path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    run_script("https://example.com/readings/book.pdf", "--notes-dir", str(notes_dir), "--title", "Small Course")

    assert (notes_dir / "Web Resources" / "Small Course" / "00_Learning_Map.md").exists()


def test_create_web_notes_can_write_english_scaffold(tmp_path: Path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    run_script(
        "https://example.com/readings/chapter-01",
        "--notes-dir",
        str(notes_dir),
        "--title",
        "Reading Course",
        "--language",
        "en",
    )

    note = notes_dir / "Web Resources" / "Reading Course" / "01_Reading Course.md"
    note_text = note.read_text(encoding="utf-8")
    assert "## Problem Background" in note_text
    assert "## Core Idea" in note_text
    assert "To complete:" in note_text
    assert "## 问题背景" not in note_text
    assert "[[00_Learning_Map]]" in note_text


def test_create_web_notes_explicit_root_and_map_names_override_language_defaults(tmp_path: Path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    run_script(
        "https://example.com/readings/chapter-02",
        "--notes-dir",
        str(notes_dir),
        "--title",
        "Custom Course",
        "--root-folder-name",
        "Imported Web",
        "--map-note-name",
        "00_Index.md",
    )

    collection_dir = notes_dir / "Imported Web" / "Custom Course"
    assert (collection_dir / "00_Index.md").exists()
    assert not (notes_dir / "Web Resources").exists()
    note_text = (collection_dir / "01_Custom Course.md").read_text(encoding="utf-8")
    assert "[[00_Index]]" in note_text
    assert "[[00_Learning_Map]]" not in note_text
    assert "[[00_学习地图]]" not in note_text


def test_create_web_notes_dry_run_allows_missing_notes_root_without_creating_it(tmp_path: Path) -> None:
    notes_dir = tmp_path / "missing-notes"

    result = run_script(
        "https://example.com/readings/chapter-03",
        "--notes-dir",
        str(notes_dir),
        "--title",
        "Dry Run Course",
        "--language",
        "en",
        "--dry-run",
    )

    assert "would_publish_web_notes" in result.stdout
    assert not notes_dir.exists()


def test_choose_category_dir_rejects_paths_outside_notes_dir(tmp_path: Path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    with pytest.raises(ValueError, match="inside --notes-dir"):
        choose_category_dir(notes_dir, "context", "../escape")

    with pytest.raises(ValueError, match="inside --notes-dir"):
        choose_category_dir(notes_dir, "context", str(tmp_path / "absolute-escape"))


@pytest.mark.parametrize(
    "unsafe",
    (
        r"C:\escape",
        r"C:escape",
        r"\\server\share",
        r"\\?\C:\escape",
        r"\\.\PhysicalDrive0",
        r"C:\escape/mixed",
    ),
)
def test_choose_category_dir_rejects_windows_anchors(
    tmp_path: Path,
    unsafe: str,
) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    (notes_dir / unsafe).mkdir(parents=True)

    with pytest.raises(ValueError, match="inside --notes-dir"):
        choose_category_dir(notes_dir, "context", unsafe)


@pytest.mark.parametrize(
    ("category_name", "title"),
    [
        ("计算机视觉", "Computer Vision Course"),
        ("Vision Notes", "Vision Notes Course"),
    ],
)
def test_create_web_notes_does_not_follow_automatic_category_symlinks(
    tmp_path: Path,
    category_name: str,
    title: str,
) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (notes_dir / category_name).symlink_to(outside, target_is_directory=True)
    source = tmp_path / "course.html"
    write_local_course(source, title)

    result = run_script_unchecked(
        str(source),
        "--notes-dir",
        str(notes_dir),
        "--title",
        title,
        "--language",
        "en",
    )

    assert result.returncode in {0, 1}, result.stdout + result.stderr
    assert list(outside.iterdir()) == []


def test_create_web_notes_rejects_symlinked_fallback_and_collection_directories(tmp_path: Path) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    source = tmp_path / "course.html"
    write_local_course(source)

    (notes_dir / "Web Resources").symlink_to(outside, target_is_directory=True)
    fallback = run_script_unchecked(str(source), "--notes-dir", str(notes_dir), "--language", "en")
    assert fallback.returncode == 1
    assert "symlink" in fallback.stderr.lower()
    assert list(outside.iterdir()) == []

    (notes_dir / "Web Resources").unlink()
    category = notes_dir / "Safe"
    category.mkdir()
    (category / "AuditCollection").symlink_to(outside, target_is_directory=True)
    collection = run_script_unchecked(
        str(source),
        "--notes-dir",
        str(notes_dir),
        "--category",
        "Safe",
        "--folder",
        "AuditCollection",
        "--language",
        "en",
    )
    assert collection.returncode == 1
    assert "symlink" in collection.stderr.lower()
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "kind",
    ("leaf_same_inode", "leaf_external", "ancestor", "broken_leaf", "broken_ancestor"),
)
def test_create_web_notes_rejects_symlinked_notes_root_components(
    tmp_path: Path,
    kind: str,
) -> None:
    real_notes = tmp_path / "real" / "notes"
    if not kind.startswith("broken"):
        real_notes.mkdir(parents=True)
    if kind in {"leaf_same_inode", "leaf_external"}:
        alias_parent = tmp_path / ("real" if kind == "leaf_same_inode" else "boundary")
        alias_parent.mkdir(parents=True, exist_ok=True)
        notes_root = alias_parent / "notes-alias"
        notes_root.symlink_to(real_notes, target_is_directory=True)
        assert notes_root.stat().st_ino == real_notes.stat().st_ino
    elif kind == "ancestor":
        alias_parent = tmp_path / "parent-alias"
        alias_parent.symlink_to(real_notes.parent, target_is_directory=True)
        notes_root = alias_parent / real_notes.name
        assert notes_root.stat().st_ino == real_notes.stat().st_ino
    elif kind == "broken_leaf":
        notes_root = tmp_path / "broken-notes"
        notes_root.symlink_to(tmp_path / "missing-notes", target_is_directory=True)
    else:
        alias_parent = tmp_path / "broken-parent"
        alias_parent.symlink_to(tmp_path / "missing-parent", target_is_directory=True)
        notes_root = alias_parent / "notes"
    source = tmp_path / "course.html"
    write_local_course(source)

    result = run_script_unchecked(
        str(source),
        "--notes-dir",
        str(notes_root),
        "--title",
        "Audit Course",
        "--language",
        "en",
    )

    assert result.returncode == 1
    assert "symlink" in result.stderr.lower()
    if real_notes.exists():
        assert list(real_notes.iterdir()) == []


@pytest.mark.parametrize(
    "output_name",
    ["00_Learning_Map.md", "source_manifest.md", "01_Audit Course.md"],
)
@pytest.mark.parametrize("dangling", [False, True])
def test_create_web_notes_rejects_existing_and_dangling_output_symlinks(
    tmp_path: Path,
    output_name: str,
    dangling: bool,
) -> None:
    notes_dir = tmp_path / "notes"
    collection = notes_dir / "Safe" / "AuditCollection"
    collection.mkdir(parents=True)
    source = tmp_path / "course.html"
    write_local_course(source)
    outside = tmp_path / f"outside-{output_name}"
    if not dangling:
        outside.write_text("external content", encoding="utf-8")
    (collection / output_name).symlink_to(outside)

    result = run_script_unchecked(
        str(source),
        "--notes-dir",
        str(notes_dir),
        "--category",
        "Safe",
        "--folder",
        "AuditCollection",
        "--title",
        "Audit Course",
        "--language",
        "en",
    )

    assert result.returncode == 1
    assert "symlink" in result.stderr.lower()
    assert not outside.exists() if dangling else outside.read_text(encoding="utf-8") == "external content"


def test_choose_category_short_ai_keyword_requires_token_boundary(tmp_path: Path) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    ai_category = notes_dir / "人工智能"
    ai_category.mkdir()

    assert choose_category_dir(notes_dir, "retail email chair catalog") == notes_dir / "网络资源"
    assert choose_category_dir(notes_dir, "A practical AI course") == ai_category


@pytest.mark.parametrize("value", ["CON", "con.md", "PRN", "AUX.txt", "NUL", "COM1", "lpt9.md"])
def test_safe_path_name_avoids_windows_reserved_device_names(value: str) -> None:
    assert safe_path_name(value).startswith("_")


def test_create_web_notes_rerun_reuses_canonical_files_without_suffixes(tmp_path: Path) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    source = tmp_path / "course.html"
    write_local_course(source)
    args = (
        str(source),
        "--notes-dir",
        str(notes_dir),
        "--title",
        "Audit Course",
        "--language",
        "en",
    )

    run_script(*args)
    collection = notes_dir / "Web Resources" / "Audit Course"
    for path in (collection / "00_Learning_Map.md", collection / "01_Audit Course.md"):
        text = path.read_text(encoding="utf-8")
        path.write_text(re.sub(r"\d{4}-\d{2}-\d{2}", "2000-01-01", text), encoding="utf-8")
    run_script(*args)

    assert sorted(path.name for path in collection.iterdir()) == [
        "00_Learning_Map.md",
        "01_Audit Course.md",
        "source_manifest.md",
    ]
    assert "Created: 2000-01-01" in (collection / "00_Learning_Map.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("canonical_name", ["00_Learning_Map.md", "source_manifest.md"])
def test_create_web_notes_fails_closed_on_canonical_content_conflict(
    tmp_path: Path,
    canonical_name: str,
) -> None:
    notes_dir = tmp_path / "notes"
    collection = notes_dir / "Safe" / "AuditCollection"
    collection.mkdir(parents=True)
    (collection / canonical_name).write_text("pre-existing canonical content\n", encoding="utf-8")
    source = tmp_path / "course.html"
    write_local_course(source)

    result = run_script_unchecked(
        str(source),
        "--notes-dir",
        str(notes_dir),
        "--category",
        "Safe",
        "--folder",
        "AuditCollection",
        "--title",
        "Audit Course",
        "--language",
        "en",
    )

    assert result.returncode == 1
    assert "canonical output conflicts" in result.stderr
    assert not (collection / f"{Path(canonical_name).stem}_2.md").exists()
    assert (collection / canonical_name).read_text(encoding="utf-8") == "pre-existing canonical content\n"


def test_detail_collision_uses_actual_suffixed_stem_in_canonical_map(tmp_path: Path) -> None:
    notes_dir = tmp_path / "notes"
    collection = notes_dir / "Safe" / "AuditCollection"
    collection.mkdir(parents=True)
    (collection / "01_Audit Course.md").write_text("unrelated note\n", encoding="utf-8")
    source = tmp_path / "course.html"
    write_local_course(source)

    run_script(
        str(source),
        "--notes-dir",
        str(notes_dir),
        "--category",
        "Safe",
        "--folder",
        "AuditCollection",
        "--title",
        "Audit Course",
        "--language",
        "en",
    )

    map_text = (collection / "00_Learning_Map.md").read_text(encoding="utf-8")
    detail_text = (collection / "01_Audit Course_2.md").read_text(encoding="utf-8")
    assert "[[01_Audit Course_2]]" in map_text
    assert "[[00_Learning_Map]]" in detail_text


@pytest.mark.parametrize("map_name", ["source_manifest.md", "01_Audit Course.md"])
def test_create_web_notes_rejects_output_name_collision_before_writing(
    tmp_path: Path,
    map_name: str,
) -> None:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    source = tmp_path / "course.html"
    write_local_course(source)

    result = run_script_unchecked(
        str(source),
        "--notes-dir",
        str(notes_dir),
        "--title",
        "Audit Course",
        "--language",
        "en",
        "--map-note-name",
        map_name,
    )

    assert result.returncode == 1
    assert "output paths collide" in result.stderr
    collection = notes_dir / "Web Resources" / "Audit Course"
    assert not collection.exists()
