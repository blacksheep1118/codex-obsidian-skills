from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


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


def test_shared_link_checker_rejects_markdown_symlink_outside_root(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    try:
        (vault / "linked.md").symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    result = subprocess.run(
        [sys.executable, "scripts/check_obsidian_links.py", str(vault)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    assert result.returncode == 1
    assert "OUTSIDE_ROOT" in result.stdout


def test_shared_link_checker_keeps_list_continuations_but_masks_top_level_code(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text(
        "    [hidden](hidden.md)\n\n- Body item\n    [visible](visible.md)\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "scripts/check_obsidian_links.py", str(vault)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    assert result.returncode == 1
    assert "checked_links 1" in result.stdout
    assert "visible.md" in result.stdout
    assert "hidden.md" not in result.stdout
