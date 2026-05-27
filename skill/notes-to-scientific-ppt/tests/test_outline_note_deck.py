from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/outline_note_deck.py", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )


def test_outline_note_deck_creates_scientific_brief(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    note = notes / "01_method.md"
    note.write_text(
        "\n".join(
            [
                "# From Noise Modeling to Blind Denoising",
                "",
                "## 问题背景",
                "",
                "盲去噪需要在未知噪声下恢复图像。",
                "",
                "## 关键公式",
                "",
                "$$",
                "y = x + n",
                "$$",
                "",
                "## 实验",
                "",
                "| 数据集 | 指标 |",
                "| --- | --- |",
                "| BSD68 | PSNR |",
                "",
                "参考: [paper](https://example.com/paper.pdf)",
            ]
        ),
        encoding="utf-8",
    )
    out = tmp_path / "deck_brief.md"

    result = run_script(str(notes), "--out", str(out), "--title", "Blind Denoising")

    assert f"wrote_deck_brief {out}" in result.stdout
    text = out.read_text(encoding="utf-8")
    assert "# Blind Denoising" in text
    assert "## Source Inventory" in text
    assert "## Extracted Note Structure" in text
    assert "## Suggested Scientific Deck Spine" in text
    assert "## Coverage Checklist" in text
    assert "科研严谨风" in text
    assert "问题背景" in text
    assert "关键公式" in text
    assert "https://example.com/paper.pdf" in text


def test_outline_note_deck_fails_without_markdown(tmp_path: Path):
    result = subprocess.run(
        [sys.executable, "scripts/outline_note_deck.py", str(tmp_path)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    assert result.returncode == 1
    assert "no Markdown note files found" in result.stderr
