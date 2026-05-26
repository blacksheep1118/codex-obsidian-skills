---
name: ppt-to-md-for-obsidian
description: Use when converting PowerPoint PPT/PPTX/PDF lecture slides, courseware, or slide-derived materials into Obsidian-ready Markdown notes, course maps, cross-links, and review pages. Use $obsidian-vault-organizer instead for vault-only organization, repair, duplicate-note cleanup, or cross-link validation that does not require slide or courseware extraction.
---

# PPT To Markdown For Obsidian

## Goal

Convert slide-based course material into an Obsidian note system, not a raw slide transcript. The output should be readable as standalone study notes with concept explanation, mechanisms, formulas, examples, boundaries, and useful cross-links.

When writing into an existing project or vault, first load project-local guidance such as `AGENT.md`, `agent.md`, and files under `agent/`. Keep source files read-only unless the user explicitly asks to rename, move, or delete them. For vault-only organization work, use `$obsidian-vault-organizer`.

## Default Outputs

For each course or topic directory, prefer this structure:

- `00_课程总览.md` or `00_学习地图.md` as the navigation entry.
- Numbered chapter notes such as `01_绪论.md`, `02_知识表示.md`.
- `知识点详细版_含公式.md` as the full review page.
- `知识点精简复习版_含公式.md` as the fast review page.

Keep the detailed review and concise review as two separate files. Do not replace the detailed version with the concise version.

## Workflow

1. Inventory the source files and existing notes first.
   - Identify PPT/PPTX/PDF/DOCX source files, their course order, and whether matching notes already exist.
   - Treat source files as read-only unless the user explicitly asks to rename, move, or delete them.

2. Extract slide text while preserving slide order.
   - For `.pptx`, use `scripts/extract_pptx_text.py` when a deterministic text dump helps.
   - For legacy `.ppt`, use `scripts/convert_ppt_to_pptx.py` to convert with LibreOffice first, then extract.
   - For `.pdf` courseware, use `scripts/extract_pdf_text.py`.
   - If the extracted text contains formula noise, run `scripts/clean_latex_from_ppt.py` before rewriting.
   - For repeatable runs, use `scripts/ppt_to_obsidian_pipeline.py` to extract, clean, and write a manifest.
   - If extraction is noisy, use slide titles, visible bullets, formulas, filenames, and course order together instead of trusting raw text blindly.

3. Rewrite into primary notes.
   - Use Chinese as the main language; keep standard English terms such as `Transformer`, `BERT`, `CLIP`, `SVM`.
   - Convert bullet fragments into continuous explanations.
   - Add variables and assumptions directly after formulas.
   - Use `$$ ... $$` for block formulas.
   - Avoid generic study plans, empty templates, and repeated bridge sentences.

4. Build Obsidian navigation.
   - Add or update the course overview.
   - Link concepts where they first become relevant.
   - Avoid dumping large link lists at the end of every note.
   - Use wiki links such as `[[课程目录/文件名|显示文本]]`.

5. Add review pages.
   - The detailed version should retain the full course mechanism and formulas.
   - The concise version should keep the main chain, core formulas, and common mistakes.
   - If the user says a long review page must not be split, keep it as one file.

6. Validate before finishing.
   - Check broken links and self-links with `scripts/check_obsidian_links.py`.
   - Check course-note output structure with `scripts/check_course_notes.py`.
   - Check empty files, conflict markers, leftover template phrases such as `相关知识链接`, and review-page coverage.

## Conversion Modes

Choose one mode before rewriting:

- Course notes: numbered chapter notes, course overview, detailed and concise review pages.
- Research group presentation: problem, method, experiment, limitation, and discussion.
- Exam review material: concept map, formula table, typical question patterns, and common mistakes.

See `references/modes.md` when the mode is ambiguous or the user asks for a specific output style.

## Configuration

Use `skill-config.example.yaml` as a starting point for repeatable conversions. It defines the source directory, output directory, mode, cleanup settings, LibreOffice conversion path, and Obsidian naming preferences.

## Quality Bar

Good notes should answer:

- What problem does this slide/topic solve?
- What are the core concepts and how do they relate?
- Which formula matters, and what does each variable mean here?
- What assumptions or failure cases should the learner remember?
- Which nearby notes should be linked for cross-course recall?

Poor notes usually look like:

- direct slide dumps,
- long bullet lists without explanation,
- formulas without variable meaning,
- duplicated link blocks,
- course overviews that become too long to navigate.

## Bundled Resources

- `scripts/extract_pptx_text.py`: extract ordered text, tables, and notes from `.pptx` files.
- `scripts/convert_ppt_to_pptx.py`: convert legacy `.ppt` files to `.pptx` with LibreOffice.
- `scripts/extract_pdf_text.py`: extract raw text from `.pdf` courseware.
- `scripts/check_obsidian_links.py`: check Markdown and Obsidian wiki links.
- `scripts/check_course_notes.py`: check course overview, review pages, empty files, conflict markers, template residue, and formula fences.
- `scripts/clean_latex_from_ppt.py`: normalize formula and Unicode noise from slide extraction.
- `scripts/ppt_to_obsidian_pipeline.py`: run conversion, extraction, cleanup, and manifest creation.
- `references/obsidian-style.md`: local style guide for note writing and cross-linking.
- `references/validation.md`: lightweight validation checks for Obsidian Markdown outputs.
- `references/modes.md`: conversion mode guidance for course notes, group presentations, and exam review.
