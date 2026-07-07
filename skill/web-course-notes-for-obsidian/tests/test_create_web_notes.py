from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
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


def test_create_web_notes_defaults_to_english_for_english_source(tmp_path: Path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    result = run_script(
        "https://example.com/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf",
        "--notes-dir",
        str(notes_dir),
    )

    collection_dir = notes_dir / "Web Resources" / "Zhu From Noise Modeling CVPR 2016 paper"
    assert f"created_web_notes {collection_dir}" in result.stdout
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
