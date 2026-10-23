import os
import subprocess
import sys
from pathlib import Path

import check_algorithm_job_notes
import pytest
from algorithm_job_taxonomy import CANONICAL_IDS
from check_cpp_examples import marked_blocks

ROOT = Path(os.environ["SOLVENOTES_VAULT_ROOT"])


def test_algorithm_job_scan_uses_closed_nine_direction_set():
    payload = check_algorithm_job_notes.scan(ROOT)
    assert payload["ok"] is True
    assert len(CANONICAL_IDS) == 9
    assert len(payload["canonical_directions"]) == 9


def test_cpp_checker_only_selects_explicit_marker():
    text = """\
```cpp
int unmarked = 1;
```

<!-- runnable: cpp17 -->
```cpp
int main() { return 0; }
```
"""
    blocks = marked_blocks(text)
    assert len(blocks) == 1
    assert "int main" in blocks[0][1]


def test_algorithm_adapter_reports_missing_sibling_skill(tmp_path, monkeypatch):
    monkeypatch.setattr(check_algorithm_job_notes, "SKILL_ROOT", tmp_path / "maintainer")
    with pytest.raises(RuntimeError, match="required Skill not installed"):
        check_algorithm_job_notes.scan(tmp_path)


def test_algorithm_adapter_text_cli_forwards_exclusions_and_handles_walk_errors(
    monkeypatch,
    capsys,
):
    payload = {
        "ok": True,
        "algorithm_files": 4,
        "excluded_paths": [
            {"path": "算法岗学习笔记/专题-link", "reason": "symlink_directory"}
        ],
        "canonical_directions": ["CV", "NLP / LLM"],
        "issues": [],
    }
    monkeypatch.setattr(check_algorithm_job_notes, "scan", lambda _root: payload)
    monkeypatch.setattr(
        sys,
        "argv",
        ["check_algorithm_job_notes.py", "--root", str(ROOT)],
    )

    assert check_algorithm_job_notes.main() == 0
    captured = capsys.readouterr()
    assert "algorithm_job_files 4" in captured.out
    assert "algorithm_job_excluded_paths 1" in captured.out
    assert "EXCLUDED symlink_directory: 算法岗学习笔记/专题-link" in captured.out

    def fail_scan(_root):
        raise PermissionError("permission denied while scanning")

    monkeypatch.setattr(check_algorithm_job_notes, "scan", fail_scan)
    assert check_algorithm_job_notes.main() == 2
    captured = capsys.readouterr()
    assert "ERROR: permission denied while scanning" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("json_output", [False, True])
def test_algorithm_adapter_rejects_symlink_loop_without_traceback(tmp_path, json_output):
    loop = tmp_path / "loop"
    try:
        loop.symlink_to(loop, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    result = subprocess.run(
        [
            sys.executable,
            str(Path(check_algorithm_job_notes.__file__)),
            "--root", str(loop),
            *(["--json"] if json_output else []),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout == ""
    assert result.stderr.startswith("ERROR: ")
    assert str(loop) in result.stderr
    assert "Traceback" not in result.stderr
