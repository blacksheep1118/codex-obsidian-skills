from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run_script(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )


def test_install_update_and_self_check(tmp_path: Path):
    destination = tmp_path / "skills"

    install = run_script("scripts/install_skill.py", "--all", "--destination", str(destination), "--self-check")
    assert "install_self_check ok skills=4" in install.stdout
    assert (destination / "ppt-to-md-for-obsidian" / "SKILL.md").exists()
    assert (destination / "obsidian-vault-organizer" / "SKILL.md").exists()
    assert (destination / "web-course-notes-for-obsidian" / "SKILL.md").exists()
    assert (destination / "notes-to-scientific-ppt" / "SKILL.md").exists()

    stale = destination / "ppt-to-md-for-obsidian" / "stale.txt"
    stale.write_text("remove me\n", encoding="utf-8")

    dry_run = run_script("scripts/update_installed_skills.py", "--all", "--destination", str(destination), "--dry-run", "--prune")
    assert "DRY-RUN prune stale files" in dry_run.stdout
    assert stale.exists()

    update = run_script("scripts/update_installed_skills.py", "--all", "--destination", str(destination), "--prune", "--self-check")
    assert "install_self_check ok skills=4" in update.stdout
    assert not stale.exists()

    self_check = run_script("scripts/install_skill.py", "--all", "--destination", str(destination), "--self-check-only")
    assert "install_self_check ok skills=4" in self_check.stdout
