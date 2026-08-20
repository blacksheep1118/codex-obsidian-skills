from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import vault_contract
from vault_contract import CURRENT_VAULT_CONTRACT_VERSION, validate_checkout, validate_lock

SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = SKILL_ROOT.parents[1]
LOCK_TOOL = SKILL_ROOT / "scripts" / "update_notes_skill_lock.py"
SUBPROCESS_TIMEOUT_SECONDS = 60


def write_lock(notes_root: Path, commit: str, version: int = CURRENT_VAULT_CONTRACT_VERSION) -> None:
    path = notes_root / ".github" / "solvenotes-skills.lock.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "repository": "blacksheep1118/codex-obsidian-skills",
                "commit": commit,
                "maintainer_skill": "solvenotes-vault-maintainer",
                "contract_version": version,
            }
        ),
        encoding="utf-8",
    )


def test_lock_contract_rejects_short_sha_and_wrong_version() -> None:
    issues = validate_lock(
        {
            "repository": "blacksheep1118/codex-obsidian-skills",
            "commit": "short",
            "maintainer_skill": "solvenotes-vault-maintainer",
            "contract_version": CURRENT_VAULT_CONTRACT_VERSION + 1,
        }
    )
    assert "commit must be a lower-case full 40-character SHA" in issues
    assert any("contract_version mismatch" in issue for issue in issues)


@pytest.mark.skipif(not (SKILLS_ROOT / ".git").exists(), reason="source-only check; installed mirrors have no Git metadata")
def test_dirty_source_checkout_does_not_claim_exact_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notes_root = tmp_path / "notes"
    notes_root.mkdir()
    commit = subprocess.check_output(["git", "-C", str(SKILLS_ROOT), "rev-parse", "HEAD"], text=True).strip()
    monkeypatch.setattr(vault_contract, "git_clean", lambda _root: False)
    write_lock(notes_root, commit)

    report = validate_checkout(notes_root, SKILLS_ROOT)

    assert report["ok"] is False
    assert report["actual_sha"] == commit
    assert report["actual_contract_version"] == CURRENT_VAULT_CONTRACT_VERSION
    assert any("dirty" in issue for issue in report["issues"])


@pytest.mark.skipif(not (SKILLS_ROOT / ".git").exists(), reason="source-only check; installed mirrors have no Git metadata")
def test_clean_source_checkout_can_match_lock_when_digest_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    notes_root = tmp_path / "notes"
    notes_root.mkdir()
    commit = subprocess.check_output(["git", "-C", str(SKILLS_ROOT), "rev-parse", "HEAD"], text=True).strip()
    monkeypatch.setattr(vault_contract, "git_clean", lambda _root: True)
    write_lock(notes_root, commit)

    report = validate_checkout(notes_root, SKILLS_ROOT)

    assert report["ok"] is True
    assert report["provenance_status"] == "EXACT_COMMIT_MATCH"


@pytest.mark.skipif(not (SKILLS_ROOT / ".git").exists(), reason="source-only check; installed mirrors have no Git metadata")
def test_installed_provenance_commit_without_lock_digest_is_not_exact(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    notes_root.mkdir()
    destination = tmp_path / "installed"
    commit = subprocess.check_output(["git", "-C", str(SKILLS_ROOT), "rev-parse", "HEAD"], text=True).strip()
    write_lock(notes_root, commit)

    result = subprocess.run(
        [
            sys.executable,
            str(SKILLS_ROOT / "scripts" / "install_skill.py"),
            "--skill",
            "solvenotes-vault-maintainer",
            "--destination",
            str(destination),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, result.stderr
    provenance_path = destination / "solvenotes-vault-maintainer" / ".codex-skill-install.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["source_commit"] = commit
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    report = validate_checkout(notes_root, destination, require_git=False)

    assert report["ok"] is False
    assert report["provenance_status"] == "CONTRACT_ONLY"
    assert any("no matching content_digest" in issue for issue in report["issues"])


@pytest.mark.skipif(not (SKILLS_ROOT / ".git").exists(), reason="source-only check; installed mirrors have no Git metadata")
def test_lock_update_is_dry_run_by_default_and_writes_only_with_flag(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    notes_root.mkdir()
    commit = subprocess.check_output(["git", "-C", str(SKILLS_ROOT), "rev-parse", "HEAD"], text=True).strip()

    dry_run = subprocess.run(
        [
            sys.executable,
            str(LOCK_TOOL),
            "--notes-root",
            str(notes_root),
            "--skills-root",
            str(SKILLS_ROOT),
            "--skills-ref",
            commit,
            "--verify-level",
            "metadata",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert dry_run.returncode == 0, dry_run.stderr
    assert not (notes_root / ".github/solvenotes-skills.lock.json").exists()

    write_run = subprocess.run(
        [
            sys.executable,
            str(LOCK_TOOL),
            "--notes-root",
            str(notes_root),
            "--skills-root",
            str(SKILLS_ROOT),
            "--skills-ref",
            commit,
            "--verify-level",
            "metadata",
            "--write",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert write_run.returncode == 0, write_run.stderr
    saved = json.loads((notes_root / ".github/solvenotes-skills.lock.json").read_text(encoding="utf-8"))
    assert saved["commit"] == commit


@pytest.mark.skipif(not (SKILLS_ROOT / ".git").exists(), reason="source-only check; installed mirrors have no Git metadata")
def test_lock_update_rejects_target_tree_without_maintainer(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    notes_root.mkdir()
    old_commit = "341846885732cf3374f41f5d0cefc00220d72c5b"

    result = subprocess.run(
        [
            sys.executable,
            str(LOCK_TOOL),
            "--notes-root",
            str(notes_root),
            "--skills-root",
            str(SKILLS_ROOT),
            "--skills-ref",
            old_commit,
            "--verify-level",
            "metadata",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode != 0
    assert "required maintainer tree" in result.stderr
    assert not (notes_root / ".github/solvenotes-skills.lock.json").exists()
