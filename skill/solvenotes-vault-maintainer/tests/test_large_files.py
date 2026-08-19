
import check_large_files as clf
import pytest


def test_collect_current_files_warns_and_fails_by_threshold(tmp_path, monkeypatch) -> None:
    (tmp_path / "small.md").write_text("ok", encoding="utf-8")
    (tmp_path / "warn.bin").write_bytes(b"x" * 600)
    (tmp_path / "fail.bin").write_bytes(b"x" * 1200)
    monkeypatch.setattr(clf, "ROOT", tmp_path)
    monkeypatch.setattr(clf, "tracked_files", lambda: ["small.md", "warn.bin", "fail.bin"])

    payload = clf.collect_current_files(max_bytes=1000, warn_bytes=512)

    assert [row["path"] for row in payload["current_warnings"]] == ["warn.bin"]
    assert [row["path"] for row in payload["current_failures"]] == ["fail.bin"]
    assert payload["largest_current_file"]["path"] == "fail.bin"


@pytest.mark.parametrize("target_exists", [True, False])
def test_collect_current_files_uses_symlink_object_size_not_external_target(
    tmp_path,
    monkeypatch,
    target_exists: bool,
) -> None:
    outside = tmp_path.parent / f"outside-large-file-{target_exists}.bin"
    if target_exists:
        outside.write_bytes(b"x" * 2000)
    linked = tmp_path / "linked.bin"
    linked.symlink_to(outside)
    monkeypatch.setattr(clf, "ROOT", tmp_path)
    monkeypatch.setattr(clf, "tracked_files", lambda: ["linked.bin"])

    payload = clf.collect_current_files(max_bytes=1000, warn_bytes=512)

    assert payload["current_warnings"] == []
    assert payload["current_failures"] == []
    assert payload["largest_current_file"]["size_bytes"] == linked.lstat().st_size


def test_collect_history_blobs_warns_and_fails_by_threshold(monkeypatch) -> None:
    monkeypatch.setattr(clf, "history_object_paths", lambda: {"a": "small.md", "b": "asset.pdf", "c": "weights.bin"})

    def fake_run_git(args, *, input_text=None, binary=False):
        assert args[0] == "cat-file"
        return "a blob 100\nb blob 11534336\nc blob 53477376\n"

    monkeypatch.setattr(clf, "run_git", fake_run_git)

    payload = clf.collect_history_blobs(max_bytes=50 * clf.MIB, warn_bytes=10 * clf.MIB)

    assert [row["path"] for row in payload["history_warnings"]] == ["asset.pdf"]
    assert [row["path"] for row in payload["history_failures"]] == ["weights.bin"]
    assert payload["largest_history_blob"]["oid"] == "c"
