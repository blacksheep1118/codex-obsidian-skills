from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

from pptx import Presentation

from scripts.build_scientific_deck import load_or_create_brief


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


def run_build_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/build_scientific_deck.py", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )


def slide_title(slide) -> str:
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False) and shape.text.strip():
            return shape.text.strip().splitlines()[0]
    return ""


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

    result = run_script(str(notes), "--out", str(out), "--title", "Blind Denoising", "--language", "en")

    assert f"wrote_deck_brief {out}" in result.stdout
    text = out.read_text(encoding="utf-8")
    assert "# Blind Denoising" in text
    assert "## Source Inventory" in text
    assert "## Extracted Note Structure" in text
    assert "## Evidence Ledger" in text
    assert "## Suggested Scientific Deck Spine" in text
    assert "Deck Mode: paper-reading" in text
    assert "## Draft Slide Backlog" in text
    assert "## Coverage Checklist" in text
    assert "科研严谨风" in text
    assert "问题背景" in text
    assert "关键公式" in text
    assert "equation-to-intuition bridge" in text
    assert "result/comparison table" in text
    assert "[formula/algorithm] Turn `关键公式`" in text
    assert "https://example.com/paper.pdf" in text


def test_outline_note_deck_creates_chinese_brief_for_chinese_notes(tmp_path: Path):
    note = tmp_path / "中文笔记.md"
    note.write_text(
        "# 盲图像去噪\n\n## 问题背景\n\n盲去噪需要处理未知噪声。\n\n## 局限\n\n真实噪声仍然复杂。\n",
        encoding="utf-8",
    )

    result = run_script(str(note), "--language", "zh")

    assert "## 来源盘点" in result.stdout
    assert "## 建议科学演示主线" in result.stdout
    assert "演示模式:" in result.stdout
    assert "## 覆盖检查清单" in result.stdout


def test_outline_note_deck_counts_wiki_embeds_and_cjk_chars(tmp_path: Path):
    note = tmp_path / "embed.md"
    note.write_text(
        "# Embed Note\n\n中文内容ABC words。\n\n![[figure 1.png]]\n\n![[dataset.csv]]\n",
        encoding="utf-8",
    )

    result = run_script(str(note), "--language", "en")

    assert "| `embed.md` | Embed Note |" in result.stdout
    assert " | 1 | 1 | 0 | 0 |" in result.stdout


def test_outline_note_deck_respects_max_slides(tmp_path: Path):
    note = tmp_path / "proposal.md"
    note.write_text("# Proposal\n\n## Method\n\nText.\n", encoding="utf-8")

    result = run_script(str(note), "--max-slides", "4", "--language", "en")
    spine = result.stdout.split("## Suggested Scientific Deck Spine", 1)[1].split("## Draft Slide Backlog", 1)[0]
    numbered = [line for line in spine.splitlines() if line.strip() and line.lstrip()[0].isdigit()]

    assert len(numbered) == 4


def test_outline_note_deck_can_follow_local_wiki_links(tmp_path: Path):
    vault = tmp_path / "vault"
    main = vault / "main.md"
    linked = vault / "Linked.md"
    main.parent.mkdir()
    main.write_text("# Main\n\nSee [[Linked]].\n", encoding="utf-8")
    linked.write_text("# Linked\n\n## 实验\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n", encoding="utf-8")

    result = run_script(str(main), "--follow-links", "--vault-root", str(vault), "--max-depth", "1", "--language", "en")

    assert "`main.md`" in result.stdout
    assert "`Linked.md`" in result.stdout
    assert "result/comparison table" in result.stdout


def test_outline_note_deck_supports_explicit_proposal_mode(tmp_path: Path):
    note = tmp_path / "proposal.md"
    note.write_text(
        "\n".join(
            [
                "# Restoration Proposal",
                "",
                "## 研究假设",
                "",
                "更稳定的退化建模可以提升泛化。",
                "",
                "## 里程碑",
                "",
                "- 数据整理",
                "- 基线复现",
                "",
                "## 风险",
                "",
                "真实噪声与合成噪声分布不一致。",
            ]
        ),
        encoding="utf-8",
    )

    result = run_script(str(note), "--mode", "proposal", "--max-slides", "12", "--language", "en")

    assert "# Restoration Proposal" in result.stdout
    assert "Deck Mode: proposal" in result.stdout
    assert "Data requirements and evaluation plan" in result.stdout
    assert "Risks, mitigations, and fallback paths" in result.stdout


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


def test_build_scientific_deck_generates_nonempty_pptx(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "method.md").write_text(
        "# Method Note\n\n## 方法\n\nA claim.\n\n## 关键公式\n\n$$x=y$$\n\n## 实验\n\n| Metric | Value |\n| --- | --- |\n| PSNR | 30 |\n",
        encoding="utf-8",
    )
    brief = tmp_path / "brief.md"
    deck = tmp_path / "test_deck.pptx"
    run_script(str(notes), "--out", str(brief), "--title", "Method Deck", "--language", "en")

    result = run_build_script(str(brief), "--out", str(deck))

    assert f"wrote_pptx {deck}" in result.stdout
    assert deck.exists()
    assert deck.stat().st_size > 1000
    prs = Presentation(str(deck))
    assert len(prs.slides) == 15
    assert [slide_title(slide) for slide in list(prs.slides)[:4]] == [
        "Method Deck",
        "Title and research question",
        "Why this problem matters",
        "Gap in existing work",
    ]
    with ZipFile(deck) as archive:
        names = set(archive.namelist())
    assert "[Content_Types].xml" in names
    assert "ppt/presentation.xml" in names
    assert any(name.startswith("ppt/slides/slide") for name in names)


def test_build_scientific_deck_respects_max_slides_from_notes_folder(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "paper.md").write_text(
        "# Paper Note\n\n## Problem\n\nText.\n\n## Method\n\nText.\n\n## Experiment\n\n| Metric | Value |\n| --- | --- |\n| PSNR | 30 |\n",
        encoding="utf-8",
    )
    deck = tmp_path / "limited.pptx"

    result = run_build_script(str(notes), "--out", str(deck), "--title", "Limited Deck", "--max-slides", "6", "--language", "en")

    assert "slides 6" in result.stdout
    prs = Presentation(str(deck))
    assert len(prs.slides) == 6
    assert [slide_title(slide) for slide in prs.slides] == [
        "Limited Deck",
        "Title and research question",
        "Why this problem matters",
        "Gap in existing work",
        "Limitations and open questions",
        "Appendix index",
    ]


def test_build_scientific_deck_follow_links_adds_linked_notes_to_brief(tmp_path: Path):
    vault = tmp_path / "vault"
    main = vault / "main.md"
    linked = vault / "Linked Evidence.md"
    vault.mkdir()
    main.write_text("# Main Claim\n\nSee [[Linked Evidence]].\n", encoding="utf-8")
    linked.write_text(
        "# Linked Evidence\n\n## Experiment\n\n| Metric | Value |\n| --- | --- |\n| Accuracy | 95 |\n",
        encoding="utf-8",
    )

    brief, _ = load_or_create_brief(
        main,
        title="Linked Deck",
        audience="committee review",
        max_slides=7,
        language="en",
        follow_links=True,
        vault_root=vault,
        max_depth=1,
    )

    assert "Audience: committee review" in brief
    assert "Target main-slide count: 7" in brief
    assert "`main.md`" in brief
    assert "`Linked Evidence.md`" in brief
    assert "result/comparison table" in brief

    deck = tmp_path / "linked.pptx"
    result = run_build_script(
        str(main),
        "--out",
        str(deck),
        "--title",
        "Linked Deck",
        "--max-slides",
        "7",
        "--language",
        "en",
        "--follow-links",
        "--vault-root",
        str(vault),
        "--max-depth",
        "1",
    )

    assert "slides 7" in result.stdout
    assert len(Presentation(str(deck)).slides) == 7
