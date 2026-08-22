import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

import check_python_runtime_examples as runtime_examples


def write_note(root: Path, body: str) -> Path:
    note = root / "example.md"
    note.write_text(body, encoding="utf-8")
    return note


def test_only_immediately_marked_python_blocks_are_selected() -> None:
    text = """\
```python
unmarked = True
```

<!-- runnable: python-e2e requires=python -->
```python
assert 2 + 2 == 4
```
"""

    blocks = runtime_examples.marked_blocks(text)

    assert len(blocks) == 1
    assert blocks[0][2] == ("python",)
    assert "2 + 2" in blocks[0][1]


def test_malformed_marker_is_reported() -> None:
    issues = runtime_examples.marker_issues(
        "<!-- runnable: python-e2e -->\n```python\npass\n```\n"
    )

    assert issues == [
        (
            1,
            "invalid python-e2e marker; expected "
            "<!-- runnable: python-e2e requires=name[,name...] -->",
        )
    ]


def test_marker_shown_inside_documentation_fence_is_not_executable() -> None:
    text = """\
````markdown
<!-- runnable: python-e2e requires=python -->
```python
raise AssertionError("documentation only")
```
````
"""

    issues, blocks = runtime_examples.parse_runtime_markdown(text)

    assert issues == []
    assert blocks == []


def test_marker_must_immediately_precede_a_closed_python_fence() -> None:
    separated = (
        "<!-- runnable: python-e2e requires=python -->\n\n```python\npass\n```\n"
    )
    unclosed = (
        "<!-- runnable: python-e2e requires=python -->\n```python\npass\n"
    )

    assert runtime_examples.marker_issues(separated) == [
        (1, "python-e2e marker must immediately precede a Python fence")
    ]
    assert runtime_examples.marker_issues(unclosed) == [
        (2, "marked Python fence is not closed")
    ]


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_timeout_must_be_positive(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="finite number greater than zero"):
        runtime_examples.positive_timeout(value)


def test_exact_requirement_parser_accepts_plain_pins_and_rejects_other_forms(
    tmp_path: Path,
) -> None:
    valid = tmp_path / "valid.txt"
    valid.write_text("numpy==1.26.4\npyspark==4.2.0\n", encoding="utf-8")

    assert runtime_examples.exact_requirement_versions(valid) == {
        "numpy": "1.26.4",
        "pyspark": "4.2.0",
    }
    for index, invalid_line in enumerate(("numpy>=1.26.4", "pyspark[ml]==4.2.0")):
        invalid = tmp_path / f"invalid-{index}.txt"
        invalid.write_text(invalid_line + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="expected one exact plain"):
            runtime_examples.exact_requirement_versions(invalid)


def test_exact_public_pin_accepts_local_build_but_not_another_public_version() -> None:
    assert runtime_examples.exact_version_matches("2.11.0+cpu", "2.11.0")
    assert not runtime_examples.exact_version_matches("2.11.1+cpu", "2.11.0")
    assert not runtime_examples.exact_version_matches("2.11.0+cpu", "2.11.0+cu130")


def test_java_17_requirement_rejects_older_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime_examples.shutil, "which", lambda _name: "/fake/java")
    monkeypatch.setattr(
        runtime_examples,
        "run_capture",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=b"",
            stderr=b'openjdk version "11.0.24"\n',
        ),
    )

    version, issue = runtime_examples.java_version()

    assert version == "11.0.24"
    assert issue == "java17: Java >=17 required (found 11.0.24)"


def test_main_executes_marked_python_in_isolated_temp_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_note(
        tmp_path,
        "<!-- runnable: python-e2e requires=python -->\n"
        "```python\n"
        "from pathlib import Path\n"
        "Path('runtime-output.txt').write_text('ok', encoding='utf-8')\n"
        "assert Path('runtime-output.txt').read_text(encoding='utf-8') == 'ok'\n"
        "```\n",
    )

    result = runtime_examples.main(
        [
            "--root",
            str(tmp_path),
            "--require-marked",
            "--reviewed-local-code",
            "--timeout",
            "5",
        ]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "marked_blocks=1 executed=1 failures=0" in output
    assert not (tmp_path / "runtime-output.txt").exists()


def test_main_fails_on_unknown_requirement_before_execution(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_note(
        tmp_path,
        "<!-- runnable: python-e2e requires=not-a-real-runtime -->\n"
        "```python\nraise AssertionError('must not run')\n```\n",
    )

    result = runtime_examples.main(["--root", str(tmp_path), "--require-marked"])

    assert result == 1
    output = capsys.readouterr().out
    assert "unknown runtime requirement: not-a-real-runtime" in output
    assert "executed=0" in output


def test_main_reports_runtime_timeout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_note(
        tmp_path,
        "<!-- runnable: python-e2e requires=python -->\n"
        "```python\nimport time\ntime.sleep(10)\n```\n",
    )

    result = runtime_examples.main(
        [
            "--root",
            str(tmp_path),
            "--require-marked",
            "--reviewed-local-code",
            "--timeout",
            "0.05",
        ]
    )

    assert result == 1
    output = capsys.readouterr().out
    assert "runtime timeout" in output
    assert "executed=0" in output


def test_runtime_environment_does_not_forward_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-leak")
    monkeypatch.setenv("PYTHONPATH", "/untrusted/import/path")

    environment = runtime_examples.runtime_environment(tmp_path)

    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "PYTHONPATH" not in environment
    assert environment["HOME"] == str(tmp_path / "home")
    assert environment["TMPDIR"] == str(tmp_path / "tmp")


def test_main_requires_explicit_review_confirmation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_note(
        tmp_path,
        "<!-- runnable: python-e2e requires=python -->\n```python\npass\n```\n",
    )

    result = runtime_examples.main(["--root", str(tmp_path), "--require-marked"])

    assert result == 1
    output = capsys.readouterr().out
    assert "requires explicit --reviewed-local-code confirmation" in output
    assert "executed=0" in output
