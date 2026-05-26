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


def test_check_links_accepts_spaces_url_encoding_anchors_and_root_paths(tmp_path: Path):
    (tmp_path / "folder").mkdir()
    (tmp_path / "folder" / "My Note.md").write_text("# My Note\n", encoding="utf-8")
    (tmp_path / "index.md").write_text("# Index\n", encoding="utf-8")
    (tmp_path / "folder" / "topic.md").write_text(
        "\n".join(
            [
                "[Encoded](My%20Note.md#section)",
                "[Root](/folder/My%20Note.md?query=1)",
                "[[folder/My Note#Section|Wiki alias]]",
                "[Parent](../index.md)",
            ]
        ),
        encoding="utf-8",
    )

    broken, self_links, checked = check_links(tmp_path)

    assert checked == 4
    assert broken == []
    assert self_links == []


def test_check_links_ignores_external_anchor_mailto_obsidian_and_images(tmp_path: Path):
    page = tmp_path / "a.md"
    page.write_text(
        "\n".join(
            [
                "[Web](https://example.com/missing.md)",
                "[Mail](mailto:test@example.com)",
                "[App](obsidian://open?vault=x)",
                "[Anchor](#local)",
                "![Image](missing.png)",
            ]
        ),
        encoding="utf-8",
    )

    broken, self_links, checked = check_links(tmp_path)

    assert checked == 0
    assert broken == []
    assert self_links == []
