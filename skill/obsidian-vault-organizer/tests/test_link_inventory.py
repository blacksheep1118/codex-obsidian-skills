from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.link_inventory import build_inventory, render_markdown


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_link_inventory_counts_links_by_file_and_directory(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "Topic.md", "# Topic\n")
    write(
        vault / "course" / "Lesson.md",
        "\n".join(
            [
                "# Lesson",
                "[topic](../Topic.md)",
                "[[Topic|topic alias]]",
                "External: https://example.com/resource",
            ]
        ),
    )

    inventory = build_inventory(vault)

    assert inventory["totals"]["files"] == 2
    assert inventory["totals"]["markdown_links"] == 1
    assert inventory["totals"]["wiki_links"] == 1
    assert inventory["totals"]["external_links"] == 1
    assert inventory["totals"]["total_links"] == 3
    assert inventory["directories"]["course"]["total_links"] == 3

    markdown = render_markdown(inventory)
    assert "## Directory Counts" in markdown
    assert "| course | 1 | 1 | 1 | 1 |" in markdown
