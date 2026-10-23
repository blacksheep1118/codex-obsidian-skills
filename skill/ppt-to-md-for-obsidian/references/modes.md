# Conversion Modes

Use these modes when the user asks for a specific output style.

## Paper Notes

Best for a local research-paper PDF that should become a standalone learning note.

- Extract with `scripts/extract_pdf_text.py` and inspect rendered figures, tables, and equations when needed. This is a writing workflow, not a new `--mode` value for the courseware pipeline.
- Verify the title, authors, year, DOI when assigned, and venue or preprint status against the paper or an official bibliographic record.
- Explain the research gap, method, assumptions, scoped experimental evidence, reproducibility obstacles, and failure boundaries; retain source files, URLs, and precise page/figure/table references.
- Default to one substantive note and existing topic navigation. Do not create course overviews, numbered chapters, paired review pages, or teaching exercises unless requested.
- Validate links, source ownership, metadata, formulas, and the paper-specific claims. Use a local paper-note checklist when available; the bundled course-structure checker does not apply.
- Keep extraction dumps and temporary coverage records outside the vault, following the project's provenance policy.

## Course Notes

Best for lecture PPT/PPTX files.

- Build numbered chapter notes.
- Preserve course order.
- Explain concepts, formulas, examples, assumptions, and boundaries.
- Create or update `00_课程总览.md`.
- Add detailed and concise review pages.
- Use `scripts/ppt_to_obsidian_pipeline.py` when the same course will be processed repeatedly.

## Research Group Presentation

Best for paper-sharing, lab meeting, and project update slides.

- Organize by problem, motivation, method, experiment, limitation, and discussion.
- Keep citation information when present.
- Separate "paper claims" from "speaker interpretation".
- Add links to related methods or course concepts when useful.
- Preserve raw extracted slides in case claims need to be checked against the original talk.

## Exam Review Material

Best for final review slides, question banks, and answer-key style material.

- Prioritize concept map, formula table, typical question patterns, and common mistakes.
- Preserve detailed explanations in the detailed review page.
- Keep the concise review page short enough for final-pass scanning.
- Avoid generic study plans unless the user explicitly asks for them.
- Treat formulas and typical question patterns as first-class sections.
