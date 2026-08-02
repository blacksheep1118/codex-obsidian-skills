# Solvenotes Profile

Use this reference only when the target vault or repository clearly follows solvenotes-style conventions, for example local guidance names solvenotes or project scripts define the same checks.

## Quality Checks

- Do not create an issue ledger or reviewer-facing audit page merely because a strict review was performed. Keep temporary reports outside the vault and write corrected explanations and source markers into notes.
- When source coverage must be recorded, update `source_manifest.md` or an existing `99_内容覆盖审查.md` only when the local validator requires it; do not create a separate quality directory.
- Prefer generated scripts over hand-edited coverage bodies when a generator owns the file.
- Keep any explicitly required central coverage page short and split large tables by course or source group.

## Solvenotes Validation

When project-local validators exist, prefer them over bundled generic checks. A typical solvenotes-style local suite may include:

- `check_all_notes.py`
- `check_links.py`
- `check_examples.py`
- `check_frontmatter.py`
- `check_markdown_tables.py`
- `check_formulas.py`
- `check_headings.py`
- `check_special_dirs.py`
- `check_source_coverage.py`
- generated-file `--check` commands

Also run local extraction-noise normalization checks when available.

## Source Coverage

- For strict PPT/PDF coverage audits, run the project-local source coverage checker first.
- If only bundled `scripts/check_source_coverage.py` is available, run it with explicit `source=notes` directory mappings.
- Add `--require-course-prefixed-source-refs` when source files live outside the notes repo, so bare filenames such as `lecture 1.pptx` are rejected in favor of root-relative paths such as `编译原理/lecture 1.pptx`.
- Do not accept `course_note_issues 0` as sufficient source coverage by itself. Also require `missing_source_mappings 0`, `source_table_issues 0`, `note_source_ownership_issues 0`, and `coverage_evidence_issues 0`.
- Treat `CHAPTER_MISMATCH_SOURCE_LINK` and `CHAPTER_MISMATCH_NOTE_SOURCE` as blockers.
- After migrating source index lines between notes, rerun source coverage checks and a direct `rg` for moved source filenames in old target notes.

## Repository Hygiene

- Before upload, run local repository hygiene checks when available.
- Confirm local trash, workspace state, caches, and package-export outputs are ignored or excluded by project scripts.
- Do not stage `.obsidian/workspace.json` or other local UI state.
- If both a notes repository and a skill repository changed, validate and report them separately.
