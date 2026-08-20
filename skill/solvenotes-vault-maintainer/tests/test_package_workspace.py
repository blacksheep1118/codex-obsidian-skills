from __future__ import annotations

import hashlib
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
    sidecar = json.loads(manifest_output.read_text(encoding="utf-8"))
    assert sidecar["archive_sha256"]
    assert manifest["archive_sha256"] is None
    assert sidecar | {"archive_sha256": None} == manifest


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


def test_workspace_package_rejects_symlinked_root_and_output(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    alias = tmp_path / "workspace-alias"
    try:
        alias.symlink_to(root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(ValueError, match="real directory|symlink"):
        pw.package(alias, tmp_path / "workspace.zip", tmp_path / "manifest.json")

    output_target = tmp_path / "output-target"
    output_target.write_bytes(b"do not replace")
    output = tmp_path / "workspace.zip"
    output.symlink_to(output_target)
    with pytest.raises(ValueError, match="symlink"):
        pw.package(root, output, tmp_path / "manifest.json")


def test_workspace_package_is_reproducible_with_fixed_epoch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "workspace"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "note.md").write_text("# Note\n", encoding="utf-8")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    first = tmp_path / "first.zip"
    first_manifest = tmp_path / "first.json"
    second = tmp_path / "second.zip"
    second_manifest = tmp_path / "second.json"
    pw.package(root, first, first_manifest)
    pw.package(root, second, second_manifest)

    assert first.read_bytes() == second.read_bytes()
    assert first_manifest.read_bytes() == second_manifest.read_bytes()


def test_verify_workspace_package_rejects_unsafe_zip_entry(tmp_path: Path) -> None:
    import verify_workspace_package as verifier

    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../outside.txt", "no")
        handle.writestr("BUILD-MANIFEST.json", "{}")

    payload = verifier.verify(archive)
    assert payload["ok"] is False
    assert any("unsafe ZIP entry" in issue for issue in payload["issues"])


def test_verify_workspace_package_rejects_windows_absolute_entry() -> None:
    import verify_workspace_package as verifier

    assert verifier.safe_entry("C:/Windows/system32/x") is False
    assert verifier.safe_entry("\\\\server\\share\\x") is False


def test_verify_workspace_package_rejects_non_object_manifest(tmp_path: Path) -> None:
    import verify_workspace_package as verifier

    archive = tmp_path / "scalar-manifest.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("note.md", "# note\n")
        handle.writestr("BUILD-MANIFEST.json", "[]")

    payload = verifier.verify(archive)
    assert payload["ok"] is False
    assert any("must contain a JSON object" in issue for issue in payload["issues"])


def test_verify_workspace_package_recomputes_lock_coherence(tmp_path: Path) -> None:
    import verify_workspace_package as verifier

    lock = json.dumps(
        {
            "repository": "blacksheep1118/codex-obsidian-skills",
            "commit": "b" * 40,
            "maintainer_skill": "solvenotes-vault-maintainer",
            "contract_version": 1,
        },
        sort_keys=True,
    ).encode("utf-8")
    note = b"# note\n"
    records = [
        {"path": "notes/.github/solvenotes-skills.lock.json", "size": len(lock), "sha256": hashlib.sha256(lock).hexdigest()},
        {"path": "notes/note.md", "size": len(note), "sha256": hashlib.sha256(note).hexdigest()},
    ]
    manifest = {
        "schema_version": 2,
        "coherent_workspace": True,
        "skills_commit": "a" * 40,
        "notes_locked_skills_commit": "b" * 40,
        "contract_version": 1,
        "file_count": len(records),
        "archive_entry_count": len(records) + 1,
        "content_digest": verifier.records_digest(records),
        "files": records,
    }
    archive = tmp_path / "incoherent.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(records[0]["path"], lock)
        handle.writestr(records[1]["path"], note)
        handle.writestr("BUILD-MANIFEST.json", json.dumps(manifest))

    payload = verifier.verify(archive)
    assert payload["ok"] is False
    assert any("coherent_workspace" in issue for issue in payload["issues"])
