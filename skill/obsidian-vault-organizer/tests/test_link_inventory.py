from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.link_inventory import build_inventory, render_markdown  # noqa: E402


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


def test_link_inventory_ignores_links_inside_fenced_and_inline_code(tmp_path: Path):
    write(
        tmp_path / "Code.md",
        "`arr[[1]]`\n\n```python\ntriton_kernel[grid](x, BLOCK=block)\nhttps://example.invalid/in-code\n```\n",
    )

    inventory = build_inventory(tmp_path)

    assert inventory["totals"]["total_links"] == 0


def test_link_inventory_ignores_longer_fence_and_indented_code(tmp_path: Path):
    write(
        tmp_path / "Code.md",
        "```python\n[[missing]]\n````\n[[outside]]\n\n    [[indented]]\n",
    )

    inventory = build_inventory(tmp_path)

    assert inventory["totals"]["total_links"] == 1
    assert inventory["totals"]["wiki_links"] == 1


def test_link_inventory_masks_inline_spans_with_different_backtick_lengths(tmp_path: Path):
    write(tmp_path / "Code.md", "``code ` [[inside]] ``\n[[outside]]\n")

    inventory = build_inventory(tmp_path)

    assert inventory["totals"]["total_links"] == 1
    assert inventory["files"][0]["wiki_links"] == ["outside"]


def test_link_inventory_excludes_guidance_tooling_cache_and_external_symlink(tmp_path: Path):
    write(tmp_path / "Actual.md", "# Actual\n")
    write(tmp_path / "AGENT.md", "# Guidance\n")
    write(tmp_path / "scripts" / "README.md", "# Tooling\n")
    write(tmp_path / ".pytest_cache" / "README.md", "# Cache\n")
    outside = tmp_path.parent / "luna-organizer-outside.md"
    write(outside, "# Outside\n")
    (tmp_path / "linked.md").symlink_to(outside)

    inventory = build_inventory(tmp_path)

    assert [item["file"] for item in inventory["files"]] == ["Actual.md"]
