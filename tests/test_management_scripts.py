from __future__ import annotations

from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from install_skill import copy_skill  # noqa: E402
from install_ignore import should_ignore_relative  # noqa: E402
import install_skill  # noqa: E402
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
    assert "interface.default_prompt must be a non-empty string" in result.stderr


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


@pytest.mark.parametrize("dangling", [False, True])
def test_install_rejects_destination_ancestor_symlink(tmp_path: Path, dangling: bool):
    outside = tmp_path / "missing-outside" if dangling else tmp_path / "outside"
    if not dangling:
        outside.mkdir()
    ancestor = tmp_path / "linked-ancestor"
    ancestor.symlink_to(outside, target_is_directory=True)
    destination = ancestor / "nested" / "skills"

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
    assert ancestor.is_symlink()
    if dangling:
        assert not outside.exists()
    else:
        assert list(outside.iterdir()) == []


@pytest.mark.parametrize("link_location", ["root", "file", "directory"])
def test_copy_skill_rejects_source_symlinks(tmp_path: Path, link_location: str):
    real_source = tmp_path / "real-source"
    write_file(real_source / "SKILL.md", "---\nname: fake-skill\ndescription: Use when testing.\n---\n")
    destination = tmp_path / "destination"
    if link_location == "root":
        source = tmp_path / "source-link"
        source.symlink_to(real_source, target_is_directory=True)
    else:
        source = real_source
        outside = tmp_path / "outside"
        if link_location == "file":
            write_file(outside / "secret.txt", "outside\n")
            (source / "secret.txt").symlink_to(outside / "secret.txt")
        else:
            outside.mkdir()
            write_file(outside / "secret.txt", "outside\n")
            (source / "linked-dir").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="source symlink"):
        copy_skill(source, destination, dry_run=False)

    assert not destination.exists()


def test_copy_skill_does_not_follow_source_file_swapped_after_scan(monkeypatch, tmp_path: Path):
    if not install_skill._supports_dir_fd():
        pytest.skip("directory-relative file operations are unavailable")
    source = tmp_path / "source" / "fake-skill"
    destination = tmp_path / "destination" / "fake-skill"
    write_file(source / "SKILL.md", "---\nname: fake-skill\ndescription: Use when testing.\n---\n")
    outside = tmp_path / "outside.txt"
    outside.write_text("OUTSIDE_SECRET\n", encoding="utf-8")
    original_copy = install_skill._copy_regular_file_at
    swapped = False

    def swap_then_copy(source_root_fd: int, destination_root_fd: int, relative: Path) -> None:
        nonlocal swapped
        if not swapped:
            attacked = source / relative
            attacked.unlink()
            attacked.symlink_to(outside)
            swapped = True
        original_copy(source_root_fd, destination_root_fd, relative)

    monkeypatch.setattr(install_skill, "_copy_regular_file_at", swap_then_copy)

    with pytest.raises(ValueError, match="source symlink"):
        copy_skill(source, destination, dry_run=False)

    copied_regular_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in destination.rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    assert "OUTSIDE_SECRET" not in copied_regular_text


def test_copy_skill_does_not_write_through_destination_ancestor_swapped_after_open(
    monkeypatch,
    tmp_path: Path,
):
    if not install_skill._supports_dir_fd():
        pytest.skip("directory-relative file operations are unavailable")
    source = tmp_path / "source" / "fake-skill"
    write_file(source / "SKILL.md", "---\nname: fake-skill\ndescription: Use when testing.\n---\n")
    ancestor = tmp_path / "destination-ancestor"
    ancestor.mkdir()
    destination = ancestor / "nested" / "fake-skill"
    detached = tmp_path / "detached-destination"
    outside = tmp_path / "outside"
    outside.mkdir()
    original_copy = install_skill._copy_regular_file_at
    swapped = False

    def swap_then_copy(source_root_fd: int, destination_root_fd: int, relative: Path) -> None:
        nonlocal swapped
        if not swapped:
            ancestor.rename(detached)
            ancestor.symlink_to(outside, target_is_directory=True)
            swapped = True
        original_copy(source_root_fd, destination_root_fd, relative)

    monkeypatch.setattr(install_skill, "_copy_regular_file_at", swap_then_copy)

    with pytest.raises(ValueError, match="destination root or ancestor changed"):
        copy_skill(source, destination, dry_run=False)

    assert list(outside.rglob("*")) == []


def test_installer_rejects_non_whitelisted_top_level_symlink(monkeypatch):
    original_lstat = Path.lstat

    def fake_lstat(path: Path):
        if path == Path("/untrusted"):
            return SimpleNamespace(st_mode=stat.S_IFLNK)
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)

    with pytest.raises(ValueError, match="untrusted top-level"):
        install_skill._absolute_with_platform_alias(Path("/untrusted/skills"))


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


def test_validate_all_pytest_steps_disable_external_plugin_autoload(monkeypatch, tmp_path: Path):
    monkeypatch.delenv(validate_all.PYTEST_PLUGIN_AUTOLOAD_OVERRIDE, raising=False)

    steps = validate_all.build_steps(sys.executable, tmp_path)
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


def test_validate_all_pytest_plugin_autoload_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv(validate_all.PYTEST_PLUGIN_AUTOLOAD_OVERRIDE, "1")

    steps = validate_all.build_steps(sys.executable, tmp_path)
    pytest_commands = [
        command
        for step in steps
        for command in step.commands
        if command.command[:3] == [sys.executable, "-m", "pytest"]
    ]

    assert pytest_commands
    assert all(command.env == {"PYTHONDONTWRITEBYTECODE": "1"} for command in pytest_commands)


def test_validate_all_quick_runs_root_tests_before_metadata_sync(tmp_path: Path):
    steps = validate_all.selected_steps(validate_all.build_steps(sys.executable, tmp_path), quick=True, skill=None)
    step_ids = [step.step_id for step in steps]

    assert step_ids[:5] == ["root.compile", "root.ruff", "root.repo_hygiene", "root.tests", "metadata.sync"]


def test_validate_all_ruff_step_uses_root_config(tmp_path: Path):
    steps = validate_all.build_steps(sys.executable, tmp_path)
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


def test_validate_all_skill_alias_selects_same_steps_as_full_name(tmp_path: Path):
    steps = validate_all.build_steps(sys.executable, tmp_path)

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


def test_non_pruning_copy_retains_local_ignored_artifacts_and_dry_run_matches(
    tmp_path: Path,
    capsys,
):
    source = tmp_path / "source" / "fake-skill"
    destination = tmp_path / "dest" / "fake-skill"
    write_file(source / "SKILL.md", "---\nname: fake-skill\ndescription: Use when testing.\n---\n")
    copy_skill(source, destination, dry_run=False)
    ignored = destination / "local.log"
    write_file(ignored, "local artifact\n")

    copy_skill(source, destination, dry_run=True)
    dry_run = capsys.readouterr().out
    copy_skill(source, destination, dry_run=False)

    assert "stale=0" in dry_run
    assert "prune not requested" in dry_run
    assert ignored.read_text(encoding="utf-8") == "local artifact\n"


def test_prune_dry_run_reports_ignored_artifact_removed_by_real_prune(tmp_path: Path, capsys):
    source = tmp_path / "source" / "fake-skill"
    destination = tmp_path / "dest" / "fake-skill"
    write_file(source / "SKILL.md", "---\nname: fake-skill\ndescription: Use when testing.\n---\n")
    copy_skill(source, destination, dry_run=False)
    ignored = destination / "local.log"
    write_file(ignored, "local artifact\n")

    copy_skill(source, destination, dry_run=True, prune=True)
    dry_run = capsys.readouterr().out

    assert "stale=0" in dry_run
    assert "DRY-RUN prune stale files" in dry_run
    assert "DRY-RUN remove local.log" in dry_run
    assert ignored.exists()

    copy_skill(source, destination, dry_run=False, prune=True)
    assert not ignored.exists()


def test_validate_all_uses_and_cleans_per_run_temporary_directory(monkeypatch, tmp_path: Path):
    temporary = tmp_path / "validation-run"
    events: list[str] = []

    class TrackedTemporaryDirectory:
        def __init__(self, prefix: str):
            assert prefix == "codex-obsidian-skills-validate-"

        def __enter__(self) -> str:
            temporary.mkdir()
            events.append("enter")
            return str(temporary)

        def __exit__(self, exc_type, exc, traceback) -> None:
            events.append("exit")
            temporary.rmdir()

    monkeypatch.setattr(validate_all.tempfile, "TemporaryDirectory", TrackedTemporaryDirectory)

    assert validate_all.main(["--list-steps"]) == 0
    assert events == ["enter", "exit"]
    assert not temporary.exists()
