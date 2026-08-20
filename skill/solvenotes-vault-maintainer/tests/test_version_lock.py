from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import vault_contract
import update_notes_skill_lock
from validate_notes_candidate import candidate_lock
from vault_contract import (
    CURRENT_LOCK_SCHEMA_VERSION,
    CURRENT_VAULT_CONTRACT_VERSION,
    MAINTAINER_SKILL,
    REQUIRED_SKILLS,
    SKILLS_REPOSITORY,
    dependency_graph_digest,
    skill_content_digest,
    source_dependency_graph,
    validate_checkout,
    validate_lock,
)

SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = SKILL_ROOT.parents[1]
LOCK_TOOL = SKILL_ROOT / "scripts" / "update_notes_skill_lock.py"
SUBPROCESS_TIMEOUT_SECONDS = 60


def synthetic_target_repo(tmp_path: Path) -> tuple[Path, str]:
    """Commit the current target-tree contract without relying on checkout HEAD."""

    repository = tmp_path / "target-skills"
    repository.mkdir()
    for relative in update_notes_skill_lock.TARGET_FILES:
        source = SKILLS_ROOT / relative
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    fixture = repository / update_notes_skill_lock.TARGET_FIXTURE_PREFIX / "AGENT.md"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("# synthetic fixture\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repository, check=True)
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-m", "synthetic target"], cwd=repository, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    return repository, commit


def write_lock(notes_root: Path, commit: str, version: int = CURRENT_VAULT_CONTRACT_VERSION) -> None:
    path = notes_root / ".github" / "solvenotes-skills.lock.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": CURRENT_LOCK_SCHEMA_VERSION,
                "repository": SKILLS_REPOSITORY,
                "commit": commit,
                "maintainer_skill": MAINTAINER_SKILL,
                "contract_version": version,
                "skills": {
                    name: {"content_digest": skill_content_digest(SKILLS_ROOT, name)}
                    for name in REQUIRED_SKILLS
                },
                "dependency_graph_digest": dependency_graph_digest(
                    source_dependency_graph(SKILLS_ROOT) or {}
                ),
            }
        ),
        encoding="utf-8",
    )


def test_lock_contract_rejects_short_sha_and_wrong_version() -> None:
    issues = validate_lock(
        {
            "schema_version": CURRENT_LOCK_SCHEMA_VERSION,
            "repository": SKILLS_REPOSITORY,
            "commit": "short",
            "maintainer_skill": MAINTAINER_SKILL,
            "contract_version": CURRENT_VAULT_CONTRACT_VERSION + 1,
            "skills": {
                name: {"content_digest": "a" * 64} for name in REQUIRED_SKILLS
            },
            "dependency_graph_digest": "b" * 64,
        }
    )
    assert "commit must be a lower-case full 40-character SHA" in issues
    assert any("contract_version mismatch" in issue for issue in issues)


def test_candidate_lock_covers_the_required_dependency_closure() -> None:
    target = {
        "contract_version": CURRENT_VAULT_CONTRACT_VERSION,
        "skills": {name: {"content_digest": "a" * 64} for name in REQUIRED_SKILLS},
        "dependency_graph_digest": "b" * 64,
    }

    payload = candidate_lock("c" * 40, target)

    assert payload["schema_version"] == CURRENT_LOCK_SCHEMA_VERSION
    assert set(payload["skills"]) == set(REQUIRED_SKILLS)
    assert validate_lock(payload) == []


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
def test_installed_dependency_provenance_mismatch_is_rejected(tmp_path: Path) -> None:
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
    provenance_path = destination / "algorithm-job-notes-for-obsidian" / ".codex-skill-install.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["source_commit"] = "0" * 40
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    report = validate_checkout(notes_root, destination, require_git=False)

    assert report["ok"] is False
    assert report["provenance_status"] in {"CONTENT_MATCH", "CONTRACT_ONLY", "MISMATCH"}
    assert report["provenance_status"] != "EXACT_COMMIT_MATCH"


@pytest.mark.skipif(not (SKILLS_ROOT / ".git").exists(), reason="source-only check; installed mirrors have no Git metadata")
def test_lock_update_is_dry_run_by_default_and_writes_only_with_flag(tmp_path: Path) -> None:
    notes_root = tmp_path / "notes"
    notes_root.mkdir()
    target_repo, commit = synthetic_target_repo(tmp_path)

    dry_run = subprocess.run(
        [
            sys.executable,
            str(LOCK_TOOL),
            "--notes-root",
            str(notes_root),
            "--skills-root",
            str(target_repo),
            "--skills-ref",
            commit,
            "--verify-level",
            "metadata",
            "--allow-local-source",
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
            str(target_repo),
            "--skills-ref",
            commit,
            "--verify-level",
            "metadata",
            "--allow-local-source",
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
    target_repo = tmp_path / "target-repo"
    target_repo.mkdir()
    subprocess.run(["git", "init"], cwd=target_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=target_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=target_repo, check=True)
    (target_repo / "README.md").write_text("synthetic old tree\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=target_repo, check=True)
    subprocess.run(["git", "commit", "-m", "old tree"], cwd=target_repo, check=True, capture_output=True)
    old_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target_repo, text=True).strip()

    result = subprocess.run(
        [
            sys.executable,
            str(LOCK_TOOL),
            "--notes-root",
            str(notes_root),
            "--skills-root",
            str(target_repo),
            "--skills-ref",
            old_commit,
            "--verify-level",
            "metadata",
            "--allow-local-source",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode != 0
    assert "required maintainer tree" in result.stderr
    assert not (notes_root / ".github/solvenotes-skills.lock.json").exists()
