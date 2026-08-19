from __future__ import annotations

import subprocess
from pathlib import Path

from check_guidance import collect_guidance_report, guidance_boundary_issues, guidance_files

HEADER = """---
course: "仓库规则"
note_type: "agent_rule"
source_files: []
coverage: "special_rule"
last_checked: "2026-08-19"
tags:
  - "course/仓库规则"
  - "type/agent_rule"
---
"""


def write_repo(root: Path) -> None:
    (root / "AGENT.md").write_text(
        HEADER
        + "\n# 规则\n\n提交和推送必须有用户明确授权。\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "AGENT.md"], cwd=root, check=True)


def test_valid_external_vault_guidance_passes(tmp_path: Path) -> None:
    write_repo(tmp_path)
    report = collect_guidance_report(tmp_path)
    assert report["guidance_files_checked"] == 1
    assert report["guidance_wikilinks_checked"] == 0
    assert report["issues"] == []
    assert guidance_files(tmp_path) == [tmp_path / "AGENT.md"]


def test_notes_rule_does_not_require_an_in_vault_scripts_readme(tmp_path: Path) -> None:
    write_repo(tmp_path)
    assert not (tmp_path / "scripts").exists()
    assert collect_guidance_report(tmp_path)["guidance_supporting_files_checked"] == 0


def test_maintenance_objects_are_rejected_from_notes(tmp_path: Path) -> None:
    write_repo(tmp_path)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n", encoding="utf-8")

    issues = guidance_boundary_issues(tmp_path)

    assert any("scripts" in issue and "external Solvenotes Skill" in issue for issue in issues)
    assert any("tests" in issue for issue in issues)
    assert any("pyproject.toml" in issue for issue in issues)


def test_nested_agent_objects_are_rejected(tmp_path: Path) -> None:
    write_repo(tmp_path)
    (tmp_path / "课程" / "AGENT.md").parent.mkdir()
    (tmp_path / "课程" / "AGENT.md").write_text("nested\n", encoding="utf-8")
    (tmp_path / "课程" / "agent").mkdir()

    issues = guidance_boundary_issues(tmp_path)

    assert any("课程/AGENT.md" in issue for issue in issues)
    assert any("课程/agent" in issue for issue in issues)


def test_guidance_rejects_implicit_git_authority(tmp_path: Path) -> None:
    write_repo(tmp_path)
    path = tmp_path / "AGENT.md"
    path.write_text(path.read_text(encoding="utf-8").replace("提交和推送必须有用户明确授权。", "修改后自动推送。"), encoding="utf-8")

    issues = collect_guidance_report(tmp_path)["issues"]

    assert any("automatic commit or push authority" in issue for issue in issues)
    assert any("must explicitly require user authorization" in issue for issue in issues)


def test_guidance_rejects_unclosed_fence_and_bad_control_character(tmp_path: Path) -> None:
    write_repo(tmp_path)
    path = tmp_path / "AGENT.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n```bash\nunsafe\x01\n", encoding="utf-8")

    issues = collect_guidance_report(tmp_path)["issues"]

    assert any("unclosed fenced code block" in issue for issue in issues)
    assert any("illegal control character" in issue for issue in issues)
