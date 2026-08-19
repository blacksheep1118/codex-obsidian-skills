from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_repo_hygiene  # noqa: E402
from install_ignore import GITIGNORE_PATTERNS, should_ignore_relative  # noqa: E402


SUBPROCESS_TIMEOUT_SECONDS = 60


def run_script(
    *args: str,
    cwd: Path = ROOT,
    check: bool = True,
    timeout: int = SUBPROCESS_TIMEOUT_SECONDS,
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


def make_hygiene_root(tmp_path: Path, kind: str) -> Path:
    regular_dir = tmp_path / "regular-root"
    regular_dir.mkdir(exist_ok=True)
    if kind == "regular-dir":
        return regular_dir
    if kind == "missing":
        return tmp_path / "missing-root"
    regular_file = tmp_path / "root.txt"
    regular_file.write_text("fixture\n", encoding="utf-8")
    if kind == "file":
        return regular_file
    alias = tmp_path / f"{kind}-root"
    if kind == "symlink-dir":
        alias.symlink_to(regular_dir, target_is_directory=True)
    elif kind == "symlink-file":
        alias.symlink_to(regular_file)
    elif kind == "broken-symlink":
        alias.symlink_to(tmp_path / "missing-target")
    else:
        raise AssertionError(kind)
    return alias


@pytest.mark.parametrize(
    "kind",
    ("missing", "file", "symlink-dir", "symlink-file", "broken-symlink"),
)
@pytest.mark.parametrize("scan_worktree", (False, True), ids=("default", "scan-worktree"))
def test_repo_hygiene_cli_rejects_invalid_root_shapes(
    tmp_path: Path,
    kind: str,
    scan_worktree: bool,
) -> None:
    root = make_hygiene_root(tmp_path, kind)
    arguments = ["scripts/check_repo_hygiene.py", "--root", str(root)]
    if scan_worktree:
        arguments.append("--scan-worktree")

    result = run_script(*arguments, check=False)

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == (
        f"ERROR: {root}: root must be an existing directory without symlink components\n"
    )
    assert "Traceback" not in result.stderr


def test_repo_hygiene_api_rejects_symlink_root_and_accepts_regular_directory(
    tmp_path: Path,
) -> None:
    regular = make_hygiene_root(tmp_path, "regular-dir")
    alias = make_hygiene_root(tmp_path, "symlink-dir")

    assert check_repo_hygiene.validate_root(regular) == regular
    with pytest.raises(check_repo_hygiene.RepoHygieneRootError) as caught:
        check_repo_hygiene.validate_root(alias)
    assert str(caught.value) == (
        f"{alias}: root must be an existing directory without symlink components"
    )


def test_repo_hygiene_keeps_valid_non_git_directory_semantics(tmp_path: Path) -> None:
    root = make_hygiene_root(tmp_path, "regular-dir")

    result = run_script("scripts/check_repo_hygiene.py", "--root", str(root))

    assert result.returncode == 0
    assert "is not a Git repository" in result.stderr
    assert result.stdout == "repo_hygiene ok workspace_scan=clean\n"


def test_repo_hygiene_accepts_current_tracked_files():
    result = run_script("scripts/check_repo_hygiene.py")

    assert "repo_hygiene ok" in result.stdout


def test_gitignore_blocks_common_repository_junk():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in GITIGNORE_PATTERNS:
        assert pattern in text


def test_repo_hygiene_and_install_ignore_share_rules():
    sample_paths = [
        ".git/config",
        "__MACOSX/._file",
        ".DS_Store",
        "._README.md",
        ".pytest_cache/v/cache/nodeids",
        ".ruff_cache/content",
        "pkg/__pycache__/module.pyc",
        "pkg/module.pyc",
        "build/artifact.txt",
        "converted_pptx/deck.pptx",
        "dist/archive.whl",
        "package.egg-info/PKG-INFO",
        "tmp/output.txt",
        ".tmp/output.txt",
        "test-output/result.txt",
        "scratch.tmp",
        "debug.log",
    ]

    for path in sample_paths:
        assert should_ignore_relative(Path(path)), path
        assert check_repo_hygiene.is_forbidden(path), path


def test_ci_runs_repo_hygiene_and_root_pytest():
    workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")

    assert "python scripts/check_repo_hygiene.py" in workflow
    assert "python -m pytest -q" in workflow
    assert 'PYTEST_DISABLE_PLUGIN_AUTOLOAD: "1"' in workflow
    assert "matrix.skill" in workflow
    assert "python -m pip install -r skill/${{ matrix.skill }}/requirements-dev.txt" in workflow
    assert "working-directory: skill/${{ matrix.skill }}" in workflow
    assert "glob('*/requirements-dev.txt')" not in workflow


def test_repo_hygiene_reports_tracked_junk_files(tmp_path: Path):
    if shutil.which("git") is None:
        return

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    (repo / "README.md").write_text("# Repo\n", encoding="utf-8")
    (repo / ".DS_Store").write_text("junk\n", encoding="utf-8")
    (repo / "._README.md").write_text("junk\n", encoding="utf-8")
    (repo / "debug.log").write_text("junk\n", encoding="utf-8")
    (repo / "scratch.tmp").write_text("junk\n", encoding="utf-8")
    (repo / "pkg" / "__pycache__").mkdir(parents=True)
    (repo / "pkg" / "__pycache__" / "module.pyc").write_bytes(b"\0")
    (repo / "build").mkdir()
    (repo / "build" / "artifact.txt").write_text("junk\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "."],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )

    result = run_script("scripts/check_repo_hygiene.py", "--root", str(repo), check=False)
    output = result.stdout + result.stderr

    assert result.returncode == 1
    assert "repo_hygiene failed" in output
    assert ".DS_Store" in output
    assert "._README.md" in output
    assert "debug.log" in output
    assert "scratch.tmp" in output
    assert "__pycache__" in output
    assert "build/artifact.txt" in output


def test_repo_hygiene_scan_worktree_reports_untracked_junk(tmp_path: Path):
    if shutil.which("git") is None:
        return

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    (repo / "README.md").write_text("# Repo\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    (repo / "debug.log").write_text("junk\n", encoding="utf-8")
    (repo / "scratch.tmp").write_text("junk\n", encoding="utf-8")

    default_result = run_script("scripts/check_repo_hygiene.py", "--root", str(repo))
    assert default_result.returncode == 0
    assert "repo_hygiene ok" in default_result.stdout

    scan_result = run_script("scripts/check_repo_hygiene.py", "--root", str(repo), "--scan-worktree", check=False)
    output = scan_result.stdout + scan_result.stderr

    assert scan_result.returncode == 1
    assert "repo_hygiene failed" in output
    assert "debug.log" in output
    assert "scratch.tmp" in output


def test_root_pytest_collects_only_root_tests():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=True,
    )

    collected = result.stdout.replace("\\", "/")
    assert "tests/test_repo_hygiene.py::test_root_pytest_collects_only_root_tests" in collected
    assert "skill/" not in collected
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD" not in result.stderr
