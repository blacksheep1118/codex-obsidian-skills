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


@pytest.mark.parametrize("verify_package", (False, True))
def test_candidate_package_verification_is_explicit_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verify_package: bool
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(validate_notes_candidate, "verify_repository_identity", lambda *_a, **_k: None)
    monkeypatch.setattr(validate_notes_candidate, "resolve_commit", lambda *_a, **_k: "c" * 40)
    monkeypatch.setattr(validate_notes_candidate, "verify_target_tree", lambda *_a, **_k: TARGET)
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
    if verify_package:
        assert calls[2:] == ["candidate Notes package", "candidate Notes package verification"]
        assert report["notes_package_entries"] == 17
    else:
        assert len(calls) == 2
        assert report["notes_package_entries"] is None
    assert report["package_verified"] is verify_package
