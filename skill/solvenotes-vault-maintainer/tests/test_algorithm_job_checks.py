import os
from pathlib import Path

from algorithm_job_taxonomy import CANONICAL_IDS
from check_algorithm_job_notes import scan
from check_cpp_examples import marked_blocks

ROOT = Path(os.environ["SOLVENOTES_VAULT_ROOT"])


def test_algorithm_job_scan_uses_closed_nine_direction_set():
    payload = scan(ROOT)
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
