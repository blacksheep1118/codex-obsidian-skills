from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run_script(*args: str, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=check,
    )


def test_repo_hygiene_accepts_current_tracked_files():
    result = run_script("scripts/check_repo_hygiene.py")

    assert "repo_hygiene ok" in result.stdout


def test_gitignore_blocks_common_repository_junk():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        "__MACOSX/",
        ".DS_Store",
        "._*",
        ".pytest_cache/",
        ".ruff_cache/",
        "__pycache__/",
        "*.pyc",
        "build/",
        "converted_pptx/",
        "dist/",
        "*.egg-info/",
        "tmp/",
        ".tmp/",
        "test-output/",
    ):
        assert pattern in text


def test_ci_runs_repo_hygiene_and_root_pytest():
    workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")

    assert "python scripts/check_repo_hygiene.py" in workflow
    assert "python -m pytest -q" in workflow
    assert "matrix.skill" in workflow
    assert "python -m pip install -r skill/${{ matrix.skill }}/requirements-dev.txt" in workflow
    assert "working-directory: skill/${{ matrix.skill }}" in workflow
    assert "glob('*/requirements-dev.txt')" not in workflow


def test_repo_hygiene_reports_tracked_junk_files(tmp_path: Path):
    if shutil.which("git") is None:
        return

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (repo / "README.md").write_text("# Repo\n", encoding="utf-8")
    (repo / ".DS_Store").write_text("junk\n", encoding="utf-8")
    (repo / "._README.md").write_text("junk\n", encoding="utf-8")
    (repo / "pkg" / "__pycache__").mkdir(parents=True)
    (repo / "pkg" / "__pycache__" / "module.pyc").write_bytes(b"\0")
    (repo / "build").mkdir()
    (repo / "build" / "artifact.txt").write_text("junk\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    result = run_script("scripts/check_repo_hygiene.py", "--root", str(repo), check=False)
    output = result.stdout + result.stderr

    assert result.returncode == 1
    assert "repo_hygiene failed" in output
    assert ".DS_Store" in output
    assert "._README.md" in output
    assert "__pycache__" in output
    assert "build/artifact.txt" in output


def test_root_pytest_collects_only_root_tests():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=True,
    )

    collected = result.stdout.replace("\\", "/")
    assert "tests/test_repo_hygiene.py::test_root_pytest_collects_only_root_tests" in collected
    assert "skill/" not in collected
