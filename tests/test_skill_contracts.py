from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skill"
SKILL_DIRS = sorted(path for path in SKILL_ROOT.iterdir() if (path / "SKILL.md").exists())
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def test_all_skills_have_output_contracts_and_validation():
    assert len(SKILL_DIRS) == 4

    for skill_dir in SKILL_DIRS:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

        assert "## Quick Start" in text, skill_dir.name
        assert "## Evidence And Assumption Gate" in text, skill_dir.name
        assert "## Output Contract" in text, skill_dir.name
        assert "final response" in text.lower(), skill_dir.name
        assert "Validate before finishing" in text, skill_dir.name
        assert "`scripts/" in text, skill_dir.name
        assert "`references/" in text, skill_dir.name


def test_skill_frontmatter_is_trigger_oriented():
    for skill_dir in SKILL_DIRS:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        assert match, skill_dir.name

        frontmatter = match.group(1)
        assert f"name: {skill_dir.name}" in frontmatter, skill_dir.name
        assert "description:" in frontmatter, skill_dir.name
        assert "Use when" in frontmatter, skill_dir.name


def test_skills_keep_progressive_disclosure_links_close_to_workflow():
    for skill_dir in SKILL_DIRS:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

        quick_start_index = text.index("## Quick Start")
        output_contract_index = text.index("## Output Contract")

        assert quick_start_index < output_contract_index, skill_dir.name
        assert "## Bundled Resources" in text[output_contract_index:], skill_dir.name
