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


def test_create_web_notes_classifies_cvpr_pdf_into_existing_vision_folder(tmp_path: Path):
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
    assert "source_type: pdf" in note.read_text(encoding="utf-8")


def test_create_web_notes_uses_network_resource_folder_when_no_category_matches(tmp_path: Path):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()

    run_script("https://example.com/readings/book.pdf", "--notes-dir", str(notes_dir), "--title", "Small Course")

    assert (notes_dir / "网络资源" / "Small Course" / "00_学习地图.md").exists()
