from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from install_skill import copy_skill  # noqa: E402
from install_ignore import should_ignore_relative  # noqa: E402
import validate_all  # noqa: E402


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


def write_file(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def assert_no_install_junk(root: Path) -> None:
    offenders = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if should_ignore_relative(relative):
            offenders.append(relative.as_posix())
    assert offenders == []


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


def test_validate_all_lists_stable_step_ids():
    result = run_script("scripts/validate_all.py", "--list-steps")
    steps = result.stdout.splitlines()

    for step_id in (
        "root.compile",
        "root.tests",
        "root.repo_hygiene",
        "metadata.sync",
        "ppt.tests",
        "ppt.validator",
        "ppt.pipeline",
        "web.tests",
        "web.validator",
        "vault.tests",
        "vault.validator",
        "notes.tests",
        "notes.validator",
        "notes.deck",
    ):
        assert step_id in steps


def test_validate_all_pytest_steps_disable_external_plugin_autoload(monkeypatch):
    monkeypatch.delenv(validate_all.PYTEST_PLUGIN_AUTOLOAD_OVERRIDE, raising=False)

    steps = validate_all.build_steps(sys.executable)
    pytest_commands = [
        command
        for step in steps
        for command in step.commands
        if command.command[:3] == [sys.executable, "-m", "pytest"]
    ]

    assert {command.command[3] for command in pytest_commands} == {"-q"}
    assert pytest_commands
    assert all(command.env == {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"} for command in pytest_commands)


def test_validate_all_pytest_plugin_autoload_override(monkeypatch):
    monkeypatch.setenv(validate_all.PYTEST_PLUGIN_AUTOLOAD_OVERRIDE, "1")

    steps = validate_all.build_steps(sys.executable)
    pytest_commands = [
        command
        for step in steps
        for command in step.commands
        if command.command[:3] == [sys.executable, "-m", "pytest"]
    ]

    assert pytest_commands
    assert all(command.env == {} for command in pytest_commands)


def test_validate_all_skill_alias_selects_same_steps_as_full_name():
    steps = validate_all.build_steps(sys.executable)

    alias_steps = [step.step_id for step in validate_all.selected_steps(steps, quick=False, skill="notes")]
    full_name_steps = [
        step.step_id
        for step in validate_all.selected_steps(steps, quick=False, skill="notes-to-scientific-ppt")
    ]

    assert alias_steps == full_name_steps
    assert alias_steps == ["notes.compile", "notes.tests", "notes.validator", "notes.deck"]


def test_validate_all_unknown_skill_lists_full_names_and_aliases():
    result = subprocess.run(
        [sys.executable, "scripts/validate_all.py", "--skill", "notez", "--list-steps"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "unknown skill: notez" in result.stderr
    assert "notes-to-scientific-ppt (notes)" in result.stderr
    assert "web-course-notes-for-obsidian (web)" in result.stderr
    assert "ppt-to-md-for-obsidian (ppt)" in result.stderr
    assert "obsidian-vault-organizer (vault)" in result.stderr


def test_install_copy_ignores_and_prunes_repository_junk(tmp_path: Path):
    source = tmp_path / "source" / "fake-skill"
    destination = tmp_path / "dest" / "fake-skill"

    write_file(source / "SKILL.md", "---\nname: fake-skill\ndescription: Use when testing.\n---\n")
    write_file(source / "scripts" / "tool.py", "print('ok')\n")
    write_file(source / ".DS_Store")
    write_file(source / "._SKILL.md")
    write_file(source / "__pycache__" / "tool.pyc")
    write_file(source / ".pytest_cache" / "v" / "cache" / "nodeids")
    write_file(source / ".ruff_cache" / "content")
    write_file(source / "__MACOSX" / "._SKILL.md")
    write_file(source / "build" / "artifact.txt")
    write_file(source / "converted_pptx" / "deck.pptx")
    write_file(source / "dist" / "archive.whl")
    write_file(source / "fake.egg-info" / "PKG-INFO")
    write_file(source / ".git" / "config")
    write_file(source / "tmp" / "output.txt")
    write_file(source / ".tmp" / "output.txt")
    write_file(source / "test-output" / "result.txt")
    write_file(source / "debug.log")
    write_file(source / "scratch.tmp")

    copy_skill(source, destination, dry_run=False)

    assert (destination / "SKILL.md").exists()
    assert (destination / "scripts" / "tool.py").exists()
    assert not (destination / "debug.log").exists()
    assert not (destination / "scratch.tmp").exists()
    assert_no_install_junk(destination)

    write_file(destination / ".DS_Store")
    write_file(destination / "._old")
    write_file(destination / "__pycache__" / "old.pyc")
    write_file(destination / ".pytest_cache" / "old")
    write_file(destination / "build" / "old.txt")
    write_file(destination / "tmp" / "old.txt")
    write_file(destination / "test-output" / "old.txt")
    write_file(destination / "old.log")
    write_file(destination / "old.tmp")
    write_file(destination / "stale.txt")

    copy_skill(source, destination, dry_run=False, prune=True)

    assert (destination / "SKILL.md").exists()
    assert (destination / "scripts" / "tool.py").exists()
    assert not (destination / "stale.txt").exists()
    assert_no_install_junk(destination)
