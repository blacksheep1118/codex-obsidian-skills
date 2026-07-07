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
    (notes_dir / "计算机视觉").mkdir(parents=True)

    result = run_script(
        "https://example.com/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf",
        "--notes-dir",
        str(notes_dir),
    )

    collection_dir = notes_dir / "计算机视觉" / "Zhu From Noise Modeling CVPR 2016 paper"
    assert f"created_web_notes {collection_dir}" in result.stdout
    assert (collection_dir / "00_学习地图.md").exists()
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

    map_text = (collection_dir / "00_学习地图.md").read_text(encoding="utf-8")
    assert "## Completion Standard" in map_text
    assert "Scaffolds are not final deliverables" in map_text


def test_create_web_notes_defaults_to_chinese_for_chinese_source(tmp_path: Path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    run_script("https://example.com/课程/机器学习.pdf", "--notes-dir", str(notes_dir))

    note = notes_dir / "网络资源" / "机器学习" / "01_机器学习.md"
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


def test_create_web_notes_uses_network_resource_folder_when_no_category_matches(tmp_path: Path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    run_script("https://example.com/readings/book.pdf", "--notes-dir", str(notes_dir), "--title", "Small Course")

    assert (notes_dir / "网络资源" / "Small Course" / "00_学习地图.md").exists()


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

    note = notes_dir / "网络资源" / "Reading Course" / "01_Reading Course.md"
    note_text = note.read_text(encoding="utf-8")
    assert "## Problem Background" in note_text
    assert "## Core Idea" in note_text
    assert "To complete:" in note_text
    assert "## 问题背景" not in note_text
