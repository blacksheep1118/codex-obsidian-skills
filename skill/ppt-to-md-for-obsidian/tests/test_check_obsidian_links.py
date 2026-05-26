from pathlib import Path

from scripts.check_obsidian_links import check_links


def test_check_links_accepts_markdown_wiki_alias_and_stem(tmp_path: Path):
    (tmp_path / "course").mkdir()
    (tmp_path / "course" / "a.md").write_text(
        "\n".join(
            [
                "# A",
                "[B](b.md)",
                "[[course/b|B alias]]",
                "[[b]]",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "course" / "b.md").write_text("# B\n", encoding="utf-8")

    broken, self_links, checked = check_links(tmp_path)

    assert checked == 3
    assert broken == []
    assert self_links == []


def test_check_links_reports_broken_and_self_links(tmp_path: Path):
    page = tmp_path / "a.md"
    page.write_text("[missing](missing.md)\n[[a]]\n", encoding="utf-8")

    broken, self_links, checked = check_links(tmp_path)

    assert checked == 2
    assert len(broken) == 1
    assert broken[0].target == "missing.md"
    assert len(self_links) == 1
    assert self_links[0].target == "a"
