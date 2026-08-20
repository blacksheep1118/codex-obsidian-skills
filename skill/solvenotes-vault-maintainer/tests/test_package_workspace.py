from __future__ import annotations

import json
import zipfile
from pathlib import Path

import package_workspace as pw
import pytest


def test_workspace_package_excludes_local_state_and_includes_manifest(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    (root / "notes" / ".obsidian").mkdir(parents=True)
    (root / "skills" / ".git").mkdir(parents=True)
    (root / "agent").mkdir(parents=True)
    (root / "AGENT.md").write_text("# Workspace\n", encoding="utf-8")
    (root / "notes" / "note.md").write_text("# Note\n", encoding="utf-8")
    (root / "agent" / "rule.md").write_text("# Rule\n", encoding="utf-8")
    (root / "notes" / ".obsidian" / "workspace.json").write_text("{}", encoding="utf-8")
    (root / "notes" / ".obsidian" / "templates.md").write_text("# Template\n", encoding="utf-8")
    (root / "skills" / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
    (root / "old.zip").write_bytes(b"old")
    (root / "notes" / "workspace.local.yaml").write_text("secret: no\n", encoding="utf-8")
    (root / "external-source").mkdir()
    (root / "external-source" / "source.pptx").write_bytes(b"not part of workspace package")
    output = tmp_path / "workspace.zip"
    manifest_output = tmp_path / "BUILD-MANIFEST.json"

    count, _size = pw.package(root, output, manifest_output)

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert names == [
            "AGENT.md",
            "agent/rule.md",
            "notes/.obsidian/templates.md",
            "notes/note.md",
            "BUILD-MANIFEST.json",
        ]
        assert "external-source/source.pptx" not in names
        manifest = json.loads(archive.read("BUILD-MANIFEST.json"))
    assert count == 4
    assert manifest["file_count"] == 4
    assert manifest["archive_entry_count"] == 5
    assert manifest["files"][0]["path"] == "AGENT.md"
    assert "workspace" not in manifest["files"][2]["path"]
    assert json.loads(manifest_output.read_text(encoding="utf-8")) == manifest


def test_workspace_package_rejects_outputs_inside_root(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    with pytest.raises(ValueError, match="outside the workspace root"):
        pw.package(root, root / "workspace.zip", tmp_path / "manifest.json")


def test_workspace_package_rejects_same_output_and_manifest(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    output = tmp_path / "same"
    with pytest.raises(ValueError, match="different files"):
        pw.package(root, output, output)
