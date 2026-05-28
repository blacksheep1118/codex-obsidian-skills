---
name: ppt-to-md-for-obsidian
description: Use when converting PowerPoint PPT/PPTX/PDF lecture slides, courseware, or slide-derived materials into Obsidian-ready Markdown notes, course maps, cross-links, and review pages. Use $obsidian-vault-organizer instead for vault-only organization, repair, duplicate-note cleanup, or cross-link validation that does not require slide or courseware extraction.
---

# PPT To Markdown For Obsidian

## Goal

Convert slide-based course material into an Obsidian note system, not a raw slide transcript. The output should be readable as standalone study notes with concept explanation, mechanisms, formulas, examples, boundaries, and useful cross-links.

When writing into an existing project or vault, first load project-local guidance such as `AGENT.md`, `agent.md`, and files under `agent/`. Keep source files read-only unless the user explicitly asks to rename, move, or delete them. For vault-only organization work, use `$obsidian-vault-organizer`.

## Handoff Boundaries

Use this skill while source extraction or slide-order reconstruction is still part of the task. Once notes have been drafted and the remaining work is only link repair, duplicate cleanup, navigation restructuring, or vault-wide validation, switch to `$obsidian-vault-organizer`. If the user starts from public URLs instead of local files, use `$web-course-notes-for-obsidian` first and return here only after a permitted PPT/PDF has become a local source file.

## Default Outputs

For each course or topic directory, prefer this structure:

- `00_课程总览.md` or `00_学习地图.md` as the navigation entry.
- Numbered chapter notes such as `01_绪论.md`, `02_知识表示.md`.
- `知识点详细版_含公式.md` as the full review page.
- `知识点精简复习版_含公式.md` as the fast review page.
- `source_manifest.md` when multiple source files are involved or extraction order could be disputed.
- `99_内容覆盖审查.md` when the user asks for a strict check, exam review, or source-coverage assurance.

Keep the detailed review and concise review as two separate files. Do not replace the detailed version with the concise version.
If the user explicitly asks for one exam review file instead of two review pages, keep the single file but make the overview link it and validate with `--allow-exam-review`.

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

3. Do a source coverage pass before writing the final notes.
   - Build a source-to-output map by file, chapter, slide/page range, and major headings.
   - Pull out formulas, algorithms, examples, derivation steps, definitions, assumptions, and warnings from each source file.
   - Compare this map with the requested exam scope. Mark topics as `included`, `out of scope by user`, `source noisy`, or `missing`.
   - If the material is long or the user asks for strict checking, write a `source_manifest.md` plus `99_内容覆盖审查.md` instead of relying on memory.
   - Do not claim completion from a short outline. If the notes do not yet explain the mechanisms, formulas, and examples from the source, keep expanding them.

4. Rewrite into primary notes.
   - Use Chinese as the main language; keep standard English terms such as `Transformer`, `BERT`, `CLIP`, `SVM`.
   - Convert bullet fragments into continuous explanations.
   - Add variables and assumptions directly after formulas.
   - Use `$$ ... $$` for block formulas.
   - For exam material, include definitions, formula meanings, derivation logic, calculation examples, decision rules, common traps, and boundary conditions.
   - For probability/statistics, write the likelihood, posterior, risk, estimator bias, or gradient formula before explaining it in words.
   - For algorithms, include the update rule, stopping condition, convergence intuition, and at least one failure case when relevant.
   - Avoid generic study plans, empty templates, and repeated bridge sentences.
   - Avoid headings or filler such as `例题模板`, `高频答题模板`, `套话`, `空话`, or placeholder-like wording. Write the actual question-solving rule instead.

5. Build Obsidian navigation.
   - Add or update the course overview.
   - Link concepts where they first become relevant.
   - Avoid dumping large link lists at the end of every note.
   - Use wiki links such as `[[课程目录/文件名|显示文本]]`.

6. Add review pages.
   - The detailed version should retain the full course mechanism and formulas.
   - The concise version should keep the main chain, core formulas, and common mistakes.
   - If the user says a long review page must not be split, keep it as one file.
   - A single exam review page still needs full derivations, examples, and comparison tables when those are in scope. It should not collapse into a formula list.

7. Validate before finishing.
   - Check broken links and self-links with `scripts/check_obsidian_links.py`.
   - Check course-note output structure with `scripts/check_course_notes.py`.
   - For long courseware or strict review requests, run `scripts/check_course_notes.py --strict-depth --require-coverage-audit`. Add `--allow-exam-review` when using one exam review file instead of the two default review pages.
   - Check empty files, conflict markers, leftover template phrases such as `相关知识链接`, and review-page coverage.
   - Run a direct keyword/formula sweep against source-derived terms before the final response. Missing hits should be explained as out of scope, noisy extraction, or corrected before delivery.

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
- Which source pages/slides supplied the topic, and where did the final note cover it?

Poor notes usually look like:

- direct slide dumps,
- long bullet lists without explanation,
- formulas without variable meaning,
- duplicated link blocks,
- course overviews that become too long to navigate,
- exam review pages that contain only generic answer patterns instead of course-specific derivations, examples, and decisions.

## Output Contract

The final response should include:

- output folder and the main note files created or updated,
- source coverage summary by PPT/PPTX/PDF file, including any extraction gaps,
- review-page status for detailed and concise versions,
- strict-depth status when used, including the exact thresholds or reason it was not used,
- validation performed, including link, course-note, formula-fence, and keyword checks when run,
- unresolved assumptions, noisy formulas, missing slides, or source files that still need manual review.

If only a dry run or audit was requested, report planned changes and validation commands without writing notes.

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
