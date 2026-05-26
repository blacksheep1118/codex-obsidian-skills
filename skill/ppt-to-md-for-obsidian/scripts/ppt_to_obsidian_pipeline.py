#!/usr/bin/env python3
"""Run a deterministic source-to-cleaned-Markdown pipeline.

The script does not attempt to write final study notes. It creates reproducible
raw extraction artifacts and a manifest that tells Codex or a human editor what
to rewrite into Obsidian notes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

try:
    from .clean_latex_from_ppt import clean_text
    from .extract_pptx_text import extract_pptx
    from .extract_pdf_text import extract_pdf
except ImportError:
    from clean_latex_from_ppt import clean_text
    from extract_pptx_text import extract_pptx
    from extract_pdf_text import extract_pdf


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


def extract_source(path: Path, config: PipelineConfig, converted_dir: Path) -> tuple[Path, str]:
    suffix = path.suffix.lower()
    actual = path
    if suffix == ".ppt":
        actual = convert_legacy_ppt(path, converted_dir, config.soffice)
        suffix = ".pptx"

    if suffix == ".pptx":
        return actual, extract_pptx(actual)
    if suffix == ".pdf":
        return actual, extract_pdf(actual)
    raise ValueError(f"unsupported source type: {path}")


def safe_stem(path: Path) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in path.stem)


def write_manifest(config: PipelineConfig, processed: list[tuple[Path, Path, Path]]) -> None:
    manifest = config.output_dir / "pipeline_manifest.md"
    lines = [
        f"# PPT/PDF To Obsidian Pipeline Manifest",
        "",
        f"- Source: `{config.source}`",
        f"- Output directory: `{config.output_dir}`",
        f"- Mode: `{config.mode}`",
        f"- Course name: `{config.course_name}`",
        "",
        "## Processed Sources",
    ]
    for source, raw, cleaned in processed:
        lines.append(f"- `{source}` -> `{raw.relative_to(config.output_dir)}` -> `{cleaned.relative_to(config.output_dir)}`")

    lines += [
        "",
        "## Suggested Obsidian Structure",
        "",
        f"- `{config.overview_name}`",
        "- `01_<topic>.md`",
        "- `知识点详细版_含公式.md`",
        "- `知识点精简复习版_含公式.md`",
        "",
        "Use the cleaned extraction files as raw material. Rewrite them into primary notes; do not treat them as final notes.",
    ]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_placeholders(config: PipelineConfig) -> None:
    if not config.create_review_placeholders:
        return
    notes_dir = config.output_dir / "notes_skeleton"
    notes_dir.mkdir(parents=True, exist_ok=True)
    overview = notes_dir / config.overview_name
    if not overview.exists():
        overview.write_text(
            f"# {config.course_name} 总览\n\n"
            "## 顺序导航\n\n"
            "待根据 cleaned extraction 添加章节笔记。\n\n"
            "## 总复习\n\n"
            "- [[知识点精简复习版_含公式|知识点精简复习版（含公式）]]\n"
            "- [[知识点详细版_含公式|知识点详细版（含公式）]]\n",
            encoding="utf-8",
        )
    for name, title in [
        ("知识点详细版_含公式.md", "知识点详细版（含公式）"),
        ("知识点精简复习版_含公式.md", "知识点精简复习版（含公式）"),
    ]:
        path = notes_dir / name
        if not path.exists():
            path.write_text(f"# {config.course_name}{title}\n\n待根据 cleaned extraction 重写。\n", encoding="utf-8")


def run(config: PipelineConfig) -> list[tuple[Path, Path, Path]]:
    sources = iter_sources(config.source)
    if not sources:
        raise SystemExit(f"no supported source files found in {config.source}")

    raw_dir = config.output_dir / "raw_extracted"
    cleaned_dir = config.output_dir / "cleaned"
    converted_dir = config.output_dir / config.converted_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    processed = []
    for source in sources:
        actual_source, extracted = extract_source(source, config, converted_dir)
        raw_path = raw_dir / f"{safe_stem(actual_source)}.md"
        cleaned_path = cleaned_dir / f"{safe_stem(actual_source)}.md"
        raw_path.write_text(extracted, encoding="utf-8")
        cleaned_path.write_text(clean_text(extracted, unicode_math=config.unicode_math), encoding="utf-8")
        processed.append((source, raw_path, cleaned_path))

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
