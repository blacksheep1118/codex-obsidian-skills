from __future__ import annotations

from pathlib import Path
import sys

import pytest

from scripts import collect_web_sources


@pytest.mark.parametrize("kind", ["final", "parent", "ancestor"])
def test_collect_web_sources_rejects_output_symlink_components(
    kind: str,
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    source = tmp_path / "course.html"
    source.write_text("<!doctype html><title>Course</title>", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    sentinel.write_text("keep\n", encoding="utf-8")
    if kind == "final":
        output = tmp_path / "manifest.md"
        output.symlink_to(sentinel)
    elif kind == "parent":
        parent = tmp_path / "linked-parent"
        parent.symlink_to(outside, target_is_directory=True)
        output = parent / "manifest.md"
    else:
        ancestor = tmp_path / "linked-ancestor"
        ancestor.symlink_to(outside, target_is_directory=True)
        output = ancestor / "nested" / "manifest.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [collect_web_sources.__file__, str(source), "--out", str(output)],
    )

    result = collect_web_sources.main()

    captured = capsys.readouterr()
    assert result == 1
    assert "symlink" in captured.err.lower()
    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert not (outside / "manifest.md").exists()
    assert not (outside / "nested" / "manifest.md").exists()
