from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

import pytest

from scripts import verify_pptx


def fake_render_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        verify_pptx.shutil,
        "which",
        lambda name: f"/fake/{name}" if name in {"soffice", "pdftoppm", "pdfinfo"} else None,
    )


def test_render_pptx_cleans_libreoffice_profile_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "render"
    seen_profiles: list[Path] = []

    def fake_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        seen_profiles.extend(tmp_path.glob("scientific-deck-lo-*"))
        executable = Path(command[0]).name
        if executable == "soffice":
            pdf_dir = Path(command[command.index("--outdir") + 1])
            (pdf_dir / "deck.pdf").write_bytes(b"%PDF")
            return subprocess.CompletedProcess(command, 0, stdout="")
        if executable == "pdfinfo":
            return subprocess.CompletedProcess(command, 0, stdout="Pages: 1\n")
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_run)

    verify_pptx.render_pptx(pptx, output_dir, expected_slides=1, require_render=True)

    assert seen_profiles
    assert all(not path.exists() for path in seen_profiles)


def test_render_pptx_cleans_libreoffice_profile_after_subprocess_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    seen_profiles: list[Path] = []

    def failing_run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        seen_profiles.extend(tmp_path.glob("scientific-deck-lo-*"))
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(verify_pptx.subprocess, "run", failing_run)

    with pytest.raises(subprocess.CalledProcessError):
        verify_pptx.render_pptx(pptx, tmp_path / "render", expected_slides=1, require_render=True)

    assert seen_profiles
    assert all(not path.exists() for path in seen_profiles)
