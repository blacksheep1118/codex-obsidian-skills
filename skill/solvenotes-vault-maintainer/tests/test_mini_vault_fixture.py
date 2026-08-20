from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import BUNDLED_TEST_VAULT, configure_test_vault

SKILL_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = SKILL_ROOT / "fixtures" / "solvenotes-mini-vault"
CASE_ROOT = SKILL_ROOT / "fixtures" / "solvenotes-mini-vault-cases"


def test_test_vault_defaults_to_bundled_fixture() -> None:
    env: dict[str, str] = {}

    assert configure_test_vault(env) == BUNDLED_TEST_VAULT
    assert env["SOLVENOTES_VAULT_ROOT"] == str(BUNDLED_TEST_VAULT)


def test_test_vault_honors_explicit_override(tmp_path: Path) -> None:
    env = {"SOLVENOTES_VAULT_ROOT": str(tmp_path)}

    assert configure_test_vault(env) == tmp_path
    assert env["SOLVENOTES_VAULT_ROOT"] == str(tmp_path)


def run_script(script: str, *args: str, root: Path = FIXTURE_ROOT) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["SOLVENOTES_VAULT_ROOT"] = str(root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(SKILL_ROOT / "scripts"),
            str(SKILL_ROOT.parent / "algorithm-job-notes-for-obsidian" / "scripts"),
            env.get("PYTHONPATH", ""),
        ]
    )
    script_root = SKILL_ROOT / "scripts"
    if script == "check_cpp_examples.py":
        script_root = SKILL_ROOT.parent / "algorithm-job-notes-for-obsidian" / "scripts"
    return subprocess.run(
        [sys.executable, str(script_root / script), *args],
        cwd=SKILL_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_mini_vault_fixture_covers_maintainer_contract() -> None:
    required = {
        "AGENT.md",
        "00_学习地图.md",
        "课程/00_课程总览.md",
        "课程/source_manifest.md",
        "论文/01_论文.md",
        "算法岗学习笔记/00_算法岗学习地图.md",
        "算法岗学习笔记/49_数据结构与算法_复杂度与高频范式.md",
        "算法岗学习笔记/108_C++17算法面试_STL与边界.md",
        "算法岗学习笔记/115_算法训练_对拍错题复做与模拟面试.md",
        "算法岗学习笔记/116_机器学习与深度学习手写题_NumPy_PyTorch与数值稳定.md",
        ".obsidian/templates/concept.md",
    }
    actual = {path.relative_to(FIXTURE_ROOT).as_posix() for path in FIXTURE_ROOT.rglob("*") if path.is_file()}
    assert required <= actual
    assert "bad-link.md" in {path.name for path in CASE_ROOT.iterdir()}
    assert "naturalness.md" in {path.name for path in CASE_ROOT.iterdir()}


@pytest.mark.parametrize(
    ("script", "args"),
    [
        ("check_algorithm_job_notes.py", ("--root", str(FIXTURE_ROOT))),
        ("check_cpp_examples.py", ("--root", str(FIXTURE_ROOT))),
        ("check_python_examples.py", ("--root", str(FIXTURE_ROOT))),
        ("check_frontmatter.py", ()),
        ("check_links.py", ()),
        ("check_naturalness.py", ("--strict",)),
    ],
)
def test_mini_vault_offline_checks(script: str, args: tuple[str, ...]) -> None:
    result = run_script(script, *args)
    assert result.returncode == 0, result.stdout + result.stderr


def test_negative_fixtures_are_detected(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "AGENT.md").write_text((FIXTURE_ROOT / "AGENT.md").read_text(encoding="utf-8"), encoding="utf-8")
    shutil.copy2(CASE_ROOT / "bad-link.md", root / "bad-link.md")
    result = run_script("check_links.py", root=root)
    assert result.returncode != 0
    assert "broken_links 1" in result.stdout

    (root / "bad-link.md").unlink()
    shutil.copy2(CASE_ROOT / "naturalness.md", root / "naturalness.md")
    result = run_script("check_naturalness.py", "--strict", root=root)
    assert result.returncode != 0
    assert "exact_paragraph_repeat" in result.stdout
