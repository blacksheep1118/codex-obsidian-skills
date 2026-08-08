from __future__ import annotations

from pathlib import Path
import sys

import pytest

from scripts import link_inventory


@pytest.mark.parametrize("kind", ["final", "parent", "ancestor"])
def test_link_inventory_rejects_output_symlink_components(
    kind: str,
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    sentinel.write_text("keep\n", encoding="utf-8")
    if kind == "final":
        output = tmp_path / "inventory.md"
        output.symlink_to(sentinel)
    elif kind == "parent":
        parent = tmp_path / "linked-parent"
        parent.symlink_to(outside, target_is_directory=True)
        output = parent / "inventory.md"
    else:
        ancestor = tmp_path / "linked-ancestor"
        ancestor.symlink_to(outside, target_is_directory=True)
        output = ancestor / "nested" / "inventory.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [link_inventory.__file__, str(vault), "--out", str(output)],
    )

    result = link_inventory.main()

    captured = capsys.readouterr()
    assert result == 1
    assert "symlink" in captured.err.lower()
    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert not (outside / "inventory.md").exists()
    assert not (outside / "nested" / "inventory.md").exists()
