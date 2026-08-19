import pytest
from check_headings import heading_issues_for_text


@pytest.mark.parametrize("level", range(1, 7))
def test_empty_section_before_same_level_heading_is_rejected(level: int) -> None:
    marker = "#" * level
    prefix = "# Root\n\nRoot content.\n\n" if level > 1 else ""
    text = f"{prefix}{marker} Empty\n\n{marker} Next\n\nNext content.\n"

    issues = heading_issues_for_text(text)

    assert any(f"empty H{level} section (Empty)" in issue for issue in issues)


def test_empty_child_before_higher_heading_is_rejected() -> None:
    text = "# Root\n\nRoot content.\n\n### Empty child\n\n## Next\n\nNext content.\n"

    assert any("empty H3 section (Empty child)" in issue for issue in heading_issues_for_text(text))


def test_parent_followed_by_nonempty_child_is_allowed() -> None:
    text = "# Root\n\n## Parent\n\n### Child\n\nChild content.\n\n## Sibling\n\nSibling content.\n"

    assert not any("empty" in issue for issue in heading_issues_for_text(text))


def test_frontmatter_and_fenced_headings_are_ignored() -> None:
    text = (
        "---\n"
        "title: '# Frontmatter heading'\n"
        "---\n\n"
        "# Root\n\n"
        "Root content.\n\n"
        "```markdown\n"
        "## Empty fake heading\n"
        "## Another fake heading\n"
        "```\n\n"
        "## Real\n\n"
        "Real content.\n"
    )

    assert heading_issues_for_text(text) == []


def test_fenced_code_counts_as_section_content() -> None:
    text = "# Root\n\n## Runnable example\n\n```python\nprint('ok')\n```\n"

    assert heading_issues_for_text(text) == []
