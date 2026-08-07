#!/usr/bin/env python3
"""Reopen a generated PPTX, verify slide count, and optionally render it."""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from zipfile import ZipFile


SLIDE_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")


def package_slide_count(path: Path) -> int:
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"PPTX contains a corrupt ZIP member: {archive.testzip()}")
        names = set(archive.namelist())
        required = {"[Content_Types].xml", "ppt/presentation.xml"}
        missing = sorted(required - names)
        if missing:
            raise ValueError(f"PPTX is missing required parts: {', '.join(missing)}")
        slide_numbers = sorted(int(match.group(1)) for name in names if (match := SLIDE_RE.match(name)))
    if slide_numbers != list(range(1, len(slide_numbers) + 1)):
        raise ValueError(f"PPTX slide parts are not contiguous: {slide_numbers}")
    return len(slide_numbers)


def reopen_presentation(path: Path):
    try:
        from pptx import Presentation
    except ModuleNotFoundError as exc:
        raise RuntimeError("python-pptx is required for the reopen gate") from exc
    return Presentation(str(path))


def slide_count(presentation) -> int:
    return len(presentation.slides)


def first_slide_text(presentation) -> str:
    if not presentation.slides:
        return ""
    return "\n".join(
        shape.text.strip()
        for shape in presentation.slides[0].shapes
        if getattr(shape, "has_text_frame", False) and shape.text.strip()
    )


def relative_beneath(root: Path, path: Path) -> Path:
    root = root.resolve()
    candidate = Path(os.path.abspath(path.expanduser()))
    try:
        return candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"render output must remain beside the PPTX: {path}") from exc


def ensure_safe_directory(root: Path, path: Path, *, create: bool) -> Path:
    root = root.resolve()
    relative = relative_beneath(root, path)
    current = root
    for component in relative.parts:
        current = current / component
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            if not create:
                break
            current.mkdir()
            mode = current.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"render directory contains symlink component: {current}")
        if not stat.S_ISDIR(mode):
            raise ValueError(f"render directory component is not a directory: {current}")
    return root / relative


def ensure_safe_generated_file(root: Path, path: Path) -> Path:
    root = root.resolve()
    relative = relative_beneath(root, path)
    candidate = root / relative
    ensure_safe_directory(root, candidate.parent, create=False)
    try:
        mode = candidate.lstat().st_mode
    except FileNotFoundError:
        return candidate
    if stat.S_ISLNK(mode):
        raise ValueError(f"generated render path is a symlink: {candidate}")
    if not stat.S_ISREG(mode):
        raise ValueError(f"generated render path is not a regular file: {candidate}")
    return candidate


def directory_identity(path: Path) -> tuple[int, int]:
    mode = path.lstat()
    if stat.S_ISLNK(mode.st_mode) or not stat.S_ISDIR(mode.st_mode):
        raise ValueError(f"render directory is not a regular directory: {path}")
    return mode.st_dev, mode.st_ino


def revalidate_render_directory(
    root: Path,
    output_dir: Path,
    expected_identity: tuple[int, int],
) -> Path:
    safe_output = ensure_safe_directory(root, output_dir, create=False)
    if directory_identity(safe_output) != expected_identity:
        raise ValueError(f"render directory identity changed during rendering: {safe_output}")
    return safe_output


def validate_slide_targets(root: Path, output_dir: Path) -> None:
    for path in output_dir.iterdir():
        if path.name.startswith("slide-") and path.suffix.lower() == ".png":
            ensure_safe_generated_file(root, path)


def render_pptx(path: Path, output_dir: Path, expected_slides: int | None, require_render: bool) -> None:
    converter = shutil.which("soffice") or shutil.which("libreoffice")
    renderer = shutil.which("pdftoppm")
    pdfinfo = shutil.which("pdfinfo")
    if converter is None or renderer is None or pdfinfo is None:
        message = "LibreOffice/Poppler render tools are unavailable"
        if require_render:
            raise RuntimeError(f"MANUAL_REVIEW_REQUIRED: {message}")
        print(f"MANUAL_REVIEW_REQUIRED: {message}")
        return

    selected_root = Path(os.path.abspath(path.parent.expanduser()))
    selected_output = Path(os.path.abspath(output_dir.expanduser()))
    try:
        output_relative = selected_output.relative_to(selected_root)
    except ValueError as exc:
        raise ValueError(f"render output must remain beside the PPTX: {output_dir}") from exc
    render_root = path.parent.expanduser().resolve()
    output_dir = ensure_safe_directory(render_root, render_root / output_relative, create=True)
    render_identity = directory_identity(output_dir)
    pdf = ensure_safe_generated_file(render_root, output_dir / f"{path.stem}.pdf")
    validate_slide_targets(render_root, output_dir)
    with tempfile.TemporaryDirectory(prefix="scientific-deck-lo-") as profile_name:
        profile_dir = Path(profile_name)
        subprocess.run(
            [
                converter,
                "--headless",
                f"-env:UserInstallation={profile_dir.as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    output_dir = revalidate_render_directory(render_root, output_dir, render_identity)
    pdf = ensure_safe_generated_file(render_root, pdf)
    if not pdf.is_file():
        raise RuntimeError(f"LibreOffice did not create {pdf}")
    info = subprocess.run([pdfinfo, str(pdf)], check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output_dir = revalidate_render_directory(render_root, output_dir, render_identity)
    pdf = ensure_safe_generated_file(render_root, pdf)
    pages_match = re.search(r"^Pages:\s*(\d+)\s*$", info.stdout, re.M)
    if pages_match is None:
        raise RuntimeError("pdfinfo did not report a page count")
    pages = int(pages_match.group(1))
    if expected_slides is not None and pages != expected_slides:
        raise RuntimeError(f"rendered PDF has {pages} pages; expected {expected_slides}")
    output_dir = revalidate_render_directory(render_root, output_dir, render_identity)
    pdf = ensure_safe_generated_file(render_root, pdf)
    validate_slide_targets(render_root, output_dir)
    subprocess.run([renderer, "-png", str(pdf), str(output_dir / "slide")], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output_dir = revalidate_render_directory(render_root, output_dir, render_identity)
    pdf = ensure_safe_generated_file(render_root, pdf)
    validate_slide_targets(render_root, output_dir)
    print(f"render ok pdf={pdf} pages={pages}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--expected-slides", type=int)
    parser.add_argument("--expected-title")
    parser.add_argument("--expected-width-inches", type=float)
    parser.add_argument("--expected-height-inches", type=float)
    parser.add_argument("--render", action="store_true", help="render to PDF and PNG previews when tools are available")
    parser.add_argument("--require-render", action="store_true", help="fail instead of reporting manual review when render tools are unavailable")
    args = parser.parse_args(argv)
    try:
        package_slides = package_slide_count(args.pptx)
        presentation = reopen_presentation(args.pptx)
        reopened_slides = slide_count(presentation)
        if package_slides != reopened_slides:
            raise RuntimeError(f"package has {package_slides} slides but python-pptx reopened {reopened_slides}")
        if args.expected_slides is not None and reopened_slides != args.expected_slides:
            raise RuntimeError(f"reopened PPTX has {reopened_slides} slides; expected {args.expected_slides}")
        if args.expected_title and not first_slide_text(presentation).startswith(args.expected_title):
            raise RuntimeError(f"first-slide title does not start with expected title {args.expected_title!r}")
        for label, expected, actual in (
            ("width", args.expected_width_inches, presentation.slide_width / 914400),
            ("height", args.expected_height_inches, presentation.slide_height / 914400),
        ):
            if expected is not None and not math.isclose(actual, expected, rel_tol=0, abs_tol=0.01):
                raise RuntimeError(f"slide {label} is {actual:.3f} inches; expected {expected:.3f}")
        print(f"pptx_reopen ok slides={reopened_slides}")
        if args.render:
            render_pptx(args.pptx, args.pptx.parent / f"{args.pptx.stem}-render", args.expected_slides or reopened_slides, args.require_render)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
