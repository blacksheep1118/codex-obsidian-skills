from __future__ import annotations

from pathlib import Path
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from shared.skill_provenance import file_records, validate_provenance_payload  # noqa: E402


DIGEST = "a" * 64
COMMIT = "b" * 40


def valid_payload() -> dict[str, object]:
    return {
        "schema_version": 2,
        "skill": "parent-skill",
        "source_repository": "owner/repository",
        "source_commit": COMMIT,
        "source_dirty": False,
        "source_tree_digest": DIGEST,
        "installed_content_digest": DIGEST,
        "content_digest": DIGEST,
        "contract_version": 1,
        "dependencies": ["child-skill"],
        "dependency_digests": {"child-skill": DIGEST},
        "managed_files": [
            {"path": "SKILL.md", "size": 10, "sha256": DIGEST},
            {"path": "scripts/run.py", "size": 20, "sha256": DIGEST},
        ],
    }


def test_valid_provenance_schema_passes() -> None:
    assert validate_provenance_payload(
        valid_payload(),
        expected_skill="parent-skill",
        expected_repository="owner/repository",
    ) == []


def test_provenance_schema_rejects_unsafe_managed_path_and_dependency_mismatch() -> None:
    payload = valid_payload()
    payload["managed_files"] = [
        {"path": "../escape", "size": 1, "sha256": DIGEST},
    ]
    payload["dependency_digests"] = {"other-skill": DIGEST}

    issues = validate_provenance_payload(payload)

    assert any("safe relative path" in issue for issue in issues)
    assert any("exactly match dependencies" in issue for issue in issues)


def test_provenance_schema_rejects_dependency_path_traversal() -> None:
    payload = valid_payload()
    payload["dependencies"] = ["../outside-skill"]
    payload["dependency_digests"] = {"../outside-skill": DIGEST}

    issues = validate_provenance_payload(payload)

    assert "dependencies must be a list of canonical lowercase Skill names" in issues


def test_known_dirty_state_requires_source_commit() -> None:
    payload = valid_payload()
    payload["source_commit"] = None

    issues = validate_provenance_payload(payload)

    assert "source_commit is required when source_dirty is known" in issues


def test_source_and_compatibility_digests_must_match_installed_payload() -> None:
    payload = valid_payload()
    payload["source_tree_digest"] = "c" * 64
    payload["content_digest"] = "d" * 64

    issues = validate_provenance_payload(payload)

    assert "source_tree_digest must match installed_content_digest" in issues
    assert "content_digest must match installed_content_digest" in issues


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks are unavailable")
def test_file_records_rejects_payload_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "skill"
    root.mkdir()
    (root / "SKILL.md").write_text("content\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (root / "linked.txt").symlink_to(outside)

    with pytest.raises(ValueError, match="must not contain symlinks"):
        file_records(root)
