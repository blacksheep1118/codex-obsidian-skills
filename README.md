# skill-ppt-to-md-for-obsidian

Codex skill for converting PPT/PPTX courseware into Obsidian-ready Markdown notes.

The skill is designed for lecture slides that need to become usable study notes, not slide transcripts. It emphasizes Chinese course notes, formulas, numbered chapter files, course maps, cross-links, and detailed plus concise review pages.

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
├── agents/
│   └── openai.yaml
├── examples/
│   └── sample-course/
├── scripts/
│   ├── check_obsidian_links.py
│   ├── clean_latex_from_ppt.py
│   ├── convert_ppt_to_pptx.py
│   ├── extract_pptx_text.py
│   └── validate_skill_repo.py
└── references/
    ├── modes.md
    ├── obsidian-style.md
    └── validation.md
```

## Usage

Install or copy this repository as a Codex skill, then ask Codex to convert courseware into Obsidian notes.

Example prompts:

```text
把这个课程 PPT 转成 Obsidian 笔记，保留公式解释和章节导航。
```

```text
检查这个 notes 目录，补课程总览、详细复习版和精简复习版。
```

```text
把新增 PPT 合并进已有笔记，不要移动源资料。
```

## PPTX Text Extraction

For deterministic extraction from `.pptx`:

```bash
python3 scripts/extract_pptx_text.py path/to/slides.pptx --out extracted.md
```

The script extracts slide text, table cells, and speaker notes when available. It is intended as a raw input aid; Codex should still rewrite the output into clean notes.

## Legacy PPT Conversion

For old `.ppt` files, install LibreOffice and convert first:

```bash
python3 scripts/convert_ppt_to_pptx.py path/to/slides.ppt --out-dir converted_pptx
```

Then run the PPTX extractor on the converted file.

## Formula Cleanup

Clean common extraction artifacts before rewriting:

```bash
python3 scripts/clean_latex_from_ppt.py extracted.md --unicode-math --out cleaned.md
```

This handles zero-width characters, control characters, repeated LaTeX backslashes, and common Unicode math symbols on math-like lines.

## Obsidian Link Check

Check a vault or notes directory:

```bash
python3 scripts/check_obsidian_links.py examples/sample-course/notes
```

The checker covers Markdown links, `[[wiki]]`, `[[path/to/file]]`, and `[[path/to/file|alias]]`.

## Examples

`examples/sample-course/` contains:

- `raw/sample_course.pptx`
- `extracted/sample_course_extracted.md`
- `notes/` with a small Obsidian-ready course note set

The example is intentionally small so it can be used in CI and regression tests.

## Conversion Modes

The skill supports three output modes:

- Course notes
- Research group presentation
- Exam review material

See [references/modes.md](references/modes.md) for mode-specific guidance.

## CI

GitHub Actions validates:

- Python syntax for scripts.
- `SKILL.md` frontmatter.
- `agents/openai.yaml` YAML and default prompt.
- README local links.
- Sample PPTX extraction.
- Formula cleanup.
- Sample Obsidian link integrity.

## Design Principles

- Source files are read-only by default.
- Markdown outputs should be study notes, not slide dumps.
- Formulas need nearby variable explanations.
- Links should be placed where concepts first appear.
- Detailed and concise review pages should both be preserved.
- Source conversion, extraction, cleanup, and validation should be reproducible from scripts.

## License

Add a license if this repository will be shared publicly.
