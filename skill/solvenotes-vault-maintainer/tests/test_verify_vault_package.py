from __future__ import annotations

import json
import stat
import warnings
import zipfile
from pathlib import Path

import package_vault as packager
import verify_vault_package as verifier


def _build(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("# Note\n", encoding="utf-8")
    archive = tmp_path / "notes.zip"
    sidecar = tmp_path / "notes.manifest.json"
    monkeypatch.setattr(packager, "ROOT", root)
    packager.package(archive, sidecar)
    return archive, sidecar


def test_verify_vault_package_accepts_package_and_sidecar(tmp_path: Path, monkeypatch) -> None:
    archive, sidecar = _build(tmp_path, monkeypatch)

    result = verifier.verify(archive, sidecar)

    assert result["ok"] is True
    assert result["issues"] == []


def test_vault_package_is_reproducible(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "中文 笔记.md").write_text("# 可复现\n", encoding="utf-8")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    monkeypatch.setattr(packager, "ROOT", root)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    packager.package(first)
    packager.package(second)

    assert first.read_bytes() == second.read_bytes()


def test_verify_vault_package_rejects_duplicate_and_traversal_entries(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("../escape.md", b"bad")
            bundle.writestr("note.md", b"one")
            bundle.writestr("note.md", b"two")

    result = verifier.verify(archive)

    assert result["ok"] is False
    assert "duplicate ZIP entries" in result["issues"]
    assert "unsafe ZIP entry: ../escape.md" in result["issues"]


def test_verify_vault_package_rejects_symlink_entry(tmp_path: Path) -> None:
    archive = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("link.md")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(info, "target.md")

    result = verifier.verify(archive)

    assert result["ok"] is False
    assert "symbolic-link ZIP entry: link.md" in result["issues"]


def test_verify_vault_package_detects_tampered_manifest(tmp_path: Path, monkeypatch) -> None:
    archive, _sidecar = _build(tmp_path, monkeypatch)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive, "r") as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == packager.MANIFEST_NAME:
                payload = json.loads(data)
                payload["content_digest"] = "0" * 64
                data = json.dumps(payload).encode()
            target.writestr(info, data)

    result = verifier.verify(tampered)

    assert result["ok"] is False
    assert "manifest content_digest does not match file records" in result["issues"]
