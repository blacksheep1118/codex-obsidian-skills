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


def test_link_inventory_masks_multiline_inline_code_spans(tmp_path: Path) -> None:
    write(
        tmp_path / "Code.md",
        "``code `\n[[inside]] https://inside.invalid\n``\n[[outside]]\n",
    )

    inventory = build_inventory(tmp_path)

    assert inventory["totals"]["total_links"] == 1
    assert inventory["files"][0]["wiki_links"] == ["outside"]


def test_link_inventory_counts_list_continuation_and_parenthesized_target(tmp_path: Path):
    write(tmp_path / "Topic(1).md", "# Topic\n")
    write(tmp_path / "Index.md", "- item\n    [Topic](Topic(1).md)\n")

    inventory = build_inventory(tmp_path)
    index = next(item for item in inventory["files"] if item["file"] == "Index.md")

    assert index["markdown_links"] == ["Topic(1).md"]


def test_link_inventory_handles_nested_escaped_angle_and_raw_url_parentheses(tmp_path: Path):
    write(
        tmp_path / "Index.md",
        "\n".join(
            [
                '[Nested](foo(and(bar)).md "title")',
                r"[Escaped](escaped\(1\).md)",
                "[Spaced](<folder/My Note.md>)",
                "Raw: https://example.com/a_(b).",
                "![Image](not-a-link(1).png)",
            ]
        )
        + "\n",
    )

    inventory = build_inventory(tmp_path)
    index = inventory["files"][0]

    assert index["markdown_links"] == [
        "foo(and(bar)).md",
        "escaped(1).md",
        "folder/My Note.md",
    ]
    assert index["external_links"] == ["https://example.com/a_(b)"]
    assert index["counts"]["total_links"] == 4


def test_link_inventory_counts_angle_bracket_external_link_once(tmp_path: Path):
    write(
        tmp_path / "Index.md",
        "[External](<https://example.com/a(b)?q=1#part>)\n",
    )

    inventory = build_inventory(tmp_path)
    index = inventory["files"][0]

    assert index["markdown_links"] == []
    assert index["external_links"] == ["https://example.com/a(b)?q=1#part"]
    assert index["counts"]["external_links"] == 1
    assert index["counts"]["total_links"] == 1


def test_link_inventory_excludes_raw_url_scans_inside_markdown_source_spans(
    tmp_path: Path,
) -> None:
    write(
        tmp_path / "Index.md",
        r'[Escaped](https://example.com/a\(b\) "title https://title.invalid")' "\n"
        "[Angle](<https://example.com/with space>)\n"
        "![Remote image](https://images.example/plot.png)\n"
        "Raw: https://raw.example/a_(b).\n",
    )

    inventory = build_inventory(tmp_path)
    index = inventory["files"][0]

    assert index["external_links"] == [
        "https://example.com/a(b)",
        "https://example.com/with space",
        "https://raw.example/a_(b)",
    ]
    assert index["counts"]["external_links"] == 3


def test_link_inventory_ignores_md_directories_and_explicit_output(tmp_path: Path):
    write(tmp_path / "Actual.md", "# Actual\n")
    (tmp_path / "directory.md").mkdir()
    output = tmp_path / "inventory.md"
    write(output, "# Prior inventory\n")

    inventory = build_inventory(tmp_path, {output})

    assert [item["file"] for item in inventory["files"]] == ["Actual.md"]


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


def test_link_inventory_obeys_quoted_destination_and_blank_label_boundaries(
    tmp_path: Path,
) -> None:
    write(
        tmp_path / "Index.md",
        '[Quoted]( "quoted".md)\n'
        "[blank\n\nlabel](https://raw.example/resource)\n",
    )

    inventory = build_inventory(tmp_path)

    assert inventory["files"][0]["markdown_links"] == ['"quoted".md']
    assert inventory["files"][0]["external_links"] == [
        "https://raw.example/resource"
    ]
