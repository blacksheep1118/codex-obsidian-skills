# Solvenotes Profile

Use this reference only when the target vault or repository clearly follows solvenotes-style conventions, for example local guidance names solvenotes, project validators define the profile, or generated quality directories such as `99_质量审查/` are present.

## Generated Quality Artifacts

- Generated quality artifacts belong in the project-designated quality area, usually `99_质量审查/`.
- Regenerate quality artifacts with project scripts when possible.
- Keep central generated pages short and use course/source shards for long tables so Obsidian does not need to open one huge page.
- Generated review queues, example indexes, concept indexes, and source-coverage reports should be a small central entry page plus per-course shards.
- Do not place page-level coverage dump sections into ordinary study notes.

## Frontmatter And Local Scripts

- Preserve required solvenotes frontmatter fields such as `course`, `note_type`, `source_files`, `coverage`, and `last_checked`.
- Preserve special paper/link fields such as `title`, `source_url`, `source_type`, `created`, and `status`.
- Add `aliases` and `tags` only through local sync scripts when they exist.

## Link Coverage During Cleanup

- In strict study-note cleanup, do not delete `相关：`, `关联阅读`, `## 相关导航`, or similar link blocks until useful wiki links have been migrated inline or into a short explained `知识链接` section.
- Before and after broad note cleanup, compare wiki-link coverage against a baseline from Git history or `scripts/link_inventory.py`.
- Report total link count, per-directory link deltas, and the files with the largest losses.
- Treat unexplained large link loss as a regression even when `broken_links` is zero.
- When removing a stale navigation/report link, classify it as stale, unrelated, duplicate, or replaced.
- Preserve links to prerequisite concepts, follow-up chapters, source chapters, concept indexes, formulas, examples, or comparison methods.
- Avoid tail `## 知识链接` dumps and large one-line related-link clusters. A `关联阅读` link should sit near the paragraph that mentions the same concept, formula, method, dataset, metric, or failure mode.

## Course And Review Repair

- Finish and validate one course directory before moving to the next.
- If a course lacks source materials, limit claims to note quality and link integrity.
- After rewriting chapter notes from sources, rebuild course overview and review pages from repaired chapter content.
- When a chapter title, source boundary, or scope changes, update the course overview, short review page, detailed review page, and local navigation that repeats that title.
- Preserve old wiki-link entry points with short bridge notes when a renamed note may still be referenced.
- Treat unrelated-domain formula explanations, such as project earned-value terms in architecture notes or transaction/deadlock text outside database/OS context, as source-mismatch residues and replace them only after checking source material.

## Solvenotes Validation

- For strict cleanup, run `scripts/check_vault_quality.py --strict-study --profile solvenotes --forbid-report-notes` on affected note directories.
- Prefer local project validators over bundled generic scripts. A typical solvenotes-style subset may include `check_links.py`, `check_frontmatter.py`, `check_headings.py`, `check_markdown_tables.py`, `check_all_notes.py`, generated-artifact `--check` commands, and repository hygiene/package checks.
- Before upload, run `git status`, stage only intended files, and leave unrelated dirty files untouched.
