from pathlib import Path

import check_changed_scope
import pytest


def test_changed_scope_preserves_non_ascii_paths(monkeypatch, tmp_path: Path) -> None:
    note = tmp_path / "数字经济学" / "复习页.md"
    note.parent.mkdir()
    note.write_text("内容\n", encoding="utf-8")
    monkeypatch.setattr(check_changed_scope, "ROOT", tmp_path)

    def fake_run(command, **kwargs):
        assert "-z" in command
        if "diff-filter=ACDMRT" in command:
            assert "diff-filter=ACMRT" not in command

        class Result:
            returncode = 0
            stdout = "数字经济学/复习页.md".encode("utf-8") + b"\0"

        return Result()

    monkeypatch.setattr(check_changed_scope.subprocess, "run", fake_run)

    assert check_changed_scope.changed_files("BASE", "HEAD") == ["数字经济学/复习页.md"]


def test_changed_scope_includes_deleted_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(check_changed_scope, "ROOT", tmp_path)

    def fake_run(command, **kwargs):
        output = b"deleted.md\0" if "--diff-filter=ACDMRT" in command else b""

        class Result:
            returncode = 0
            stderr = b""
            stdout = output

        return Result()

    monkeypatch.setattr(check_changed_scope.subprocess, "run", fake_run)

    assert check_changed_scope.changed_files("BASE", "HEAD") == ["deleted.md"]


def test_changed_scope_fails_closed_when_git_path_query_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(check_changed_scope, "ROOT", tmp_path)

    def fake_run(command, **kwargs):
        class Result:
            returncode = 128
            stderr = b"fatal: bad revision"
            stdout = b""

        return Result()

    monkeypatch.setattr(check_changed_scope.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Git path query failed: fatal: bad revision"):
        check_changed_scope.changed_files("BASE", "HEAD")


def test_course_for_non_ascii_note_uses_top_level_directory() -> None:
    assert check_changed_scope.course_for("数字经济学/复习页.md") == "数字经济学"


def test_resolve_range_uses_github_pull_request_shas(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_BASE_SHA", "BASE")
    monkeypatch.setenv("GITHUB_SHA", "HEAD")

    assert check_changed_scope.resolve_range(None, None, None) == ("BASE", "HEAD")
