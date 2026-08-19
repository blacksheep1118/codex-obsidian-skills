from __future__ import annotations

import errno
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

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


@pytest.mark.parametrize(
    ("flag", "required"),
    [("--render", False), ("--require-render", True)],
)
def test_render_flags_invoke_render_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
    required: bool,
) -> None:
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    presentation = SimpleNamespace(
        slides=[object()],
        slide_width=12192000,
        slide_height=6858000,
    )
    calls: list[tuple[Path, Path, int | None, bool]] = []
    monkeypatch.setattr(verify_pptx, "package_slide_count", lambda _path: 1)
    monkeypatch.setattr(verify_pptx, "reopen_presentation", lambda _path: presentation)
    monkeypatch.setattr(
        verify_pptx,
        "render_pptx",
        lambda path, output_dir, expected, require: calls.append(
            (path, output_dir, expected, require)
        ),
    )

    assert verify_pptx.main([str(pptx), flag]) == 0
    assert calls == [(pptx, tmp_path / "deck-render", 1, required)]


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


def test_render_pptx_replaces_owned_page_set_and_removes_stale_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    (output_dir / "deck.pdf").write_bytes(b"old PDF")
    (output_dir / "slide-1.png").write_bytes(b"old page 1")
    (output_dir / "slide-2.png").write_bytes(b"stale page 2")

    verify_pptx.render_pptx(
        pptx,
        output_dir,
        expected_slides=1,
        require_render=True,
    )

    assert (output_dir / "deck.pdf").read_bytes() == b"%PDF"
    assert (output_dir / "slide-1.png").read_bytes() == b"PNG"
    assert not (output_dir / "slide-2.png").exists()
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "deck.pdf",
        "slide-1.png",
    ]
    assert list(tmp_path.glob(".deck-render-stage-*")) == []


@pytest.mark.parametrize("stale_name", ["Slide-2.PNG", "sLiDe-003.PnG"])
def test_render_pptx_removes_case_variant_stale_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stale_name: str,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    stale = output_dir / stale_name
    stale.write_bytes(b"stale page")

    verify_pptx.render_pptx(
        pptx,
        output_dir,
        expected_slides=1,
        require_render=True,
    )

    assert not stale.exists()
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "deck.pdf",
        "slide-1.png",
    ]


@pytest.mark.parametrize(
    "unrelated_name",
    [
        "slide-x.png",
        "slide-١.png",
        "slide-１.png",
        "slide-².png",
    ],
    ids=("letter", "arabic-indic", "fullwidth", "superscript"),
)
def test_render_pptx_preserves_non_ascii_or_non_decimal_slide_named_png(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unrelated_name: str,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    unrelated = output_dir / unrelated_name
    unrelated.write_bytes(b"not a numbered preview")

    verify_pptx.render_pptx(
        pptx,
        output_dir,
        expected_slides=1,
        require_render=True,
    )

    assert unrelated.read_bytes() == b"not a numbered preview"


def test_indexed_slide_targets_keeps_ascii_zero_padded_page_identity(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "render"
    output_dir.mkdir()
    padded = output_dir / "slide-001.png"
    padded.write_bytes(b"padded")

    assert verify_pptx.indexed_slide_targets(tmp_path, output_dir) == {1: padded}

    (output_dir / "slide-1.png").write_bytes(b"plain")
    with pytest.raises(ValueError, match="duplicate page 1"):
        verify_pptx.indexed_slide_targets(tmp_path, output_dir)


def test_render_pptx_replaces_case_variant_current_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    prior = output_dir / "SLIDE-1.PNG"
    prior.write_bytes(b"old page")

    verify_pptx.render_pptx(
        pptx,
        output_dir,
        expected_slides=1,
        require_render=True,
    )

    assert (output_dir / "slide-1.png").read_bytes() == b"PNG"
    assert sorted(
        path.name for path in output_dir.iterdir() if path.name.casefold() == "slide-1.png"
    ) == ["slide-1.png"]


def test_indexed_slide_targets_rejects_case_variant_duplicate_page(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "render"
    output_dir.mkdir()
    lower = output_dir / "slide-1.png"
    upper = output_dir / "SLIDE-01.PNG"
    lower.write_bytes(b"first")
    upper.write_bytes(b"second")
    if lower.samefile(upper):
        pytest.skip("filesystem does not permit distinct case-variant page entries")

    with pytest.raises(ValueError, match="duplicate page 1"):
        verify_pptx.indexed_slide_targets(tmp_path, output_dir)


@pytest.mark.parametrize("generated_name", ["deck.pdf", "slide-1.png"])
def test_render_pptx_breaks_existing_hardlink_without_mutating_external_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    generated_name: str,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    sentinel = tmp_path / f"outside-{generated_name}"
    sentinel.write_bytes(b"external")
    generated = output_dir / generated_name
    os.link(sentinel, generated)

    verify_pptx.render_pptx(
        pptx,
        output_dir,
        expected_slides=1,
        require_render=True,
    )

    assert sentinel.read_bytes() == b"external"
    assert generated.stat().st_ino != sentinel.stat().st_ino
    assert generated.read_bytes() == (b"%PDF" if generated_name == "deck.pdf" else b"PNG")


def test_render_pptx_renderer_failure_preserves_previous_complete_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_render_tools(monkeypatch)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    previous = {
        "deck.pdf": b"old PDF",
        "slide-1.png": b"old page 1",
        "slide-2.png": b"old page 2",
    }
    for name, payload in previous.items():
        (output_dir / name).write_bytes(payload)

    def failing_renderer(
        command: list[str],
        **kwargs,
    ) -> subprocess.CompletedProcess[str]:
        if Path(command[0]).name == "pdftoppm":
            raise subprocess.CalledProcessError(1, command)
        return fake_successful_render(command, **kwargs)

    monkeypatch.setattr(verify_pptx.subprocess, "run", failing_renderer)

    with pytest.raises(subprocess.CalledProcessError):
        verify_pptx.render_pptx(
            pptx,
            output_dir,
            expected_slides=1,
            require_render=True,
        )

    assert {
        path.name: path.read_bytes()
        for path in output_dir.iterdir()
    } == previous
    assert list(tmp_path.glob(".deck-render-stage-*")) == []


@pytest.mark.parametrize(
    ("reported_pages", "rendered_pages"),
    [(2, (1,)), (1, (1, 2))],
    ids=("missing-page", "extra-page"),
)
def test_render_pptx_requires_png_page_set_to_match_pdf_before_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reported_pages: int,
    rendered_pages: tuple[int, ...],
) -> None:
    fake_render_tools(monkeypatch)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    (output_dir / "deck.pdf").write_bytes(b"old PDF")
    (output_dir / "slide-1.png").write_bytes(b"old page 1")

    def mismatched_render(
        command: list[str],
        **kwargs,
    ) -> subprocess.CompletedProcess[str]:
        executable = Path(command[0]).name
        if executable == "pdfinfo":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"Pages: {reported_pages}\n",
            )
        if executable == "pdftoppm":
            prefix = Path(command[-1])
            for page in rendered_pages:
                prefix.with_name(f"{prefix.name}-{page}.png").write_bytes(b"PNG")
            return subprocess.CompletedProcess(command, 0, stdout="")
        return fake_successful_render(command, **kwargs)

    monkeypatch.setattr(verify_pptx.subprocess, "run", mismatched_render)

    with pytest.raises(RuntimeError, match="PNG page set"):
        verify_pptx.render_pptx(
            pptx,
            output_dir,
            expected_slides=reported_pages,
            require_render=True,
        )

    assert (output_dir / "deck.pdf").read_bytes() == b"old PDF"
    assert (output_dir / "slide-1.png").read_bytes() == b"old page 1"
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "deck.pdf",
        "slide-1.png",
    ]


@pytest.mark.parametrize(
    ("fail_after", "failure_type"),
    [
        (1, RuntimeError),
        (4, RuntimeError),
        (5, RuntimeError),
        (1, KeyboardInterrupt),
        (4, KeyboardInterrupt),
        (5, KeyboardInterrupt),
    ],
    ids=(
        "exception-after-backup-pdf",
        "exception-after-publish-pdf",
        "exception-after-publish-png",
        "interrupt-after-backup-pdf",
        "interrupt-after-publish-pdf",
        "interrupt-after-publish-png",
    ),
)
def test_render_publish_rolls_back_after_completed_move_is_interrupted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_after: int,
    failure_type: type[BaseException],
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    previous = {
        "deck.pdf": b"old PDF",
        "slide-1.png": b"old page 1",
        "slide-2.png": b"old page 2",
    }
    for name, payload in previous.items():
        (output_dir / name).write_bytes(payload)
    real_replace = verify_pptx.os.replace
    replace_count = 0

    def interrupting_replace(*args, **kwargs):
        nonlocal replace_count
        result = real_replace(*args, **kwargs)
        replace_count += 1
        if replace_count == fail_after:
            raise failure_type("injected after completed move")
        return result

    monkeypatch.setattr(verify_pptx.os, "replace", interrupting_replace)

    with pytest.raises(failure_type, match="injected"):
        verify_pptx.render_pptx(
            pptx,
            output_dir,
            expected_slides=1,
            require_render=True,
        )

    assert {
        path.name: path.read_bytes()
        for path in output_dir.iterdir()
    } == previous
    assert list(tmp_path.glob(".deck-render-stage-*")) == []


@pytest.mark.parametrize(
    "fail_before",
    [1, 4, 5],
    ids=("before-backup-pdf", "before-publish-pdf", "before-publish-png"),
)
def test_render_publish_rolls_back_when_move_fails_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_before: int,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    previous = {
        "deck.pdf": b"old PDF",
        "slide-1.png": b"old page 1",
        "slide-2.png": b"old page 2",
    }
    for name, payload in previous.items():
        (output_dir / name).write_bytes(payload)
    real_replace = verify_pptx.os.replace
    replace_count = 0

    def rejecting_replace(*args, **kwargs):
        nonlocal replace_count
        replace_count += 1
        if replace_count == fail_before:
            raise RuntimeError("injected before move")
        return real_replace(*args, **kwargs)

    monkeypatch.setattr(verify_pptx.os, "replace", rejecting_replace)

    with pytest.raises(RuntimeError, match="before move"):
        verify_pptx.render_pptx(
            pptx,
            output_dir,
            expected_slides=1,
            require_render=True,
        )

    assert {path.name: path.read_bytes() for path in output_dir.iterdir()} == previous
    assert list(tmp_path.glob(".deck-render-stage-*")) == []


@pytest.mark.parametrize("fail_on_open", [2, 3])
@pytest.mark.parametrize("failure_type", [RuntimeError, KeyboardInterrupt, SystemExit])
def test_render_publish_closes_acquired_fds_when_directory_open_is_interrupted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_on_open: int,
    failure_type: type[BaseException],
) -> None:
    if os.name == "nt":
        pytest.skip("Windows publish does not use directory file descriptors")
    output_dir = tmp_path / "render"
    staging_dir = tmp_path / "staging"
    backup_dir = tmp_path / "backup"
    for directory in (output_dir, staging_dir, backup_dir):
        directory.mkdir()
    previous = {"deck.pdf": b"old PDF", "slide-1.png": b"old page"}
    staged = {"deck.pdf": b"new PDF", "slide-1.png": b"new page"}
    for name, payload in previous.items():
        (output_dir / name).write_bytes(payload)
    for name, payload in staged.items():
        (staging_dir / name).write_bytes(payload)

    real_open = verify_pptx.open_directory_fd
    real_fstat = verify_pptx.os.fstat
    opened: list[int] = []
    calls = 0

    def interrupted_open(path: Path) -> int | None:
        nonlocal calls
        calls += 1
        if calls == fail_on_open:
            raise failure_type("injected directory-open interruption")
        descriptor = real_open(path)
        assert descriptor is not None
        opened.append(descriptor)
        return descriptor

    monkeypatch.setattr(verify_pptx, "open_directory_fd", interrupted_open)

    with pytest.raises(failure_type, match="directory-open interruption"):
        verify_pptx.publish_render_outputs(
            tmp_path,
            output_dir,
            verify_pptx.directory_identity(output_dir),
            staging_dir / "deck.pdf",
            [staging_dir / "slide-1.png"],
            backup_dir,
        )

    for descriptor in opened:
        with pytest.raises(OSError) as exc_info:
            real_fstat(descriptor)
        assert exc_info.value.errno == errno.EBADF
    assert {path.name: path.read_bytes() for path in output_dir.iterdir()} == previous
    assert {path.name: path.read_bytes() for path in staging_dir.iterdir()} == staged
    assert list(backup_dir.iterdir()) == []


@pytest.mark.parametrize("fail_on_fstat", [1, 2, 3])
@pytest.mark.parametrize("failure_type", [RuntimeError, KeyboardInterrupt, SystemExit])
def test_render_publish_closes_all_fds_when_identity_check_is_interrupted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_on_fstat: int,
    failure_type: type[BaseException],
) -> None:
    if os.name == "nt":
        pytest.skip("Windows publish does not use directory file descriptors")
    output_dir = tmp_path / "render"
    staging_dir = tmp_path / "staging"
    backup_dir = tmp_path / "backup"
    for directory in (output_dir, staging_dir, backup_dir):
        directory.mkdir()
    previous = {"deck.pdf": b"old PDF", "slide-1.png": b"old page"}
    staged = {"deck.pdf": b"new PDF", "slide-1.png": b"new page"}
    for name, payload in previous.items():
        (output_dir / name).write_bytes(payload)
    for name, payload in staged.items():
        (staging_dir / name).write_bytes(payload)

    real_open = verify_pptx.open_directory_fd
    real_fstat = verify_pptx.os.fstat
    opened: list[int] = []
    fstat_calls = 0

    def tracking_open(path: Path) -> int | None:
        descriptor = real_open(path)
        assert descriptor is not None
        opened.append(descriptor)
        return descriptor

    def interrupted_fstat(descriptor: int):
        nonlocal fstat_calls
        fstat_calls += 1
        if fstat_calls == fail_on_fstat:
            raise failure_type("injected identity-check interruption")
        return real_fstat(descriptor)

    monkeypatch.setattr(verify_pptx, "open_directory_fd", tracking_open)
    monkeypatch.setattr(verify_pptx.os, "fstat", interrupted_fstat)

    with pytest.raises(failure_type, match="identity-check interruption"):
        verify_pptx.publish_render_outputs(
            tmp_path,
            output_dir,
            verify_pptx.directory_identity(output_dir),
            staging_dir / "deck.pdf",
            [staging_dir / "slide-1.png"],
            backup_dir,
        )

    for descriptor in opened:
        with pytest.raises(OSError) as exc_info:
            real_fstat(descriptor)
        assert exc_info.value.errno == errno.EBADF
    assert {path.name: path.read_bytes() for path in output_dir.iterdir()} == previous
    assert {path.name: path.read_bytes() for path in staging_dir.iterdir()} == staged
    assert list(backup_dir.iterdir()) == []


def test_render_publish_preserves_conflict_and_recovery_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    (output_dir / "deck.pdf").write_bytes(b"old PDF")
    (output_dir / "slide-1.png").write_bytes(b"old page 1")
    real_replace = verify_pptx.os.replace
    injected = False

    def conflicting_replace(*args, **kwargs):
        nonlocal injected
        result = real_replace(*args, **kwargs)
        if not injected:
            injected = True
            (output_dir / "deck.pdf").write_bytes(b"CONFLICT")
            raise RuntimeError("injected conflict")
        return result

    monkeypatch.setattr(verify_pptx.os, "replace", conflicting_replace)

    with pytest.raises(
        verify_pptx.RenderPublishRecoveryError,
        match="need recovery",
    ):
        verify_pptx.render_pptx(
            pptx,
            output_dir,
            expected_slides=1,
            require_render=True,
        )

    assert (output_dir / "deck.pdf").read_bytes() == b"CONFLICT"
    assert (output_dir / "slide-1.png").read_bytes() == b"old page 1"
    transactions = list(tmp_path.glob(".deck-render-stage-*"))
    assert len(transactions) == 1
    assert (transactions[0] / "backup/deck.pdf").read_bytes() == b"old PDF"


@pytest.mark.parametrize("alias_target", ["outside", "same-inode"], ids=("outside-symlink", "same-inode-alias"))
def test_render_publish_parent_swap_never_writes_through_new_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    alias_target: str,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"
    output_dir.mkdir()
    previous = {
        "deck.pdf": b"old PDF",
        "slide-1.png": b"old page 1",
    }
    for name, payload in previous.items():
        (output_dir / name).write_bytes(payload)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel.txt").write_text("unchanged", encoding="utf-8")
    detached = tmp_path / "detached-render"
    real_replace = verify_pptx.os.replace
    swapped = False

    def swapping_replace(*args, **kwargs):
        nonlocal swapped
        if not swapped:
            output_dir.rename(detached)
            output_dir.symlink_to(
                outside if alias_target == "outside" else detached,
                target_is_directory=True,
            )
            swapped = True
        return real_replace(*args, **kwargs)

    monkeypatch.setattr(verify_pptx.os, "replace", swapping_replace)

    with pytest.raises(ValueError, match="symlink|identity"):
        verify_pptx.render_pptx(
            pptx,
            output_dir,
            expected_slides=1,
            require_render=True,
        )

    assert {
        path.name: path.read_bytes()
        for path in detached.iterdir()
    } == previous
    assert (outside / "sentinel.txt").read_text(encoding="utf-8") == "unchanged"
    assert not (outside / "deck.pdf").exists()
    assert not (outside / "slide-1.png").exists()
    assert list(tmp_path.glob(".deck-render-stage-*")) == []


def test_render_publish_reports_committed_output_when_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_render_tools(monkeypatch)
    monkeypatch.setattr(verify_pptx.subprocess, "run", fake_successful_render)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"placeholder")
    output_dir = tmp_path / "deck-render"

    real_rmtree = verify_pptx.shutil.rmtree

    def fail_cleanup(path, *args, **kwargs):
        if Path(path).name.startswith(".deck-render-stage-"):
            raise OSError("injected cleanup failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(verify_pptx.shutil, "rmtree", fail_cleanup)

    with pytest.raises(RuntimeError, match="outputs were committed"):
        verify_pptx.render_pptx(
            pptx,
            output_dir,
            expected_slides=1,
            require_render=True,
        )

    assert (output_dir / "deck.pdf").read_bytes() == b"%PDF"
    assert (output_dir / "slide-1.png").read_bytes() == b"PNG"


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
            output_dir.rename(tmp_path / "detached-render")
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
