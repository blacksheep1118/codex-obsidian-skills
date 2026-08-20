import io
import tarfile
from pathlib import Path

import pytest
import update_notes_skill_lock


def test_target_paths_preserve_unicode_fixture_names(monkeypatch, tmp_path: Path) -> None:
    def fake_run(command, **kwargs):
        assert "-z" in command
        assert "core.quotePath=false" in command

        class Result:
            returncode = 0
            stderr = b""
            stdout = (
                "skill/solvenotes-vault-maintainer/fixtures/solvenotes-mini-vault/"
                "算法岗学习笔记/00_算法岗学习地图.md\0"
            ).encode("utf-8")

        return Result()

    monkeypatch.setattr(update_notes_skill_lock.subprocess, "run", fake_run)

    assert update_notes_skill_lock.target_paths(tmp_path, "a" * 40) == [
        "skill/solvenotes-vault-maintainer/fixtures/solvenotes-mini-vault/"
        "算法岗学习笔记/00_算法岗学习地图.md"
    ]


def test_repository_identity_rejects_unrelated_remote(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        update_notes_skill_lock,
        "git_origin_url",
        lambda _root: "git@github.com:someone/unrelated-skills.git",
    )

    with pytest.raises(ValueError, match="does not match"):
        update_notes_skill_lock.verify_repository_identity(tmp_path)


def test_repository_identity_allows_explicit_local_test_source(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(update_notes_skill_lock, "git_origin_url", lambda _root: str(tmp_path))

    update_notes_skill_lock.verify_repository_identity(tmp_path, allow_local_source=True)


def test_tar_extraction_rejects_traversal_and_links(tmp_path: Path) -> None:
    traversal = io.BytesIO()
    with tarfile.open(fileobj=traversal, mode="w") as archive:
        info = tarfile.TarInfo("../outside.txt")
        data = b"unsafe"
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    traversal.seek(0)
    with tarfile.open(fileobj=traversal, mode="r:") as archive:
        with pytest.raises(ValueError, match="unsafe Skills archive member"):
            update_notes_skill_lock.safe_extract_tar(archive, tmp_path)

    symlink = io.BytesIO()
    with tarfile.open(fileobj=symlink, mode="w") as archive:
        info = tarfile.TarInfo("link")
        info.type = tarfile.SYMTYPE
        info.linkname = "outside"
        archive.addfile(info)
    symlink.seek(0)
    with tarfile.open(fileobj=symlink, mode="r:") as archive:
        with pytest.raises(ValueError, match="link member"):
            update_notes_skill_lock.safe_extract_tar(archive, tmp_path)
