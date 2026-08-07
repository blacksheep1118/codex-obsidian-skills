from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from install_skill import copy_skill  # noqa: E402
from install_ignore import should_ignore_relative  # noqa: E402
import validate_all  # noqa: E402


SUBPROCESS_TIMEOUT_SECONDS = 60


def run_script(
    *args: str,
    cwd: Path = ROOT,
    timeout: int = SUBPROCESS_TIMEOUT_SECONDS,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=check,
        timeout=timeout,
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
    assert "stale=1" in dry_run.stdout
    assert "DRY-RUN stale stale.txt" in dry_run.stdout
    assert stale.exists()

    update = run_script("scripts/update_installed_skills.py", "--all", "--destination", str(destination), "--prune", "--self-check")
    assert "install_self_check ok skills=4" in update.stdout
    assert not stale.exists()

    self_check = run_script("scripts/install_skill.py", "--all", "--destination", str(destination), "--self-check-only")
    assert "install_self_check ok skills=4" in self_check.stdout


def test_update_dry_run_self_check_requires_installed_copy(tmp_path: Path):
    destination = tmp_path / "missing-skills"
    skill_name = "ppt-to-md-for-obsidian"

    plain_dry_run = run_script(
        "scripts/update_installed_skills.py",
        "--skill",
        skill_name,
        "--destination",
        str(destination),
        "--dry-run",
    )
    assert plain_dry_run.returncode == 0

    checked_dry_run = run_script(
        "scripts/update_installed_skills.py",
        "--skill",
        skill_name,
        "--destination",
        str(destination),
        "--dry-run",
        "--self-check",
        check=False,
    )
    assert checked_dry_run.returncode != 0
    assert "source_self_check ok skills=1" in checked_dry_run.stdout
    assert "not installed" in checked_dry_run.stderr


def test_update_dry_run_self_check_rejects_broken_installed_metadata(tmp_path: Path):
    destination = tmp_path / "skills"
    skill_name = "ppt-to-md-for-obsidian"
    run_script(
        "scripts/install_skill.py",
        "--skill",
        skill_name,
        "--destination",
        str(destination),
    )
    openai_yaml = destination / skill_name / "agents" / "openai.yaml"
    valid_lines = openai_yaml.read_text(encoding="utf-8").splitlines()
    openai_yaml.write_text(
        "\n".join(line for line in valid_lines if "default_prompt:" not in line) + "\n",
        encoding="utf-8",
    )

    result = run_script(
        "scripts/update_installed_skills.py",
        "--skill",
        skill_name,
        "--destination",
        str(destination),
        "--dry-run",
        "--self-check",
        check=False,
    )

    assert result.returncode != 0
    assert "source_self_check ok skills=1" in result.stdout
    assert "missing default_prompt:" in result.stderr


def test_update_dry_run_self_check_validates_source_and_installed_copy(tmp_path: Path):
    destination = tmp_path / "skills"
    skill_name = "ppt-to-md-for-obsidian"
    run_script(
        "scripts/install_skill.py",
        "--skill",
        skill_name,
        "--destination",
        str(destination),
    )

    result = run_script(
        "scripts/update_installed_skills.py",
        "--skill",
        skill_name,
        "--destination",
        str(destination),
        "--dry-run",
        "--self-check",
    )

    assert "source_self_check ok skills=1" in result.stdout
    assert "install_self_check ok skills=1" in result.stdout


@pytest.mark.parametrize("dangling", [False, True])
def test_install_rejects_existing_or_dangling_skill_symlink(tmp_path: Path, dangling: bool):
    destination = tmp_path / "skills"
    destination.mkdir()
    skill_name = "ppt-to-md-for-obsidian"
    target = tmp_path / ("missing-target" if dangling else "outside")
    if not dangling:
        target.mkdir()
    (destination / skill_name).symlink_to(target, target_is_directory=True)

    result = run_script(
        "scripts/install_skill.py",
        "--skill",
        skill_name,
        "--destination",
        str(destination),
        check=False,
    )

    assert result.returncode != 0
    assert "symlink" in result.stderr.lower()
    assert (destination / skill_name).is_symlink()
    assert not (target / "SKILL.md").exists()


def test_install_rejects_symlink_destination_root(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    destination = tmp_path / "skills-link"
    destination.symlink_to(outside, target_is_directory=True)

    result = run_script(
        "scripts/install_skill.py",
        "--skill",
        "ppt-to-md-for-obsidian",
        "--destination",
        str(destination),
        check=False,
    )

    assert result.returncode != 0
    assert "symlink" in result.stderr.lower()
    assert list(outside.iterdir()) == []


def test_update_prune_rejects_internal_symlink_before_copying(tmp_path: Path):
    destination = tmp_path / "skills"
    skill_name = "ppt-to-md-for-obsidian"
    run_script(
        "scripts/install_skill.py",
        "--skill",
        skill_name,
        "--destination",
        str(destination),
    )
    installed = destination / skill_name
    local_skill_text = "locally modified\n"
    (installed / "SKILL.md").write_text(local_skill_text, encoding="utf-8")
    outside = tmp_path / "outside"
    write_file(outside / "sentinel.txt", "keep\n")
    (installed / "stale-link").symlink_to(outside, target_is_directory=True)

    result = run_script(
        "scripts/update_installed_skills.py",
        "--skill",
        skill_name,
        "--destination",
        str(destination),
        "--prune",
        check=False,
    )

    assert result.returncode != 0
    assert "symlink" in result.stderr.lower()
    assert (installed / "SKILL.md").read_text(encoding="utf-8") == local_skill_text
    assert (outside / "sentinel.txt").read_text(encoding="utf-8") == "keep\n"


def test_validate_all_lists_stable_step_ids():
    result = run_script("scripts/validate_all.py", "--list-steps")
    steps = result.stdout.splitlines()

    for step_id in (
        "root.compile",
        "root.ruff",
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
    assert all(
        command.env == {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        for command in pytest_commands
    )


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
    assert all(command.env == {"PYTHONDONTWRITEBYTECODE": "1"} for command in pytest_commands)


def test_validate_all_quick_runs_root_tests_before_metadata_sync():
    steps = validate_all.selected_steps(validate_all.build_steps(sys.executable), quick=True, skill=None)
    step_ids = [step.step_id for step in steps]

    assert step_ids[:5] == ["root.compile", "root.ruff", "root.repo_hygiene", "root.tests", "metadata.sync"]


def test_validate_all_ruff_step_uses_root_config():
    steps = validate_all.build_steps(sys.executable)
    ruff_step = next(step for step in steps if step.step_id == "root.ruff")

    assert len(ruff_step.commands) == 1
    assert ruff_step.commands[0].cwd == ROOT
    assert ruff_step.commands[0].command == [
        sys.executable,
        "-m",
        "ruff",
        "check",
        ".",
        "--no-cache",
        "--config",
        str(ROOT / "pyproject.toml"),
    ]


def test_validate_all_timeout_reports_context(monkeypatch, capsys):
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=kwargs.get("args", args[0]), timeout=7)

    monkeypatch.setattr(validate_all.subprocess, "run", raise_timeout)

    try:
        validate_all.run_command("root.tests", [sys.executable, "-m", "pytest", "-q"], ROOT, timeout=7)
    except SystemExit as exc:
        assert exc.code == 124
    else:
        raise AssertionError("run_command should exit on timeout")

    captured = capsys.readouterr()
    assert "step: root.tests" in captured.err
    assert f"cwd: {ROOT}" in captured.err
    assert "command:" in captured.err
    assert "timeout: after 7s" in captured.err


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
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
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
