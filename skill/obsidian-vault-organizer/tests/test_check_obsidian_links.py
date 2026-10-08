from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_obsidian_links import check_links, check_markdown_links  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_check_links_reports_broken_and_self_links_while_resolving_alias_and_encoded_space(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "Target Note.md", "# Target\n")
    write(
        vault / "Source.md",
        "\n".join(
            [
                "# Source",
                "[encoded](Target%20Note.md)",
                "[broken](Missing.md)",
                "[[Target Note|Readable Alias]]",
                "[[Source]]",
            ]
        ),
    )

    broken, self_links, checked = check_links(vault)

    assert checked == 4
    assert [(issue.source.name, issue.target) for issue in broken] == [("Source.md", "Missing.md")]
    assert [(issue.source.name, issue.target) for issue in self_links] == [("Source.md", "Source")]


def test_check_links_ignores_links_inside_fenced_and_inline_code(tmp_path: Path):
    write(
        tmp_path / "Source.md",
        "`arr[[1]]`\n\n```python\nself.branches[0](x)\ntriton_kernel[grid](x, BLOCK=block)\n```\n",
    )

    broken, self_links, checked = check_links(tmp_path)

    assert checked == 0
    assert broken == []
    assert self_links == []


def test_check_links_ignores_fence_closed_by_a_longer_fence(tmp_path: Path):
    write(tmp_path / "Source.md", "```python\n[[missing]]\n````\n[[also-missing]]\n")

    broken, self_links, checked = check_links(tmp_path)

    assert checked == 1
    assert [issue.target for issue in broken] == ["also-missing"]
    assert self_links == []


def test_check_links_ignores_four_space_indented_code(tmp_path: Path):
    write(tmp_path / "Source.md", "    [[missing]]\n\t[also-missing](no.md)\n")

    broken, self_links, checked = check_links(tmp_path)

    assert checked == 0
    assert broken == []
    assert self_links == []


def test_check_links_resolves_nested_headings_and_explicit_block_ids(tmp_path: Path):
    vault = tmp_path / "vault"
    write(
        vault / "Target.md",
        "# Parent\n## Child\nParagraph anchor. ^paragraph-id\n- list item ^list-id\n",
    )
    write(
        vault / "Source.md",
        "\n".join(
            [
                "[[Target#Parent#Child|Nested heading]]",
                "[[Target#^paragraph-id]]",
                "![[Target#^list-id]]",
                "[[Target#Missing#Child]]",
                "[[Target#^missing-id]]",
            ]
        )
        + "\n",
    )

    broken, self_links, checked = check_links(vault)

    assert checked == 5
    assert [issue.target for issue in broken] == [
        "Target#Missing#Child",
        "Target#^missing-id",
    ]
    assert self_links == []


def test_check_links_ignores_search_queries_comments_and_attachment_fragments(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "Target.md", "<!--\n# Hidden heading\n-->\n# Visible heading\n")
    write(vault / "Image.png", "fixture image")
    write(vault / "Document.pdf", "fixture pdf")
    write(
        vault / "Source.md",
        "\n".join(
            [
                "[[## Visible heading]]",
                "[[^^block-search]]",
                "![[Image.png#outline]]",
                "![[Document.pdf#page=3]]",
                "[[Target#Hidden heading]]",
                "<!-- [[html-comment-missing]] -->",
                "%% [[obsidian-comment-missing]] %%",
                "`[[inline-code-missing]]`",
                "```md",
                "[[fenced-code-missing]]",
                "```",
            ]
        )
        + "\n",
    )

    broken, self_links, checked = check_links(vault)

    assert checked == 5
    assert [issue.target for issue in broken] == ["Target#Hidden heading"]
    assert self_links == []


def test_check_links_respects_escaped_wikilinks_and_markdown_brackets(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "Target.md", "# Target\n")
    write(
        vault / "Source.md",
        "\n".join(
            [
                r"\[[missing-wikilink]]",
                r"\[missing markdown](Missing.md)",
                r"\\[[Target]]",
            ]
        )
        + "\n",
    )

    broken, self_links, checked = check_links(vault)

    assert checked == 1
    assert broken == []
    assert self_links == []


def test_check_markdown_links_checks_only_the_requested_note_population(tmp_path: Path):
    vault = tmp_path / "vault"
    target = vault / "Target.md"
    source = vault / "Source.md"
    template = vault / ".obsidian" / "templates" / "Template.md"
    write(target, "# Target\n")
    write(
        source,
        '[valid](Target.md "title")\n'
        '`[code](Missing.md)`\n'
        '<!-- [comment](Missing.md) -->\n'
        '[excluded template](.obsidian/templates/Template.md)\n'
        '[broken](Missing.md)\n',
    )
    write(template, "[placeholder](MissingTemplate.md)\n")

    broken, self_links, checked = check_markdown_links(
        vault,
        files=[source, target],
    )

    assert checked == 3
    assert [(issue.source.name, issue.target) for issue in broken] == [
        ("Source.md", ".obsidian/templates/Template.md"),
        ("Source.md", "Missing.md"),
    ]
    assert self_links == []


def test_check_links_resolves_used_markdown_reference_forms_without_double_counting(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "Target.md", "# Target\n")
    write(
        vault / "Source.md",
        "\n".join(
            [
                "[full][  CLOUD\t  ID ]",
                "[collapsed][]",
                "[shortcut]",
                "[bad][id]",
                '[inline](Target.md "title")',
                "[duplicate][duplicate]",
                "`[inline-code]`",
                r"\[escaped]",
                "",
                '[cloud id]: Target.md "reference title"',
                "[collapsed]: Target.md",
                "[shortcut]: Target.md",
                "[id]: <Missing.md>",
                "[inline]: InlineMissing.md",
                "[inline-code]: InlineCodeMissing.md",
                "[escaped]: EscapedMissing.md",
                "[duplicate]: Target.md",
                "[duplicate]: DuplicateMissing.md",
                "[unused]: UnusedMissing.md",
            ]
        )
        + "\n",
    )

    broken, self_links, checked = check_links(vault)

    assert checked == 6
    assert [issue.target for issue in broken] == ["Missing.md"]
    assert self_links == []


def test_check_links_ignores_unused_and_non_block_reference_definitions(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "Target.md", "# Target\n")
    write(
        vault / "Source.md",
        "Paragraph text.\n"
        "[paragraph]: MissingParagraph.md\n"
        "[paragraph]\n\n"
        "<!--\n[comment]: MissingComment.md\n[comment]\n-->\n\n"
        "`[inline-code][inline-code]`\n"
        "```md\n[code]: MissingCode.md\n[code]\n```\n\n"
        "[real][good]\n\n"
        "[good]: Target.md\n"
        "[unused]: MissingUnused.md\n"
        "# Local definitions can follow a heading\n"
        "[heading]: Target.md\n"
        "[heading]\n",
    )

    broken, self_links, checked = check_links(vault)

    assert checked == 2
    assert broken == []
    assert self_links == []


def test_check_links_does_not_resolve_headings_or_blocks_in_yaml_frontmatter(tmp_path: Path):
    vault = tmp_path / "vault"
    write(
        vault / "Target.md",
        "\ufeff---\r\n# Ghost heading\r\n## Ghost child\r\nDescription ^ghost-id\r\n---\r\n"
        "# Visible heading\r\n## Visible child\r\nReal paragraph. ^real-id\r\n",
    )
    write(
        vault / "Source.md",
        "[[Target#Ghost heading]]\n"
        "[[Target#Ghost heading#Ghost child]]\n"
        "[[Target#^ghost-id]]\n"
        "[[Target#Visible heading]]\n"
        "[[Target#Visible heading#Visible child]]\n"
        "[[Target#^real-id]]\n",
    )

    broken, self_links, checked = check_links(vault)

    assert checked == 6
    assert [issue.target for issue in broken] == [
        "Target#Ghost heading",
        "Target#Ghost heading#Ghost child",
        "Target#^ghost-id",
    ]
    assert self_links == []
