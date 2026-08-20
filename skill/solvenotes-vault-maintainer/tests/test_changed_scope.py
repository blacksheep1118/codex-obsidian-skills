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


def test_suggested_checks_use_stable_ids_and_registry_records() -> None:
    checks = check_changed_scope.suggested_checks(
        [
            "算法岗学习笔记/111_排序二分分治_边界与答案搜索.md",
            ".github/solvenotes-skills.lock.json",
        ]
    )

    assert checks == ["algorithm_job", "cpp17", "frontmatter", "links", "naturalness", "package"]
    records = check_changed_scope.command_records(checks)
    assert [record["id"] for record in records] == checks
    assert all(record["owner"] in {"maintainer", "algorithm-job"} for record in records)
    assert all(str(record["script"]).startswith("scripts/") for record in records)


def test_registry_scripts_and_declared_parameters_exist() -> None:
    maintainer_root = Path(check_changed_scope.__file__).resolve().parents[1]
    algorithm_root = maintainer_root.parent / "algorithm-job-notes-for-obsidian"
    owner_roots = {"maintainer": maintainer_root, "algorithm-job": algorithm_root}

    for check_id, record in check_changed_scope.CHECK_REGISTRY.items():
        owner = str(record["owner"])
        script = owner_roots[owner] / str(record["script"])
        assert script.is_file(), f"{check_id}: missing mapped script {script}"
        assert isinstance(record["arguments"], list)


def test_infrastructure_changes_request_package_check() -> None:
    for path in (".gitignore", ".gitattributes", "notes.base", ".github/workflows/vault-quality.yml"):
        assert "package" in check_changed_scope.suggested_checks([path])
