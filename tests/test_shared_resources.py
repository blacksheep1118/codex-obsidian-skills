from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_shared_resources_are_in_sync():
    result = subprocess.run(
        [sys.executable, "scripts/sync_shared_resources.py", "--check"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "shared_resource_sync ok" in result.stdout


def test_all_skills_keep_local_validator_copy():
    expected = {
        "notes-to-scientific-ppt": "scripts/validate_skill.py",
        "web-course-notes-for-obsidian": "scripts/validate_skill.py",
        "obsidian-vault-organizer": "scripts/validate_skill.py",
        "ppt-to-md-for-obsidian": "scripts/validate_skill_repo.py",
    }

    for skill_name, validator in expected.items():
        assert (ROOT / "skill" / skill_name / validator).exists(), skill_name
