from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


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
    "algorithm-job-notes-for-obsidian": {
        "positive": ("algorithm-job learning notes", "internship or recruiting maps", "nine directions"),
        "boundary": ("$obsidian-vault-organizer", "$ppt-to-md-for-obsidian"),
    },
    "solvenotes-vault-maintainer": {
        "positive": ("repository-wide validation", "clean export packaging", "source-manifest checks"),
        "boundary": ("$obsidian-vault-organizer", "$algorithm-job-notes-for-obsidian"),
    },
}
FORBIDDEN_SKILL_AUXILIARY_FILES = {
    "readme.md",
    "installation_guide.md",
    "quick_reference.md",
    "changelog.md",
}


def test_root_command_reference_uses_supported_notes_to_ppt_mode(tmp_path: Path):
    command_reference = (ROOT / "docs" / "skill-command-reference.md").read_text(
        encoding="utf-8"
    )

    assert "--mode paper-reading" in command_reference
    assert "--mode paper-defense" not in command_reference
    assert "scripts/extract_legacy_ppt_text.py" in command_reference
    assert "--brief deck-brief.md" not in command_reference
    assert "scientific-deck.pptx \\\n  --json" not in command_reference

    note = tmp_path / "note.md"
    output = tmp_path / "deck-brief.md"
    note.write_text("# Paper\n\n## Method\n\nEvidence.\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "skill"
                / "notes-to-scientific-ppt"
                / "scripts"
                / "outline_note_deck.py"
            ),
            str(note),
            "--mode",
            "paper-reading",
            "--out",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert output.is_file()
    assert "Deck Mode: paper-reading" in output.read_text(encoding="utf-8")


def test_ppt_skill_generated_example_marker_matches_checker_contract():
    skill_text = (
        SKILL_ROOT / "ppt-to-md-for-obsidian" / "SKILL.md"
    ).read_text(encoding="utf-8")
    checker_text = (
        SKILL_ROOT
        / "ppt-to-md-for-obsidian"
        / "scripts"
        / "check_source_coverage.py"
    ).read_text(encoding="utf-8")
    match = re.search(r'^GENERATED_MARKER = "([^"]+)"$', checker_text, re.M)

    assert match is not None
    assert f"`{match.group(1)}`" in skill_text


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
    assert len(SKILL_DIRS) == 6

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


def test_skill_packages_exclude_forbidden_auxiliary_documentation():
    for skill_dir in SKILL_DIRS:
        present = {
            path.name.casefold()
            for path in skill_dir.rglob("*")
            if path.is_file()
        }
        assert not present & FORBIDDEN_SKILL_AUXILIARY_FILES, skill_dir.name


def test_long_skill_references_have_top_contents_with_live_heading_anchors():
    for reference in SKILL_ROOT.glob("*/references/*.md"):
        lines = reference.read_text(encoding="utf-8").splitlines()
        if len(lines) <= 100:
            continue

        contents_index = lines.index("## Contents")
        assert contents_index <= 12, reference
        next_heading = next(
            (index for index in range(contents_index + 1, len(lines)) if lines[index].startswith("## ")),
            len(lines),
        )
        contents = "\n".join(lines[contents_index + 1 : next_heading])
        anchors = set(re.findall(r"\]\(#([^)]+)\)", contents))
        expected = {
            heading.removeprefix("## ").strip().casefold().replace(" ", "-")
            for heading in lines[next_heading:]
            if heading.startswith("## ")
        }

        assert expected <= anchors, (reference, sorted(expected - anchors))


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
            ("check_all_notes.py", "check_frontmatter.py", "source_manifest.md"),
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
