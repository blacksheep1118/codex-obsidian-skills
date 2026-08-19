---
name: solvenotes-vault-maintainer
description: Use when maintaining the Solvenotes Obsidian vault from outside the vault, including repository-wide validation, migration of maintenance tooling, clean export packaging, source-manifest checks, template hygiene, navigation consistency, and orchestration of the other Solvenotes note skills. Use $obsidian-vault-organizer for reusable vault cleanup, $ppt-to-md-for-obsidian for courseware extraction, and $algorithm-job-notes-for-obsidian for algorithm-job taxonomy. It keeps learning content in /notes and sends scripts, tests, and temporary outputs to Skills or /tmp.
---

# Solvenotes Vault Maintainer

Use this skill only for the Solvenotes workspace. It is the project-level
orchestrator for a learning vault; it does not replace the reusable
`obsidian-vault-organizer`, `ppt-to-md-for-obsidian`, or
`algorithm-job-notes-for-obsidian` skills.

## Boundary

- `/notes` contains notes, navigation, review pages, learning paths, and
  versioned source manifests that provide provenance.
- This skill owns maintenance scripts, tests, fixtures, package/export checks,
  and temporary diagnostics. Do not recreate these under `/notes`.
- Templates live in the hidden, versioned `.obsidian/templates/` directory and
  use `note_type: template`; they are not learning notes or navigation targets.
- Temporary reports, extracted inventories, and package files belong under
  `/tmp` or another explicitly external output directory.
- Never modify an installed skill copy directly. Edit this source repository,
  validate it, then use the repository installation scripts to synchronize the
  mirror.

## Required environment

Set the vault explicitly before invoking a maintenance command:

```bash
export SOLVENOTES_VAULT_ROOT=/absolute/path/to/solvenotes/notes
```

The scripts accept `--root` where documented, but the environment variable is
the stable interface used by the full gate and by agents. The skill must fail
clearly rather than silently treating its own `skill/` directory as a vault.

## Quick Start

1. Read the workspace and vault `AGENT.md` files and inspect Git status.
2. Run the read-only baseline checks before editing. Keep diagnostics outside
   the vault.
3. Use the generic Obsidian skill for link/frontmatter/structure work, the
   courseware skill for source-manifest and course coverage work, and the
   algorithm skill for the nine-direction algorithm-job contract and C++
   runnable examples.
4. Edit notes semantically. Preserve source manifests and move unique content
   before deleting obsolete pages or routes.
5. Run the full gate from this skill, compile only explicitly marked runnable
   code, and inspect the generated clean package.
6. Validate the source skill repository, then update the installed mirror with
   the official repository scripts. Compare source and installed metadata and
   run the installed scanner against the real vault.
7. Report actual commands and PASS/FAIL/SKIP results. Do not commit or push
   unless the user explicitly authorizes it.

## Main commands

From the Skills repository:

```bash
SOLVENOTES_VAULT_ROOT=/absolute/path/to/notes \
  bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh quick

SOLVENOTES_VAULT_ROOT=/absolute/path/to/notes \
  bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh full

SOLVENOTES_VAULT_ROOT=/absolute/path/to/notes \
  bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh online \
  --changed-only --max-urls 100 --timeout 10 --total-timeout 300

python3 skill/solvenotes-vault-maintainer/scripts/package_vault.py \
  --root /absolute/path/to/notes --output /tmp/solvenotes-notes-clean.zip
```

The package command excludes Git metadata, macOS sidecar files, Obsidian
local workspace/graph state, caches, compiled files, and previous exports.
It must not write an archive into the vault by default.

`online` is an explicit, read-only external URL audit. It is separate from
`quick`, `full`, and ordinary CI. It deduplicates HTTP(S) URLs from Markdown,
stores response records under `/tmp/solvenotes-web-cache` by default, and
distinguishes redirects, authentication/paywalls, robots or rate limits,
temporary failures, and confirmed missing resources. Use
`--offline-cache-only` for a repeatable cache-only report. Unit tests use
mocked responses; transport status alone is not a semantic or visual review.
`--timeout` bounds one request and `--total-timeout` bounds the whole scan.

## Direction contract

Algorithm-job top-level directions are exactly:

```text
cv, nlp_llm, recommendation, search, speech,
robotics, automotive, embodied_ai, ai_infra
```

The algorithm skill is the single owner of this taxonomy. Topics such as RAG,
Agent, GNN, reinforcement learning, diffusion, multimodal learning, and
advertising may occur as foundations or internal topics, but this skill must
not create them as new job directions.

## Evidence And Assumption Gate

- Read the whole candidate note before changing or deleting it.
- Move unique learning value into the most appropriate note or shared
  foundation first; then update links, aliases, frontmatter, and manifests.
- Do not leave audit reports, deprecated stubs, redirect placeholders, or
  generated inventories in `/notes`.
- Do not use lexical keyword replacement to make prose appear natural. A
  language warning is a review candidate until its surrounding claim is read.
- Formal guarantees, theorem statements, negated claims, questions, and
  quoted source language must not be weakened merely to satisfy a heuristic.

## Output Contract

The final response names the real vault and repositories changed, separates
learning-content edits from maintenance migrations, reports installed-mirror
verification, and lists exact PASS/FAIL/SKIP commands. It never claims that a
GUI review, training run, checkpoint load, OCR pass, or network fetch happened
unless it actually did.

## Validate before finishing

Run the quick gate before editing and the full gate after editing. Run the
algorithm Skill scanner and its isolated tests when algorithm-job notes are in
scope. Compile only marked C++17 examples. Run the package builder and inspect
its ZIP listing before delivering an export. Keep generated reports and caches
outside `/notes`.

## Handoff Boundaries

- `$obsidian-vault-organizer` owns reusable vault link, duplicate, navigation,
  and note-quality methods.
- `$ppt-to-md-for-obsidian` owns local courseware extraction and source
  coverage methods.
- `$algorithm-job-notes-for-obsidian` owns the nine-direction taxonomy,
  algorithm-job route checks, and marked C++ examples.
- The singular `/agent` directory owns Solvenotes execution order; this Skill
  owns the reusable external maintenance implementation.

## Bundled Resources

The `scripts/` directory is the source of the external-vault maintenance gate,
the `tests/` directory covers its behavior, and `references/validation.md`
records the project-specific validation boundary. No copy of these resources
belongs inside `/notes`.

## Editing and deletion rules

The maintenance gate must check, as applicable:

- links, ambiguous links, frontmatter, formulas, headings, tables, special
  directories, source coverage, and repository hygiene;
- high-confidence template residue, duplicate paragraphs, placeholder text,
  and empty notes;
- the nine-direction algorithm contract, DSA/C++ entry points, and explicit
  runnable C++17 blocks;
- Python fenced examples are parsed with `ast` without executing them;
- context-sensitive naturalness candidates, high-confidence placeholders, and
  exact repeated paragraphs without mechanically rewriting formal prose;
- clean export contents and absence of local Obsidian state.

Checks should report context and confidence. A checker may fail on a confirmed
structural violation, but it must not rewrite a note or classify every mention
of a word such as “保证” or “解决” as a factual error.
