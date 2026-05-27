---
name: obsidian-vault-organizer
description: Use when organizing, repairing, merging, restructuring, or validating existing Obsidian vaults or Markdown note collections, including course notes, research notes, paper notes, concept maps, indexes, cross-links, review pages, project-local AGENT.md/agent guidance, source-file safety, broken links, duplicate notes, naming conventions, and vault navigation. Do not use solely for extracting PPT/PPTX/PDF slide text; use $ppt-to-md-for-obsidian for slide or courseware conversion.
---

# Obsidian Vault Organizer

## Goal

Organize an existing Obsidian vault or Markdown note collection into a coherent note system without damaging source materials. Preserve local conventions, improve navigation, repair links, merge duplicate notes, and turn rough notes into usable study or research material.

Use this skill for vault-first work. If the main task is extracting or converting PPT/PPTX/PDF courseware, use `$ppt-to-md-for-obsidian` instead.

## Dry-run Mode

When the user asks for a dry run, audit and report planned edits only. Include broken links, duplicate note stems, proposed merges, proposed renames, source files that should stay read-only, and validation commands to run. Do not modify files until the user approves the plan.

Do not create backup copies or backup directories unless the user explicitly asks. Use dry-run reports, git diffs, and validation output as the default safety mechanism.

## Workflow

1. Resolve the project, vault, and source boundaries.
   - Identify the vault from explicit paths, `.obsidian`, notes-like directories, or dense Markdown collections.
   - Identify source materials separately from notes.
   - Treat source files as read-only unless the user explicitly asks to rename, move, delete, or reorganize them.

2. Load local guidance before editing.
   - Read `AGENT.md`, `agent.md`, and relevant files under `agent/` when present.
   - Read nearby overview pages, indexes, and existing note examples.
   - Let project-local guidance override this generic skill.
   - See `references/project-vault-workflow.md` for path resolution and editing boundaries.

3. Audit the current vault shape.
   - Find navigation pages, orphan notes, broken links, self-links, duplicate topics, empty files, conflict markers, and leftover template phrases.
   - Identify naming and numbering conventions before creating files.
   - Prefer updating an existing note over creating a duplicate.

4. Organize content.
   - Create or update overview/index notes only where they are useful.
   - Merge duplicate same-topic notes when the target is clear.
   - Keep course order, paper sequence, and concept hierarchy consistent with neighboring notes.
   - Put links where concepts first become relevant rather than dumping large link lists at the end.

5. Improve note quality.
   - Rewrite rough notes into explanations, not source dumps.
   - Preserve Chinese as the default language when the vault uses Chinese.
   - Keep standard English technical terms where appropriate.
   - Add formula variable meanings, assumptions, examples, failure cases, and boundaries when useful.
   - See `references/obsidian-style.md` for style guidance.

6. Validate before finishing.
   - Run `scripts/check_obsidian_links.py` for Markdown and Obsidian wiki links when the vault is local.
   - Run `scripts/check_vault_quality.py` for conflict markers, empty files, unbalanced block math, duplicate note stems, and leftover template text.
   - See `references/validation.md` for lightweight checks.

## Common Tasks

- Merge newly written notes into an existing vault.
- Repair broken `[[wiki]]` and Markdown links.
- Build or update `00_课程总览.md`, `00_学习地图.md`, concept indexes, and review pages.
- Clean duplicated topic notes while preserving the better content.
- Reconcile note names, numbering, and cross-links after a course or project update.
- Audit a vault and report safe edits separately from source-file findings.

## Quality Bar

Good vault organization should make the note system easier to navigate without hiding source provenance or local conventions. The final vault should have clear entry points, stable filenames, useful cross-links, no accidental source-file edits, and no new duplicate same-topic notes.

Avoid generic study templates, empty boilerplate sections, broad rewrites unrelated to the request, and moving source materials into the vault without explicit permission.

## Output Contract

The final response should include:

- vault path and scope that were actually inspected,
- files created, updated, merged, renamed, or intentionally left untouched,
- source-file safety status, especially if source materials were found near notes,
- validation performed, including link and quality checks when run,
- unresolved broken links, duplicate candidates, naming conflicts, or local-guidance assumptions.

For dry-run work, clearly separate proposed edits from applied edits and do not claim changes were made.

## Bundled Resources

- `scripts/check_obsidian_links.py`: check Markdown links and Obsidian wiki links.
- `scripts/check_vault_quality.py`: check empty files, conflict markers, unbalanced fences/math, duplicate note stems, and template residue.
- `references/project-vault-workflow.md`: path discovery, local guidance loading, and editing boundaries.
- `references/obsidian-style.md`: note writing, formulas, links, navigation, and review page style.
- `references/validation.md`: lightweight validation checks for vault edits.
