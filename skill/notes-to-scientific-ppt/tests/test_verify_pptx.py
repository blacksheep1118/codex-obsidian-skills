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


def fake_successful_render(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
    executable = Path(command[0]).name
    if executable == "soffice":
        pdf_dir = Path(command[command.index("--outdir") + 1])
        (pdf_dir / "deck.pdf").write_bytes(b"%PDF")
        return subprocess.CompletedProcess(command, 0, stdout="")
    if executable == "pdfinfo":
        return subprocess.CompletedProcess(command, 0, stdout="Pages: 1\n")
    if executable == "pdftoppm":
        prefix = Path(command[-1])
        prefix.with_name(f"{prefix.name}-1.png").write_bytes(b"PNG")
    return subprocess.CompletedProcess(command, 0, stdout="")


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
        return fake_successful_render(command, **_kwargs)

    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_run)

    verify_pptx.render_pptx(pptx, output_dir, expected_slides=1, require_render=True)

    assert seen_profiles
    assert all(not path.exists() for path in seen_profiles)


def test_render_pptx_rejects_symlinked_render_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    outside = tmp_path / "outside"
    outside.mkdir()
    output_dir = tmp_path / "deck-render"
    output_dir.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        verify_pptx.render_pptx(pptx, output_dir, expected_slides=1, require_render=True)

    assert list(outside.iterdir()) == []


def test_render_pptx_supports_explicit_parent_path_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    (actual / "deck.pptx").write_bytes(b"placeholder")

    verify_pptx.render_pptx(
        alias / "deck.pptx",
        alias / "deck-render",
        expected_slides=1,
        require_render=True,
    )

    assert (actual / "deck-render" / "deck.pdf").is_file()
    assert (actual / "deck-render" / "slide-1.png").is_file()


@pytest.mark.parametrize("dangling", [False, True])
def test_render_pptx_rejects_existing_and_dangling_pdf_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dangling: bool,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    outside = tmp_path / "outside.pdf"
    if not dangling:
        outside.write_bytes(b"external")
    (output_dir / "deck.pdf").symlink_to(outside)

    with pytest.raises(ValueError, match="symlink"):
        verify_pptx.render_pptx(pptx, output_dir, expected_slides=1, require_render=True)

    assert not outside.exists() if dangling else outside.read_bytes() == b"external"


@pytest.mark.parametrize("dangling", [False, True])
def test_render_pptx_rejects_existing_and_dangling_png_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dangling: bool,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    outside = tmp_path / "outside.png"
    if not dangling:
        outside.write_bytes(b"external")
    (output_dir / "slide-1.png").symlink_to(outside)

    with pytest.raises(ValueError, match="symlink"):
        verify_pptx.render_pptx(pptx, output_dir, expected_slides=1, require_render=True)

    assert not outside.exists() if dangling else outside.read_bytes() == b"external"


def test_render_pptx_rechecks_render_directory_after_pdfinfo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_render_tools(monkeypatch)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    renderer_calls: list[list[str]] = []

    def swapping_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        executable = Path(command[0]).name
        if executable == "pdfinfo":
            (output_dir / "deck.pdf").unlink()
            output_dir.rmdir()
            output_dir.symlink_to(outside, target_is_directory=True)
            return subprocess.CompletedProcess(command, 0, stdout="Pages: 1\n")
        if executable == "pdftoppm":
            renderer_calls.append(command)
        return fake_successful_render(command, **kwargs)

    monkeypatch.setattr(verify_pptx.subprocess, "run", swapping_run)

    with pytest.raises(ValueError, match="symlink|identity"):
        verify_pptx.render_pptx(pptx, output_dir, expected_slides=1, require_render=True)

    assert renderer_calls == []
    assert sentinel.read_text(encoding="utf-8") == "unchanged"
    assert not (outside / "slide-1.png").exists()


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
