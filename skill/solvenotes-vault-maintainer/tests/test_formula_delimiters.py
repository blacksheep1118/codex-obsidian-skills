"""Escaped stack-bottom dollars must not become display math delimiters."""

import json
import sys
from types import SimpleNamespace

import check_all_notes
import check_formulas
import pytest
from notes_utils import split_block_math

STACK_TABLE = r"""| Input | Stack | Action |
| --- | --- | --- |
| `aab` | $S\$$ | Start |
| `aab` | $aTb\$$ | Expand |
| `ab` | $Tb\$$ | Match |
| `ab` | $Tab\$$ | Expand |
| `ab` | $ab\$$ | Expand |
| `b` | $b\$$ | Match |
| $\varepsilon$ | $\$$ | Match |
"""


@pytest.mark.parametrize("slashes", range(6))
def test_backslash_parity_preserves_prose_and_formula_content(slashes):
    prefix = "prefix " + "\\" * slashes
    text = prefix + "$$x$$ suffix"
    expected = [prefix, "x", " suffix"] if slashes % 2 == 0 else [prefix + "$$x", " suffix"]
    assert split_block_math(text) == expected


def test_escaped_dollar_does_not_consume_following_display_delimiter():
    assert split_block_math(r"\$$$x$$") == [r"\$", "x", ""]


def test_inline_stack_dollars_are_not_formula_blocks():
    assert check_formulas.block_formulas(STACK_TABLE) == []
    assert check_formulas.block_formulas(STACK_TABLE + "\n$$\nx=1\n$$\n") == ["\nx=1\n"]


def test_code_is_still_excluded_from_formula_blocks():
    text = "`$$`\n~~~latex\n$$\n~~~\n    $$\n\n$$x$$\n"
    assert check_formulas.block_formulas(text) == ["x"]


@pytest.mark.parametrize("checker", [check_all_notes, check_formulas])
@pytest.mark.parametrize(
    "body, unbalanced",
    [
        (STACK_TABLE, False),
        (STACK_TABLE + "\n$$x$$\n", False),
        (STACK_TABLE + "\n$$x\n", True),
        (STACK_TABLE + "\n$$x$$\n$$y\n", True),
        (r"\$$", False),
        (r"\\$$", True),
        (r"\\\$$", False),
        (r"\\\\$$", True),
    ],
)
def test_both_checkers_report_only_real_unbalanced_display_pairs(
    checker, body, unbalanced, tmp_path, monkeypatch, capsys
):
    note = tmp_path / "note.md"
    note.write_text(body, encoding="utf-8")
    monkeypatch.setattr(checker, "markdown_files", lambda: [note])
    monkeypatch.setattr(checker, "rel", lambda path: path.name)
    monkeypatch.setattr(sys, "argv", [checker.__file__, "--json"])
    if checker is check_all_notes:
        monkeypatch.setattr(checker, "build_note_index", lambda: {})
        monkeypatch.setattr(checker, "infer_note_type", lambda path: "template")
        monkeypatch.setattr(checker.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    status = checker.main()
    payload = json.loads(capsys.readouterr().out)
    delimiter_issues = [issue for issue in payload["issues"] if "unbalanced" in issue]
    assert len(delimiter_issues) == int(unbalanced)
    assert status == int(unbalanced)
