from __future__ import annotations

import json
from pathlib import Path

import pytest
import validate_notes_candidate

TARGET = {
    "contract_version": 2,
    "skills": {"solvenotes-vault-maintainer": {"content_digest": "a" * 64}},
    "dependency_graph_digest": "b" * 64,
}


def _patch_candidate_runner(monkeypatch: pytest.MonkeyPatch, run) -> None:
    monkeypatch.setattr(validate_notes_candidate, "verify_repository_identity", lambda *_a, **_k: None)
    monkeypatch.setattr(validate_notes_candidate, "resolve_commit", lambda *_a, **_k: "c" * 40)
    monkeypatch.setattr(validate_notes_candidate, "verify_target_tree", lambda *_a, **_k: TARGET)
    monkeypatch.setattr(validate_notes_candidate, "_add_detached_worktree", lambda *_a, **_k: None)
    monkeypatch.setattr(validate_notes_candidate, "_remove_worktree", lambda *_a, **_k: None)
    monkeypatch.setattr(validate_notes_candidate, "_run", run)


def test_candidate_cli_defaults_to_full_and_accepts_explicit_basic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[str] = []

    def fake_validate(*_args, **kwargs):
        profile = kwargs["validation_profile"]
        seen.append(profile)
        return {
            "ok": True,
            "validation_profile": profile,
            "source_audit": "NOT_RUN" if profile == "vault-basic" else "PASS",
        }

    monkeypatch.setattr(validate_notes_candidate, "validate_candidate", fake_validate)
    base = [
        "--notes-root", str(tmp_path / "notes"),
        "--skills-root", str(tmp_path / "skills"),
        "--skills-ref", "candidate",
    ]
    assert validate_notes_candidate.main(base) == 0
    default_report = json.loads(capsys.readouterr().out)
    assert default_report["validation_profile"] == "vault-full"
    assert default_report["source_audit"] == "PASS"

    assert validate_notes_candidate.main(base + ["--validation-profile", "vault-basic"]) == 0
    basic_report = json.loads(capsys.readouterr().out)
    assert basic_report["validation_profile"] == "vault-basic"
    assert basic_report["source_audit"] == "NOT_RUN"
    assert seen == ["vault-full", "vault-basic"]


def test_default_full_profile_requires_an_explicit_manifest_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SOLVENOTES_MANIFEST_ROOT", raising=False)
    with pytest.raises(ValueError, match="explicit SOLVENOTES_MANIFEST_ROOT"):
        validate_notes_candidate.validate_candidate(
            tmp_path / "notes", tmp_path / "skills", "main",
            verify_level="full", python_bin="python3", allow_local_source=True,
        )


def test_basic_profile_runs_basic_gate_and_marks_source_audit_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, list[str]]] = []
    def fake_run(command, *, cwd, env, timeout, label):
        del cwd, env, timeout
        calls.append((label, command))

    monkeypatch.delenv("SOLVENOTES_MANIFEST_ROOT", raising=False)
    _patch_candidate_runner(monkeypatch, fake_run)
    report = validate_notes_candidate.validate_candidate(
        tmp_path / "notes", tmp_path / "skills", "main",
        verify_level="full", python_bin="python3", allow_local_source=True,
        validation_profile="vault-basic",
    )
    assert calls[1][0] == "candidate real Notes vault-basic"
    assert calls[1][1][-1] == "vault-basic"
    assert report["validation_profile"] == "vault-basic"
    assert report["source_audit"] == "NOT_RUN"


def test_full_candidate_propagates_empty_manifest_gate_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_root = tmp_path / "empty-manifest-root"
    manifest_root.mkdir()
    monkeypatch.setenv("SOLVENOTES_MANIFEST_ROOT", str(manifest_root))
    calls: list[str] = []
    def fake_run(command, *, cwd, env, timeout, label):
        del command, cwd, env, timeout
        calls.append(label)
        if label == "candidate real Notes vault-full":
            raise ValueError("SOURCE_MANIFESTS_MISSING")

    _patch_candidate_runner(monkeypatch, fake_run)
    with pytest.raises(ValueError, match="SOURCE_MANIFESTS_MISSING"):
        validate_notes_candidate.validate_candidate(
            tmp_path / "notes", tmp_path / "skills", "main",
            verify_level="full", python_bin="python3", allow_local_source=True,
        )
    assert calls == ["candidate installed smoke", "candidate real Notes vault-full"]


@pytest.mark.parametrize("verify_package", (False, True))
def test_candidate_package_verification_is_explicit_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verify_package: bool
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(validate_notes_candidate, "verify_repository_identity", lambda *_a, **_k: None)
    monkeypatch.setattr(validate_notes_candidate, "resolve_commit", lambda *_a, **_k: "c" * 40)
    monkeypatch.setattr(validate_notes_candidate, "verify_target_tree", lambda *_a, **_k: TARGET)
    manifest_root = tmp_path / "manifest-root"
    manifest_root.mkdir()
    monkeypatch.setenv("SOLVENOTES_MANIFEST_ROOT", str(manifest_root))
    monkeypatch.setattr(validate_notes_candidate, "_add_detached_worktree", lambda *_a, **_k: None)
    monkeypatch.setattr(validate_notes_candidate, "_remove_worktree", lambda *_a, **_k: None)

    def fake_run(
        command: list[str], *, cwd: Path, env: dict[str, str], timeout: int, label: str
    ) -> None:
        del cwd, env, timeout
        calls.append(label)
        if label == "candidate Notes package":
            manifest = Path(command[command.index("--manifest-output") + 1])
            manifest.write_text(json.dumps({"archive_entry_count": 17}), encoding="utf-8")

    monkeypatch.setattr(validate_notes_candidate, "_run", fake_run)

    report = validate_notes_candidate.validate_candidate(
        tmp_path / "notes",
        tmp_path / "skills",
        "main",
        verify_level="full",
        python_bin="python3",
        allow_local_source=True,
        verify_package=verify_package,
    )

    assert calls[:2] == ["candidate installed smoke", "candidate real Notes vault-full"]
    assert report["validation_profile"] == "vault-full"
    assert report["source_audit"] == "PASS"
    if verify_package:
        assert calls[2:] == ["candidate Notes package", "candidate Notes package verification"]
        assert report["notes_package_entries"] == 17
    else:
        assert len(calls) == 2
        assert report["notes_package_entries"] is None
    assert report["package_verified"] is verify_package
