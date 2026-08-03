# Solvenotes Profile

Use this reference only when the target vault or repository clearly follows solvenotes-style conventions, for example local guidance names solvenotes or project validators define the profile.

## Quality Checks

- Keep backups and audit artifacts outside the vault by default. Create an in-vault artifact only when explicitly requested or required by local guidance.
- When source coverage is required, use the existing `source_manifest.md` and `99_内容覆盖审查.md` contracts instead of creating a separate quality-review page.
- Keep any explicitly requested central pages short and use course/source shards for long tables so Obsidian does not need to open one huge page.
- Generated review queues, example indexes, concept indexes, and source-coverage reports should follow the project’s existing filenames and validators.
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

- For strict cleanup, run `scripts/check_vault_quality.py --strict-study --profile solvenotes --forbid-report-notes --allow-formal-coverage-audits` separately on each affected course directory, not on the vault root where legitimate course pages reuse filenames.
  - Apply the formal-coverage exception only under the solvenotes profile. Accept only `99_内容覆盖审查.md` with frontmatter `note_type: coverage_audit` when the same directory contains `source_manifest.md` with frontmatter `note_type: source_manifest`. Treat a missing or wrongly typed manifest as a report-note failure, and keep ordinary audit and report notes forbidden.
- A course may contain a nested topic that local guidance treats as an independent validation root. Pass repeatable `--skip-dir` values for those exact root-relative directories, then validate each nested directory separately.
  - Use the canonical directory-entry spelling for every path component.
  - Reject absolute paths, parent traversal, missing paths, non-directories, internal or external symlink components, and non-canonical letter case or spelling.
  - Never canonicalize an alias or use substring or basename matching.

  For the independently validated `计算机视觉/图像Raw域去噪` topic, run both commands:

  ```bash
  python3 scripts/check_vault_quality.py --strict-study --profile solvenotes --forbid-report-notes --allow-formal-coverage-audits --skip-dir 图像Raw域去噪 /path/to/notes/计算机视觉
  python3 scripts/check_vault_quality.py --strict-study --profile solvenotes --forbid-report-notes --allow-formal-coverage-audits /path/to/notes/计算机视觉/图像Raw域去噪
  ```

- Prefer local project validators over bundled generic scripts. A typical solvenotes-style subset may include `check_links.py`, `check_frontmatter.py`, `check_headings.py`, `check_markdown_tables.py`, `check_all_notes.py`, generated-artifact `--check` commands, and repository hygiene/package checks.
- Before upload, run `git status`, stage only intended files, and leave unrelated dirty files untouched.
