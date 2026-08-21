from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import package_workspace as pw
import pytest
from vault_contract import CURRENT_LOCK_SCHEMA_VERSION, CURRENT_VAULT_CONTRACT_VERSION


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

    count, _size = pw.package(root, output, manifest_output, allow_lock_drift=True)

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
    assert manifest["root_agent_files"] == 1
    assert manifest["agent_rule_files"] == 1
    assert manifest["notes_files"] == 2
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


def test_workspace_lock_drift_names_dirty_checkout_and_digest_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notes_root = tmp_path / "notes"
    skills_root = tmp_path / "skills"
    (notes_root / ".github").mkdir(parents=True)
    skills_root.mkdir()
    commit = "a" * 40
    graph = {
        "algorithm-job-notes-for-obsidian": [],
        "solvenotes-vault-maintainer": ["algorithm-job-notes-for-obsidian"],
    }
    lock = {
        "schema_version": CURRENT_LOCK_SCHEMA_VERSION,
        "repository": "blacksheep1118/codex-obsidian-skills",
        "commit": commit,
        "maintainer_skill": "solvenotes-vault-maintainer",
        "contract_version": CURRENT_VAULT_CONTRACT_VERSION,
        "skills": {
            name: {"content_digest": "b" * 64} for name in pw.REQUIRED_SKILLS
        },
        "dependency_graph_digest": pw.dependency_graph_digest(graph),
    }
    (notes_root / ".github" / "solvenotes-skills.lock.json").write_text(
        json.dumps(lock), encoding="utf-8"
    )
    monkeypatch.setattr(pw, "git_commit", lambda _root: commit)
    monkeypatch.setattr(pw, "git_is_clean", lambda _root: False)
    monkeypatch.setattr(pw, "skill_content_digest", lambda _root, _name: "c" * 64)
    monkeypatch.setattr(pw, "source_dependency_graph", lambda _root: graph)

    with pytest.raises(ValueError) as exc_info:
        pw.lock_metadata(notes_root, skills_root)

    message = str(exc_info.value)
    assert "Skills checkout is dirty" in message
    assert "content digest mismatch for solvenotes-vault-maintainer" in message
    assert "commit mismatch" not in message


def test_workspace_package_cli_reports_expected_failure_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(*_args, **_kwargs):
        raise ValueError("content digest mismatch")

    monkeypatch.setattr(pw, "package", fail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "package_workspace.py",
            "--root",
            str(tmp_path),
            "--output",
            str(tmp_path / "out.zip"),
            "--manifest-output",
            str(tmp_path / "manifest.json"),
        ],
    )

    assert pw.main() == 1
    captured = capsys.readouterr()
    assert "workspace_package_error content digest mismatch" in captured.err
    assert "Traceback" not in captured.err


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


def test_workspace_package_rejects_symlinked_output_or_manifest_parent(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    real_parent = tmp_path / "real-output"
    real_parent.mkdir()
    alias_parent = tmp_path / "alias-output"
    try:
        alias_parent.symlink_to(real_parent, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    with pytest.raises(ValueError, match="symlink"):
        pw.package(
            root,
            alias_parent / "workspace.zip",
            tmp_path / "manifest.json",
            allow_lock_drift=True,
        )
    with pytest.raises(ValueError, match="symlink"):
        pw.package(
            root,
            tmp_path / "workspace.zip",
            alias_parent / "manifest.json",
            allow_lock_drift=True,
        )


def test_workspace_package_rejects_broken_output_symlink(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    output = tmp_path / "workspace.zip"
    try:
        output.symlink_to(tmp_path / "missing-target")
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    with pytest.raises(ValueError, match="symlink"):
        pw.package(root, output, tmp_path / "manifest.json", allow_lock_drift=True)


def test_workspace_package_is_reproducible_with_fixed_epoch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "workspace"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "note.md").write_text("# Note\n", encoding="utf-8")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    first = tmp_path / "first.zip"
    first_manifest = tmp_path / "first.json"
    second = tmp_path / "second.zip"
    second_manifest = tmp_path / "second.json"
    pw.package(root, first, first_manifest, allow_lock_drift=True)
    pw.package(root, second, second_manifest, allow_lock_drift=True)

    assert first.read_bytes() == second.read_bytes()
    assert first_manifest.read_bytes() == second_manifest.read_bytes()


def test_workspace_verifier_checks_sidecar_archive_digest(tmp_path: Path) -> None:
    import verify_workspace_package as verifier

    root = tmp_path / "workspace"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "note.md").write_text("# Note\n", encoding="utf-8")
    archive = tmp_path / "workspace.zip"
    sidecar = tmp_path / "manifest.json"
    pw.package(root, archive, sidecar, allow_lock_drift=True)

    payload = verifier.verify(archive, sidecar)
    assert not any("sidecar" in issue for issue in payload["issues"])

    tampered = json.loads(sidecar.read_text(encoding="utf-8"))
    tampered["archive_sha256"] = "0" * 64
    sidecar.write_text(json.dumps(tampered), encoding="utf-8")
    payload = verifier.verify(archive, sidecar)
    assert any("sidecar archive_sha256" in issue for issue in payload["issues"])


def test_workspace_verifier_uses_runtime_skill_payload_digest() -> None:
    import verify_workspace_package as verifier

    runtime = b"runtime"
    development_test = b"not installed"
    files = [
        {
            "path": "skills/skill/solvenotes-vault-maintainer/scripts/run.py",
            "size": len(runtime),
            "sha256": hashlib.sha256(runtime).hexdigest(),
        },
        {
            "path": "skills/skill/solvenotes-vault-maintainer/tests/test_run.py",
            "size": len(development_test),
            "sha256": hashlib.sha256(development_test).hexdigest(),
        },
    ]
    expected = verifier.records_digest(
        [
            {
                "path": "scripts/run.py",
                "size": len(runtime),
                "sha256": hashlib.sha256(runtime).hexdigest(),
            }
        ]
    )

    assert (
        verifier._skill_digest_from_manifest(
            files, "solvenotes-vault-maintainer"
        )
        == expected
    )


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


@pytest.mark.parametrize(
    "name",
    [
        "notes/bad\x00name.md",
        "notes/bad:name.md",
        "notes/NUL.txt",
        "notes/trailing-space ",
        "notes/trailing-dot.",
    ],
)
def test_archive_entry_contract_rejects_nonportable_components(name: str) -> None:
    import verify_workspace_package as verifier

    assert verifier.safe_entry(name) is False


def test_verify_workspace_package_rejects_non_object_manifest(tmp_path: Path) -> None:
    import verify_workspace_package as verifier

    archive = tmp_path / "scalar-manifest.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("note.md", "# note\n")
        handle.writestr("BUILD-MANIFEST.json", "[]")

    payload = verifier.verify(archive)
    assert payload["ok"] is False
    assert any("must contain a JSON object" in issue for issue in payload["issues"])


def test_verify_workspace_package_reports_malformed_zip_without_traceback(tmp_path: Path) -> None:
    import verify_workspace_package as verifier

    archive = tmp_path / "malformed.zip"
    archive.write_bytes(b"not a zip archive")

    payload = verifier.verify(archive)

    assert payload["ok"] is False
    assert payload["entries"] == 0
    assert any("invalid workspace ZIP" in issue for issue in payload["issues"])


def test_verify_workspace_package_missing_archive_is_structured_failure(tmp_path: Path) -> None:
    import verify_workspace_package as verifier

    payload = verifier.verify(tmp_path / "missing.zip")

    assert payload["ok"] is False
    assert payload["entries"] == 0
    assert payload["archive_sha256"] == ""
    assert any("does not exist" in issue for issue in payload["issues"])


def test_verify_workspace_package_reports_non_utf8_sidecar(tmp_path: Path) -> None:
    import verify_workspace_package as verifier

    root = tmp_path / "workspace"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "note.md").write_text("# Note\n", encoding="utf-8")
    archive = tmp_path / "workspace.zip"
    sidecar = tmp_path / "manifest.json"
    pw.package(root, archive, sidecar, allow_lock_drift=True)
    sidecar.write_bytes(b"\xff\xfe")

    payload = verifier.verify(archive, sidecar)

    assert payload["ok"] is False
    assert any("invalid sidecar manifest" in issue for issue in payload["issues"])


def test_verify_workspace_package_recomputes_lock_coherence(tmp_path: Path) -> None:
    import verify_workspace_package as verifier

    lock = json.dumps(
        {
            "schema_version": 2,
            "repository": "blacksheep1118/codex-obsidian-skills",
            "commit": "b" * 40,
            "maintainer_skill": "solvenotes-vault-maintainer",
            "contract_version": 1,
            "skills": {
                "solvenotes-vault-maintainer": {"content_digest": "c" * 64},
                "algorithm-job-notes-for-obsidian": {"content_digest": "d" * 64},
            },
            "dependency_graph_digest": "e" * 64,
        },
        sort_keys=True,
    ).encode("utf-8")
    note = b"# note\n"
    records = [
        {"path": "notes/.github/solvenotes-skills.lock.json", "size": len(lock), "sha256": hashlib.sha256(lock).hexdigest()},
        {"path": "notes/note.md", "size": len(note), "sha256": hashlib.sha256(note).hexdigest()},
    ]
    manifest = {
        "schema_version": 3,
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
