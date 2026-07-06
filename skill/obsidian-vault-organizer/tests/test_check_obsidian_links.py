from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_obsidian_links import check_links


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
