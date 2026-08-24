import argparse
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import check_cpp_examples
from check_cpp_examples import DEFAULT_TIMEOUT_SECONDS, marked_blocks, positive_timeout


def test_only_explicit_cpp17_blocks_are_selected() -> None:
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


@pytest.mark.parametrize("value", ["0", "-1"])
def test_timeout_must_be_positive(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="greater than zero"):
        positive_timeout(value)


def test_default_timeout_allows_cold_ci_compiler_startup() -> None:
    assert DEFAULT_TIMEOUT_SECONDS == 15.0


def test_compile_timeout_is_reported_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    note = tmp_path / "example.md"
    note.write_text(
        "<!-- runnable: cpp17 -->\n```cpp\nint main() { return 0; }\n```\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_cpp_examples.shutil, "which", lambda _name: "/fake/g++")

    def time_out(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=124,
            stdout=b"",
            stderr=b"",
            timed_out=True,
            stdout_limit_exceeded=False,
            stderr_limit_exceeded=False,
        )

    monkeypatch.setattr(check_cpp_examples, "run_capture", time_out)
    monkeypatch.setattr(sys, "argv", ["check_cpp_examples.py", "--root", str(tmp_path)])

    assert check_cpp_examples.main() == 1
    output = capsys.readouterr()
    assert "compiled=0 failures=1" in output.out
    assert "FAIL example.md:2: compile timeout" in output.out
    assert "Traceback" not in output.err
