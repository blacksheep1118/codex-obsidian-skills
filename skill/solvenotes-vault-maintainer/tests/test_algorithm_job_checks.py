import os
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
