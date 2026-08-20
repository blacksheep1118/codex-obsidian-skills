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
