#!/usr/bin/env python3
"""Run a deterministic source-to-cleaned-Markdown pipeline.

The script does not attempt to write final study notes. It creates reproducible
raw extraction artifacts and a manifest that tells Codex or a human editor what
to rewrite into Obsidian notes.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import stat

try:
    from .clean_latex_from_ppt import clean_text
    from .extract_legacy_ppt_text import LegacyPptTextResult, extract_legacy_ppt_text
    from .extract_pptx_text import extract_pptx
    from .extract_pdf_text import LOW_COVERAGE_WARNING, extract_pdf_result
except ImportError:
    from clean_latex_from_ppt import clean_text
    from extract_legacy_ppt_text import LegacyPptTextResult, extract_legacy_ppt_text
    from extract_pptx_text import extract_pptx
    from extract_pdf_text import LOW_COVERAGE_WARNING, extract_pdf_result


SUPPORTED_SUFFIXES = {".ppt", ".pptx", ".pdf"}


@dataclass
class PipelineConfig:
    source: Path
    output_dir: Path
    mode: str = "course-notes"
    unicode_math: bool = False
    soffice: str | None = None
    converted_dir: str = "converted_pptx"
    course_name: str = "Course"
    overview_name: str = "00_课程总览.md"
    create_review_placeholders: bool = True


@dataclass
class ExtractionResult:
    actual_source: Path
    text: str
    backend: str
    partial: bool = False
    notes: list[str] | None = None
    text_record_count: int | None = None
    low_coverage: bool = False
    empty_pages: int | None = None
    char_count: int | None = None
    page_count: int | None = None


@dataclass
class ProcessedSource:
    source: Path
    raw: Path
    cleaned: Path
    backend: str
    partial: bool = False
    notes: list[str] | None = None
    text_record_count: int | None = None
    low_coverage: bool = False
    empty_pages: int | None = None
    char_count: int | None = None
    page_count: int | None = None


def safe_relative_config_path(value: str, label: str) -> Path:
    """Return a root-relative configured child path without traversal."""

    try:
        path = Path(value)
        windows_path = PureWindowsPath(value)
    except TypeError as exc:
        raise ValueError(f"{label} must be a relative path string") from exc
    if path.is_absolute() or windows_path.is_absolute():
        raise ValueError(f"{label} must be root-relative, not absolute: {value!r}")
    if not path.parts or path == Path(".") or ".." in path.parts or ".." in windows_path.parts:
        raise ValueError(f"{label} must not be empty or contain '..': {value!r}")
    return path


def relative_beneath(root: Path, path: Path) -> Path:
    root = root.resolve()
    candidate = path if path.is_absolute() else root / path
    candidate = Path(os.path.abspath(candidate))
    try:
        return candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"output path escapes output_dir: {path}") from exc


def ensure_safe_directory(root: Path, path: Path, *, create: bool) -> Path:
    """Validate or create a directory without traversing symlink components."""

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
            raise ValueError(f"output directory contains symlink component: {current}")
        if not stat.S_ISDIR(mode):
            raise ValueError(f"output directory component is not a directory: {current}")
    return root / relative


def ensure_safe_output_path(root: Path, path: Path, *, create_parent: bool = True) -> Path:
    root = root.resolve()
    relative = relative_beneath(root, path)
    candidate = root / relative
    ensure_safe_directory(root, candidate.parent, create=create_parent)
    try:
        mode = candidate.lstat().st_mode
    except FileNotFoundError:
        return candidate
    if stat.S_ISLNK(mode):
        raise ValueError(f"output path is a symlink: {candidate}")
    if not stat.S_ISREG(mode):
        raise ValueError(f"output path is not a regular file: {candidate}")
    return candidate


def write_text_no_follow(root: Path, path: Path, content: str) -> None:
    candidate = ensure_safe_output_path(root, path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(candidate, flags, 0o666)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError(f"output path is not a regular file: {candidate}")
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            descriptor = -1
            stream.write(content)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def load_yaml_config(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        raise SystemExit("PyYAML is required for --config. Install dependencies from requirements.txt.")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def config_from_args(args: argparse.Namespace) -> PipelineConfig:
    data = load_yaml_config(args.config) if args.config else {}
    clean = data.get("clean", {})
    conversion = data.get("conversion", {})
    obsidian = data.get("obsidian", {})

    source = Path(args.source or data.get("source", "."))
    output_dir = Path(args.output_dir or data.get("output_dir", "build/obsidian-pipeline"))
    mode = args.mode or data.get("mode", "course-notes")

    return PipelineConfig(
        source=source,
        output_dir=output_dir,
        mode=mode,
        unicode_math=args.unicode_math or bool(clean.get("unicode_math", False)),
        soffice=args.soffice or conversion.get("soffice"),
        converted_dir=conversion.get("converted_dir", "converted_pptx"),
        course_name=obsidian.get("course_name", source.stem or "Course"),
        overview_name=obsidian.get("overview_name", "00_课程总览.md"),
        create_review_placeholders=bool(obsidian.get("create_review_placeholders", True)),
    )


def iter_sources(source: Path) -> list[Path]:
    if source.is_dir():
        return sorted(path for path in source.rglob("*") if path.suffix.lower() in SUPPORTED_SUFFIXES)
    return [source]


def convert_legacy_ppt(path: Path, converted_dir: Path, soffice: str | None) -> Path:
    try:
        from .convert_ppt_to_pptx import convert_one, find_soffice
    except ImportError:
        from convert_ppt_to_pptx import convert_one, find_soffice

    return convert_one(path, converted_dir, find_soffice(soffice))


def legacy_ppt_fallback(path: Path, conversion_error: Exception) -> ExtractionResult:
    try:
        fallback: LegacyPptTextResult = extract_legacy_ppt_text(path)
    except Exception as fallback_error:
        raise RuntimeError(
            "LibreOffice conversion failed or was unavailable, and OLE/CFB text-record fallback also failed. "
            f"Conversion error: {conversion_error}; fallback error: {fallback_error}"
        ) from fallback_error
    notes = [
        f"LibreOffice conversion failed or was unavailable: {conversion_error}",
        "Used OLE/CFB text-record fallback; treat this as partial text evidence, not full slide coverage.",
    ]
    if fallback.text_record_count == 0:
        notes.append("No legacy PPT text records were found; the file may be image-only or OCR-limited.")
    return ExtractionResult(
        actual_source=path,
        text=fallback.markdown,
        backend="legacy-ppt-ole-cfb-fallback",
        partial=True,
        notes=notes,
        text_record_count=fallback.text_record_count,
    )


def extract_source(path: Path, config: PipelineConfig, converted_dir: Path) -> ExtractionResult:
    suffix = path.suffix.lower()
    actual = path
    if suffix == ".ppt":
        try:
            actual = convert_legacy_ppt(path, converted_dir, config.soffice)
        except Exception as exc:
            return legacy_ppt_fallback(path, exc)
        suffix = ".pptx"

    if suffix == ".pptx":
        return ExtractionResult(actual_source=actual, text=extract_pptx(actual), backend="pptx")
    if suffix == ".pdf":
        pdf_result = extract_pdf_result(actual)
        notes = [
            f"PDF pages: {pdf_result.page_count}; empty text pages: {pdf_result.empty_pages}; text characters: {pdf_result.char_count}.",
        ]
        if pdf_result.low_coverage:
            notes.append(LOW_COVERAGE_WARNING)
        return ExtractionResult(
            actual_source=actual,
            text=pdf_result.markdown,
            backend=f"pdf:{pdf_result.backend}",
            notes=notes,
            low_coverage=pdf_result.low_coverage,
            empty_pages=pdf_result.empty_pages,
            char_count=pdf_result.char_count,
            page_count=pdf_result.page_count,
        )
    raise ValueError(f"unsupported source type: {path}")


def safe_stem(path: Path) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in path.stem)


def disambiguated_stem(path: Path, source_identity: Path, used: dict[str, str]) -> str:
    """Return a stable output stem without overwriting same-named sources.

    A basename is kept for the common single-source case. When two sources
    share that basename, later outputs receive a short hash of their source
    path, so same-named files cannot overwrite one another.
    """

    base = safe_stem(path)
    identity = source_identity.as_posix()
    if base not in used:
        used[base] = identity
        return base

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
    candidate = f"{base}-{digest}"
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{digest}-{suffix}"
        suffix += 1
    used[candidate] = identity
    return candidate


def write_manifest(config: PipelineConfig, processed: list[ProcessedSource]) -> None:
    manifest = config.output_dir / "pipeline_manifest.md"
    lines = [
        "# PPT/PDF To Obsidian Pipeline Manifest",
        "",
        f"- Source: `{config.source}`",
        f"- Output directory: `{config.output_dir}`",
        f"- Mode: `{config.mode}`",
        f"- Course name: `{config.course_name}`",
        "",
        "## Processed Sources",
    ]
    for item in processed:
        lines.append(f"- `{item.source}` -> `{item.raw.relative_to(config.output_dir)}` -> `{item.cleaned.relative_to(config.output_dir)}`")
        lines.append(f"  - Extraction backend: `{item.backend}`")
        if item.text_record_count is not None:
            lines.append(f"  - Text records: {item.text_record_count}")
        if item.page_count is not None:
            lines.append(
                f"  - PDF pages: {item.page_count}; empty text pages: {item.empty_pages}; text characters: {item.char_count}"
            )
        if item.low_coverage:
            lines.append("  - Coverage: low text coverage; do not claim complete source coverage without OCR/manual inspection.")
        if item.partial:
            lines.append("  - Coverage: partial/fallback extraction; do not claim complete source coverage from this artifact alone.")
        for note in item.notes or []:
            lines.append(f"  - Note: {note}")

    lines += [
        "",
        "## Suggested Obsidian Structure",
        "",
        f"- `{config.overview_name}`",
        "- `01_<topic>.md`",
        "- `知识点详细版_含公式.md`",
        "- `知识点精简复习版_含公式.md`",
        "",
        "Output stems keep the source basename when unique and add a stable path hash on collisions; no source may overwrite another artifact.",
        "Use the cleaned extraction files as raw material. Rewrite them into primary notes; do not treat them as final notes.",
    ]
    write_text_no_follow(config.output_dir, manifest, "\n".join(lines) + "\n")


def write_placeholders(config: PipelineConfig) -> None:
    if not config.create_review_placeholders:
        return
    notes_dir = ensure_safe_directory(
        config.output_dir,
        config.output_dir / "notes_skeleton",
        create=True,
    )
    overview = ensure_safe_output_path(
        config.output_dir,
        notes_dir / safe_relative_config_path(config.overview_name, "overview_name"),
    )
    if not overview.exists():
        write_text_no_follow(
            config.output_dir,
            overview,
            f"# {config.course_name} 总览\n\n"
            "## 顺序导航\n\n"
            "待根据 cleaned extraction 添加章节笔记。\n\n"
            "## 总复习\n\n"
            "- [[知识点精简复习版_含公式|知识点精简复习版（含公式）]]\n"
            "- [[知识点详细版_含公式|知识点详细版（含公式）]]\n",
        )
    for name, title in [
        ("知识点详细版_含公式.md", "知识点详细版（含公式）"),
        ("知识点精简复习版_含公式.md", "知识点精简复习版（含公式）"),
    ]:
        path = ensure_safe_output_path(config.output_dir, notes_dir / name)
        if not path.exists():
            write_text_no_follow(
                config.output_dir,
                path,
                f"# {config.course_name}{title}\n\n待根据 cleaned extraction 重写。\n",
            )


def run(config: PipelineConfig) -> list[ProcessedSource]:
    converted_relative = safe_relative_config_path(config.converted_dir, "converted_dir")
    safe_relative_config_path(config.overview_name, "overview_name")
    output_root = config.output_dir.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    if not output_root.is_dir():
        raise ValueError(f"output_dir is not a directory: {output_root}")
    config.output_dir = output_root
    sources = iter_sources(config.source)
    if not sources:
        raise SystemExit(f"no supported source files found in {config.source}")

    raw_dir = ensure_safe_directory(
        config.output_dir,
        config.output_dir / "raw_extracted",
        create=True,
    )
    cleaned_dir = ensure_safe_directory(
        config.output_dir,
        config.output_dir / "cleaned",
        create=True,
    )
    converted_dir = ensure_safe_directory(
        config.output_dir,
        config.output_dir / converted_relative,
        create=False,
    )
    ensure_safe_directory(
        config.output_dir,
        config.output_dir / "notes_skeleton",
        create=False,
    )
    ensure_safe_output_path(
        config.output_dir,
        config.output_dir / "pipeline_manifest.md",
        create_parent=False,
    )

    processed: list[ProcessedSource] = []
    used_output_stems: dict[str, str] = {}
    for source in sources:
        if source.suffix.lower() == ".ppt":
            converted_dir = ensure_safe_directory(
                config.output_dir,
                converted_dir,
                create=True,
            )
        extraction = extract_source(source, config, converted_dir)
        output_stem = disambiguated_stem(extraction.actual_source, source, used_output_stems)
        raw_path = raw_dir / f"{output_stem}.md"
        cleaned_path = cleaned_dir / f"{output_stem}.md"
        write_text_no_follow(config.output_dir, raw_path, extraction.text)
        write_text_no_follow(
            config.output_dir,
            cleaned_path,
            clean_text(extraction.text, unicode_math=config.unicode_math),
        )
        processed.append(
            ProcessedSource(
                source=source,
                raw=raw_path,
                cleaned=cleaned_path,
                backend=extraction.backend,
                partial=extraction.partial,
                notes=extraction.notes,
                text_record_count=extraction.text_record_count,
                low_coverage=extraction.low_coverage,
                empty_pages=extraction.empty_pages,
                char_count=extraction.char_count,
                page_count=extraction.page_count,
            )
        )

    write_manifest(config, processed)
    write_placeholders(config)
    return processed


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract and clean PPT/PDF sources for Obsidian note rewriting.")
    parser.add_argument("source", nargs="?", help="Source file or directory")
    parser.add_argument("--config", type=Path, help="YAML config path")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--mode", choices=["course-notes", "research-presentation", "exam-review"])
    parser.add_argument("--unicode-math", action="store_true")
    parser.add_argument("--soffice", help="Path to LibreOffice soffice binary")
    args = parser.parse_args()

    config = config_from_args(args)
    if not config.source.exists():
        parser.error(f"source does not exist: {config.source}")
    processed = run(config)
    print(f"processed_sources {len(processed)}")
    print(config.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
