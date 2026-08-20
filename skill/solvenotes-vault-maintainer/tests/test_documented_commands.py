from pathlib import Path

import check_documented_commands


def test_documented_command_paths_are_checked_without_executing_shell(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    skills = workspace / "skills"
    (workspace / "notes").mkdir(parents=True)
    (workspace / "agent").mkdir()
    (skills / "skill" / "demo" / "scripts").mkdir(parents=True)
    (skills / "scripts").mkdir()
    (workspace / "AGENT.md").write_text("run `scripts/root.py`\n", encoding="utf-8")
    (workspace / "notes" / "AGENT.md").write_text("run `skill/demo/scripts/check.py`\n", encoding="utf-8")
    (workspace / "notes" / "README.md").write_text("ignore /path/to/example.py\n", encoding="utf-8")
    (skills / "README.md").write_text("run `scripts/root.py`\n", encoding="utf-8")
    (skills / "CONTRIBUTING.md").write_text("run `scripts/root.py`\n", encoding="utf-8")
    (skills / "skill" / "demo" / "SKILL.md").write_text("run `scripts/check.py`\n", encoding="utf-8")
    (skills / "scripts" / "root.py").write_text("# root\n", encoding="utf-8")
    (skills / "skill" / "demo" / "scripts" / "check.py").write_text("# check\n", encoding="utf-8")

    payload = check_documented_commands.scan(workspace, skills)

    assert payload["issue_count"] == 0
    assert payload["references_checked"] == 3


def test_documented_command_missing_path_is_reported(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "notes").mkdir(parents=True)
    (workspace / "agent").mkdir()
    (workspace / "skills").mkdir()
    (workspace / "AGENT.md").write_text("run `scripts/missing.py`\n", encoding="utf-8")

    payload = check_documented_commands.scan(workspace, workspace / "skills")

    assert payload["issue_count"] == 1
    assert payload["issues"][0]["token"] == "scripts/missing.py"
