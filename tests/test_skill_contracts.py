from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skill"
SKILL_DIRS = sorted(path for path in SKILL_ROOT.iterdir() if (path / "SKILL.md").exists())
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
ROUTING_EXPECTATIONS = {
    "web-course-notes-for-obsidian": {
        "positive": ("URL", "webpage course", "direct PDF/PPT/transcript URL"),
        "boundary": ("$ppt-to-md-for-obsidian", "$obsidian-vault-organizer"),
    },
    "ppt-to-md-for-obsidian": {
        "positive": ("local PPT/PPTX/PDF", "courseware", "PPT转笔记"),
        "boundary": ("$web-course-notes-for-obsidian", "$obsidian-vault-organizer"),
    },
    "obsidian-vault-organizer": {
        "positive": ("existing Obsidian vault", "broken-link repair", "vault整理"),
        "boundary": ("$ppt-to-md-for-obsidian", "$web-course-notes-for-obsidian", "$notes-to-scientific-ppt"),
    },
    "notes-to-scientific-ppt": {
        "positive": ("existing Markdown/Obsidian notes", "scientific PPTX deck", "科研严谨风PPT"),
        "boundary": ("$web-course-notes-for-obsidian", "$ppt-to-md-for-obsidian", "$obsidian-vault-organizer"),
    },
}


def load_frontmatter(skill_dir: Path) -> dict:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    assert match, skill_dir.name
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


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
        assert "## Handoff Boundaries" in text, skill_dir.name


def test_skill_frontmatter_is_trigger_oriented():
    for skill_dir in SKILL_DIRS:
        metadata = load_frontmatter(skill_dir)
        description = metadata["description"]
        expectations = ROUTING_EXPECTATIONS[skill_dir.name]

        assert metadata["name"] == skill_dir.name
        assert description.startswith("Use when"), skill_dir.name
        assert all(token in description for token in expectations["positive"]), skill_dir.name
        assert any(boundary in description for boundary in expectations["boundary"]), skill_dir.name
        assert "Use $" in description, skill_dir.name


def test_readme_links_routing_guide():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    routing = ROOT / "docs" / "routing.md"

    assert routing.exists()
    assert "[Skill Routing](docs/routing.md)" in readme or "[Skill routing](docs/routing.md)" in readme


def test_skill_dev_requirements_are_independent():
    for skill_dir in SKILL_DIRS:
        if not (skill_dir / "tests").exists():
            continue
        dev_requirements = skill_dir / "requirements-dev.txt"
        assert dev_requirements.exists(), skill_dir.name

        lines = [
            line.strip()
            for line in dev_requirements.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert any(line.startswith("pytest") for line in lines), skill_dir.name

        if (skill_dir / "requirements.txt").exists():
            assert "-r requirements.txt" in lines, skill_dir.name


def test_skills_keep_progressive_disclosure_links_close_to_workflow():
    for skill_dir in SKILL_DIRS:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

        quick_start_index = text.index("## Quick Start")
        output_contract_index = text.index("## Output Contract")

        assert quick_start_index < output_contract_index, skill_dir.name
        assert "## Bundled Resources" in text[output_contract_index:], skill_dir.name


def test_project_specific_rules_live_in_references_not_main_skill_files():
    profile_skills = {
        "ppt-to-md-for-obsidian": (
            220,
            ("check_all_notes.py", "check_examples.py", ".obsidian/workspace.json"),
        ),
        "obsidian-vault-organizer": (
            180,
            ("check_all_notes.py", "check_frontmatter.py", "99_质量审查/"),
        ),
    }

    for skill_name, (max_main_lines, private_markers) in profile_skills.items():
        skill_dir = SKILL_ROOT / skill_name
        main_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        profile_text = (skill_dir / "references" / "solvenotes-profile.md").read_text(encoding="utf-8")

        assert "`references/solvenotes-profile.md`" in main_text
        assert len(main_text.splitlines()) <= max_main_lines, skill_name
        assert len(profile_text.splitlines()) >= 30, skill_name
        for marker in private_markers:
            assert marker not in main_text, (skill_name, marker)
            assert marker in profile_text, (skill_name, marker)
