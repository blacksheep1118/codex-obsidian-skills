# ppt-to-md-for-obsidian

Codex skill for converting PPT/PPTX/PDF courseware into Obsidian-ready Markdown notes.

The skill is designed for lecture slides that need to become usable study notes, not slide transcripts. It emphasizes Chinese course notes, formulas, numbered chapter files, course maps, cross-links, and detailed plus concise review pages.

For vault-only organization, duplicate-note cleanup, or link repair that does not require slide extraction, use the companion `obsidian-vault-organizer` skill.

## Install

Clone this repository, then install this skill into the matching Codex skill directory. By default this is `~/.codex/skills` on macOS/Linux and `%USERPROFILE%\.codex\skills` on Windows, unless `CODEX_HOME` is set.

macOS/Linux:

```bash
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git "${TMPDIR:-/tmp}/codex-obsidian-skills"
cd "${TMPDIR:-/tmp}/codex-obsidian-skills"
python3 scripts/install_skill.py --skill ppt-to-md-for-obsidian --self-check
```

Windows PowerShell:

```powershell
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git "$env:TEMP\codex-obsidian-skills"
cd "$env:TEMP\codex-obsidian-skills"
py scripts\install_skill.py --skill ppt-to-md-for-obsidian --self-check
```

On Windows, replace `py` with `python` if the Python launcher is not installed.

Install runtime dependencies when you want to run the bundled extraction scripts locally:

```bash
python3 -m pip install -r ~/.codex/skills/ppt-to-md-for-obsidian/requirements.txt
```

```powershell
py -m pip install -r "$env:USERPROFILE\.codex\skills\ppt-to-md-for-obsidian\requirements.txt"
```

## What It Produces

- Obsidian Markdown chapter notes.
- `00_课程总览.md` or `00_学习地图.md` navigation pages.
- `知识点详细版_含公式.md` full review pages.
- `知识点精简复习版_含公式.md` fast review pages.
- Cross-course wiki links using Obsidian syntax.

## Repository Layout

```text
.
├── SKILL.md
├── README.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── skill-config.example.yaml
├── agents/
│   └── openai.yaml
├── examples/
│   └── sample-course/
├── scripts/
│   ├── check_obsidian_links.py
│   ├── check_course_notes.py
│   ├── check_source_coverage.py
│   ├── clean_latex_from_ppt.py
│   ├── convert_ppt_to_pptx.py
│   ├── extract_legacy_ppt_text.py
│   ├── extract_pdf_text.py
│   ├── extract_pptx_text.py
│   ├── ppt_to_obsidian_pipeline.py
│   └── validate_skill_repo.py
├── fixtures/
│   └── pdf-formula-regression/
└── references/
    ├── modes.md
    ├── obsidian-style.md
    └── validation.md
```

## Usage

Install or copy this repository as a Codex skill, then ask Codex to convert courseware into Obsidian notes.

Install development/test dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
```

```powershell
py -m pip install -r requirements-dev.txt
```

Example prompts:

```text
把这个课程 PPT 转成 Obsidian 笔记，保留公式解释和章节导航。
```

```text
把这组 PDF 课件转成 Obsidian 章节笔记，并生成详细版和精简版复习页。
```

```text
把新增 PPT 合并进已有笔记，不要移动源资料。
```

Use `obsidian-vault-organizer` instead when the task starts from an existing vault and does not require PPT/PPTX/PDF extraction.

## PPTX Text Extraction

For deterministic extraction from `.pptx`:

```bash
python3 scripts/extract_pptx_text.py path/to/slides.pptx --out extracted.md
```

```powershell
py scripts\extract_pptx_text.py path\to\slides.pptx --out extracted.md
```

The script extracts slide text, table cells, and speaker notes when available. It is intended as a raw input aid; Codex should still rewrite the output into clean notes.

By default it sorts shapes by approximate visual position, detects slide titles, and emits placeholders for images or charts.

## Legacy PPT Conversion

For old `.ppt` files, install LibreOffice and convert first:

```bash
python3 scripts/convert_ppt_to_pptx.py path/to/slides.ppt --out-dir converted_pptx
```

```powershell
py scripts\convert_ppt_to_pptx.py path\to\slides.ppt --out-dir converted_pptx
```

The converter searches for `soffice`, `soffice.exe`, `libreoffice`, `libreoffice.exe`, the standard macOS app path, and common Windows LibreOffice install paths. If LibreOffice is installed elsewhere, pass `--soffice` with the executable path.

Then run the PPTX extractor on the converted file.

The one-command pipeline also starts with LibreOffice for `.ppt` files. If LibreOffice is unavailable or conversion fails, it falls back to the bundled read-only OLE/CFB text-record extractor:

```bash
python3 scripts/extract_legacy_ppt_text.py path/to/slides.ppt --out extracted.md
```

Fallback extraction is partial by design. The output and pipeline manifest report the fallback backend and text-record count, and should be treated as text hints rather than complete slide coverage.

## PDF Text Extraction

For PDF courseware:

```bash
python3 scripts/extract_pdf_text.py path/to/slides.pdf --out extracted.md
```

```powershell
py scripts\extract_pdf_text.py path\to\slides.pdf --out extracted.md
```

The PDF extractor tries `pypdf`, then `pdfplumber`, then the `pdftotext` CLI. If a backend returns all-empty pages or very low text coverage, the script continues to the next backend and reports the selected backend, page count, empty-text page count, and text character count in the Markdown output.

## Formula Cleanup

Clean common extraction artifacts before rewriting:

```bash
python3 scripts/clean_latex_from_ppt.py extracted.md --unicode-math --out cleaned.md
```

```powershell
py scripts\clean_latex_from_ppt.py extracted.md --unicode-math --out cleaned.md
```

This handles zero-width characters, control characters, repeated LaTeX backslashes, and common Unicode math symbols on math-like lines.

## Obsidian Link Check

Check a vault or notes directory:

```bash
python3 scripts/check_obsidian_links.py examples/sample-course/notes
```

```powershell
py scripts\check_obsidian_links.py examples\sample-course\notes
```

The checker covers Markdown links, `[[wiki]]`, `[[path/to/file]]`, and `[[path/to/file|alias]]`.

## Course-note Quality Check

Check generated course notes before finishing:

```bash
python3 scripts/check_course_notes.py examples/sample-course/notes
```

```powershell
py scripts\check_course_notes.py examples\sample-course\notes
```

The checker verifies the overview page, detailed and concise review pages, review links, empty files, conflict markers, template residue, fenced code blocks, and block math delimiters.

When checking a broader notes tree that contains non-course generated indexes or audit folders, exclude them by directory name:

```bash
python3 scripts/check_course_notes.py --skip-dir 概念索引 --skip-dir 生成审查 notes
```

```powershell
py scripts\check_course_notes.py --skip-dir 概念索引 --skip-dir 生成审查 notes
```

## Source Coverage Evidence Check

For strict PPT/PDF coverage audits, especially when source files live outside the notes repo, run the source coverage checker with explicit source-to-notes mappings:

```bash
python3 scripts/check_source_coverage.py \
  --source-root /path/to/course-root \
  --notes-root /path/to/course-root/notes \
  --mapping '数学模型=数学模型,编译原理=编译原理' \
  --require-course-prefixed-source-refs
```

The checker verifies source-file references, page-level supplement index fields, source/generated example evidence, canonical root-relative source paths, chapter ownership, hidden control characters, and stale manual-review labels.

## One-command Pipeline

Use the pipeline to convert/extract/clean sources and create a manifest:

```bash
python3 scripts/ppt_to_obsidian_pipeline.py --config skill-config.example.yaml
```

```powershell
py scripts\ppt_to_obsidian_pipeline.py --config skill-config.example.yaml
```

The pipeline supports `.ppt`, `.pptx`, and `.pdf` sources. It writes:

- `raw_extracted/`
- `cleaned/`
- `pipeline_manifest.md`
- optional `notes_skeleton/`

## Examples

`examples/sample-course/` contains:

- `raw/sample_course.pptx`
- `extracted/sample_course_extracted.md`
- `notes/` with a small Obsidian-ready course note set

The example is intentionally small so it can be used in CI and regression tests.

`examples/before-after/` shows a raw slide dump and the corresponding rewritten notes.

`examples/non-course/` shows research-presentation and paper-note patterns for non-course workflows.

## Conversion Modes

The skill supports three output modes:

- Course notes
- Research group presentation
- Exam review material

See [references/modes.md](references/modes.md) for mode-specific guidance.

## CI

GitHub Actions validates:

- Python syntax for scripts across Ubuntu, macOS, and Windows.
- Python 3.9, 3.11, and 3.12 on Ubuntu; Python 3.11 on macOS and Windows.
- pytest unit tests.
- `SKILL.md` frontmatter.
- `agents/openai.yaml` YAML and default prompt.
- README local links.
- Sample PPTX extraction.
- Formula cleanup.
- Pipeline execution.
- Sample Obsidian link integrity.
- Course-note output quality.
- Source coverage evidence checks.

## Design Principles

- Source files are read-only by default.
- Markdown outputs should be study notes, not slide dumps.
- Formulas need nearby variable explanations.
- Links should be placed where concepts first appear.
- Detailed and concise review pages should both be preserved.
- Source conversion, extraction, cleanup, and validation should be reproducible from scripts.

## License

MIT. See [LICENSE](LICENSE).
