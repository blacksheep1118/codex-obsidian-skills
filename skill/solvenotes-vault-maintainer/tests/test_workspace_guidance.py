from pathlib import Path

from check_workspace_guidance import scan


def make_workspace(root: Path) -> None:
    (root / "agent").mkdir(parents=True)
    (root / "notes" / ".github" / "workflows").mkdir(parents=True)
    (root / "skills").mkdir()
    (root / "AGENT.md").write_text("提交和推送必须有用户明确授权。\n", encoding="utf-8")
    (root / "notes" / "AGENT.md").write_text("规则。\n", encoding="utf-8")
    (root / "agent" / "01.md").write_text("只说明工作流。\n", encoding="utf-8")
    (root / "notes" / ".github" / "solvenotes-skills.lock.json").write_text(
        '{"repository":"blacksheep1118/codex-obsidian-skills","commit":"'
        + "a" * 40
        + '","maintainer_skill":"solvenotes-vault-maintainer","contract_version":1}\n',
        encoding="utf-8",
    )
    (root / "notes" / ".github" / "workflows" / "vault-quality.yml").write_text(
        "solvenotes-skills.lock.json\n", encoding="utf-8"
    )


def test_workspace_guidance_accepts_portable_surface(tmp_path: Path) -> None:
    make_workspace(tmp_path)
    assert scan(tmp_path)["issues"] == []


def test_workspace_guidance_rejects_machine_paths_and_plural_agent(tmp_path: Path) -> None:
    make_workspace(tmp_path)
    (tmp_path / "agents").mkdir()
    (tmp_path / "agent" / "01.md").write_text("/Users/example/private\n", encoding="utf-8")
    report = scan(tmp_path)
    assert report["ok"] is False
    assert any("duplicate plural" in issue for issue in report["issues"])
    assert any("machine-specific" in issue for issue in report["issues"])
