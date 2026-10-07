from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV_CHECK = ROOT / "scripts" / "dev_check.sh"
SUBPROCESS_TIMEOUT_SECONDS = 60


def installed_skill_root() -> Path:
    source_layout_root = ROOT.parents[1]
    return source_layout_root if (source_layout_root / "skill").is_dir() else ROOT.parent


def stub_git(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "git-calls.log"
    git = bin_dir / "git"
    git.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$GIT_CALL_LOG"\n',
        encoding="utf-8",
    )
    git.chmod(0o755)
    return bin_dir, log


def run_gc(tmp_path: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    bin_dir, log = stub_git(tmp_path)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["GIT_CALL_LOG"] = str(log)
    result = subprocess.run(
        ["bash", str(DEV_CHECK), "gc", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    return result, log


def test_gc_refuses_without_explicit_confirmation_and_never_calls_git(tmp_path: Path) -> None:
    result, log = run_gc(tmp_path)

    assert result.returncode == 2
    assert "--confirm-prune-now" in result.stderr
    assert not log.exists()


def test_gc_runs_only_with_explicit_confirmation(tmp_path: Path) -> None:
    result, log = run_gc(tmp_path, "--confirm-prune-now")

    assert result.returncode == 0
    expected_root = installed_skill_root()
    assert log.read_text(encoding="utf-8").splitlines() == [
        f"-C {expected_root} gc --prune=now",
        f"-C {expected_root} count-objects -vH",
    ]


def test_path_named_python_interpreter_is_resolved(tmp_path: Path) -> None:
    bin_dir, _log = stub_git(tmp_path)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["SOLVENOTES_PYTHON_BIN"] = "python3"
    result = subprocess.run(
        ["bash", str(DEV_CHECK), "gc"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )

    assert result.returncode == 2
    assert "No Python interpreter found" not in result.stderr
    assert "--confirm-prune-now" in result.stderr


def test_full_gate_guards_empty_changed_scope_arguments() -> None:
    script = DEV_CHECK.read_text(encoding="utf-8")

    assert "if ((${#changed_scope_args[@]})); then" in script
    assert "check_script check_changed_scope.py\n  fi" in script


def test_tool_and_vault_gates_are_separate_with_compatibility_aliases() -> None:
    script = DEV_CHECK.read_text(encoding="utf-8")

    assert "tool-quick" in script
    assert "tool-full" in script
    assert "vault-quick" in script
    assert "vault-full" in script
    assert "vault-runtime" in script
    assert "vault-full|full) vault_full" in script
    assert "vault-quick|quick) vault_quick" in script

    vault_section = script.split("vault_full()", 1)[1].split("vault_runtime()", 1)[0]
    assert "pytest" not in vault_section
    assert "ruff" not in vault_section
    assert "check_python_runtime_examples.py" not in vault_section

    runtime_section = script.split("vault_runtime()", 1)[1].split("github_ready()", 1)[0]
    assert "check_environment vault-runtime" in runtime_section
    assert "check_skill_lock" in runtime_section
    assert "check_python_runtime_examples.py" in runtime_section
    assert "--require-marked" in runtime_section
    assert "SOLVENOTES_RUNTIME_REVIEWED" in runtime_section
    assert "SOLVENOTES_RUNTIME_GATE_TIMEOUT:-3600" in runtime_section
    assert "SOLVENOTES_RUNTIME_EXAMPLE_TIMEOUT:-180" in runtime_section
    assert "validate_runtime_timeouts" in script
    assert "must be greater than or equal to" in script
    assert "--reviewed-local-code" in runtime_section


def test_task_temp_root_controls_caches_and_online_report() -> None:
    script = DEV_CHECK.read_text(encoding="utf-8")

    assert 'SOLVENOTES_TMP_ROOT="${SOLVENOTES_TMP_ROOT:-${TMPDIR:-/tmp}}"' in script
    assert "$SOLVENOTES_TMP_ROOT/solvenotes-pycache" in script
    assert "$SOLVENOTES_TMP_ROOT/solvenotes-ruff-cache" in script
    assert "$SOLVENOTES_TMP_ROOT/solvenotes-external-sources.json" in script



def test_basic_gate_runs_content_checks_without_private_source_audit(tmp_path):
    import json
    import sys

    skill = tmp_path / "installed" / "solvenotes-vault-maintainer"
    scripts = skill / "scripts"
    scripts.mkdir(parents=True)
    script_text = DEV_CHECK.read_text(encoding="utf-8")
    (scripts / "dev_check.sh").write_text(script_text, encoding="utf-8")
    (scripts / "run_with_timeout.py").write_text(
        "import subprocess,sys\nraise SystemExit(subprocess.call(sys.argv[sys.argv.index('--')+1:]))\n",
        encoding="utf-8",
    )
    names = [
        "doctor.py", "check_repo_hygiene.py", "check_skills_lock.py", "check_guidance.py", "check_algorithm_job_notes.py",
        "check_links.py", "check_frontmatter.py", "check_all_notes.py", "check_naturalness.py",
        "check_python_examples.py", "check_markdown_tables.py", "check_formulas.py", "check_headings.py",
    ]
    for name in names:
        (scripts / name).write_text(
            "import json,os,sys\nfrom pathlib import Path\n"
            "with open(os.environ['CHECK_LOG'],'a') as f:f.write(json.dumps([Path(__file__).name,*sys.argv[1:]])+'\\n')\n",
            encoding="utf-8",
        )
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "AGENT.md").write_text("# Rules\n", encoding="utf-8")
    log = tmp_path / "checks.jsonl"
    bin_dir, git_log = stub_git(tmp_path)
    env = os.environ.copy()
    env.update({
        "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
        "GIT_CALL_LOG": str(git_log), "CHECK_LOG": str(log),
        "SOLVENOTES_VAULT_ROOT": str(notes),
        "SOLVENOTES_MANIFEST_ROOT": str(tmp_path / "missing-private-evidence"),
        "SOLVENOTES_WORKSPACE_ROOT": str(tmp_path / "unavailable-workspace"),
        "SOLVENOTES_PYTHON_BIN": sys.executable,
        "SOLVENOTES_TMP_ROOT": str(tmp_path / "cache"),
    })
    result = subprocess.run(["bash", str(scripts / "dev_check.sh"), "vault-basic"], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "source_audit NOT_RUN" in result.stdout
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert set(call[0] for call in calls) == set(names)
    assert [call for call in calls if call[0] == "doctor.py"][0][-2:] == ["--notes-root", str(notes)]
    assert "vault-basic" in calls[0]
