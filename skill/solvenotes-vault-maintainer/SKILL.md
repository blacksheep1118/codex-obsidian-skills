---
name: solvenotes-vault-maintainer
description: Use when maintaining the Solvenotes Obsidian vault from outside the vault, including repository-wide validation, migration of maintenance tooling, clean export packaging, source-manifest checks, template hygiene, navigation consistency, and orchestration of the other Solvenotes note skills. Use $obsidian-vault-organizer for reusable vault cleanup, $ppt-to-md-for-obsidian for courseware extraction, and $algorithm-job-notes-for-obsidian for algorithm-job taxonomy. It keeps learning content in /notes and sends scripts, tests, and temporary outputs to Skills or one task-specific temporary directory.
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
- Create one task-specific `RUN_TMP` outside the workspace. Route temporary
  reports, extracted inventories, caches, subprocess homes, and any explicitly
  authorized package files into that directory; remove that exact directory at
  handoff after checking that it contains no requested deliverable.
- The public Skills repository must remain self-contained: its CI uses source
  code and non-sensitive fixtures only, and never checks out a private Notes
  vault. The real-vault quick/full gate belongs to the Notes repository's
  hidden `.github/workflows/vault-quality.yml`, which pins this source skill to
  a commit. Do not make the two repositories follow floating `main` branches.
- Never modify an installed skill copy directly. Edit this source repository,
  validate it, then use the repository installation scripts to synchronize the
  mirror.
- A real Notes vault pins the exact Skills source and required dependency closure in
  `notes/.github/solvenotes-skills.lock.json`. The lock stores one full 40-character
  lowercase-hexadecimal
  commit SHA, `contract_version`, per-Skill runtime digests, and the dependency
  graph digest; do not copy a floating branch or a second
  SHA into another document. Validate it with `check_skills_lock.py` before a
  full gate. Use `update_notes_skill_lock.py` in dry-run mode first; `--write`
  only changes the lock and never commits or pushes.

## Required environment

Set the vault explicitly before invoking a maintenance command:

```bash
export SOLVENOTES_VAULT_ROOT=/absolute/path/to/solvenotes/notes
RUN_TMP="$(mktemp -d)"
export RUN_TMP TMPDIR="$RUN_TMP" SOLVENOTES_TMP_ROOT="$RUN_TMP"
```

Each maintenance subprocess is bounded by `SOLVENOTES_STEP_TIMEOUT` seconds
(180 by default). The timeout wrapper reports the command, elapsed time, and
stdout/stderr tails, and terminates the child process group where the platform
supports it.

The scripts accept `--root` where documented, but the environment variable is
the stable interface used by the full gate and by agents. The skill must fail
clearly rather than silently treating its own `skill/` directory as a vault.
Run `scripts/doctor.py --profile PROFILE --strict` before a long gate when the
environment is uncertain. It reads the shared validation-profile contract and
reports the selected interpreter, dependency versions, system tools, vault
path, and Skills path without using machine-specific fallbacks.

## Quick Start

1. Read the workspace and vault `AGENT.md` files and inspect Git status.
2. Create one task-specific `RUN_TMP`, point temporary-output settings such as
   `TMPDIR` at it, then run the read-only baseline checks. Keep diagnostics
   outside the vault and clean the exact task directory before handoff.
3. Use the generic Obsidian skill for link/frontmatter/structure work, the
   courseware skill for source-manifest and course coverage work, and the
   algorithm skill for the nine-direction algorithm-job contract and C++
   runnable examples. Use its separate runtime contract when explicitly
   marked dependency-backed Python examples must actually execute.
4. Edit notes semantically. Preserve source manifests and move unique content
   before deleting obsolete pages or routes.
5. Run the full gate from this skill and compile only explicitly marked
   runnable code. Build and verify a clean package outside the vault only when
   the user requests an export and local guidance permits package mode.
6. Validate the source skill repository and use the official update script in
   dry-run mode to compare source and installed metadata. Update the real
   installed mirror, then run its scanner against the vault, only when the user
   explicitly authorizes synchronization.
7. Report actual commands and PASS/FAIL/SKIP results. Do not commit or push
   unless the user explicitly authorizes it.

The current maintainer contract is version `2`. It covers the external vault
root, the lock format, the source-manifest boundary, the algorithm-job
nine-direction handoff, the maintainer-to-algorithm dependency closure,
marked runnable-code checks, the tool/vault command
surface, and clean-package exclusions. A version mismatch must fail before the
expensive vault scan.

## Main commands

From the Skills repository. The package and verification commands in this block
are conditional: use them only when the user requests an export and local
guidance permits package mode.

```bash
SOLVENOTES_VAULT_ROOT=/absolute/path/to/notes \
  bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh vault-quick

SOLVENOTES_VAULT_ROOT=/absolute/path/to/notes \
  bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh vault-full

SOLVENOTES_VAULT_ROOT=/absolute/path/to/notes \
SOLVENOTES_PYTHON_BIN=/absolute/path/to/solvenotes-runtime/bin/python \
SOLVENOTES_RUNTIME_REVIEWED=1 \
JAVA_HOME=/absolute/path/to/jdk-17 \
PATH="/absolute/path/to/jdk-17/bin:$PATH" \
  bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh vault-runtime

SOLVENOTES_VAULT_ROOT=/absolute/path/to/notes \
  bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh online \
  --changed-only --max-urls 100 --timeout 10 --total-timeout 300

python3 skill/solvenotes-vault-maintainer/scripts/package_vault.py \
  --root /absolute/path/to/notes \
  --output "$RUN_TMP/solvenotes-notes-clean.zip" \
  --manifest-output "$RUN_TMP/solvenotes-notes-PACKAGE-MANIFEST.json"

python3 skill/solvenotes-vault-maintainer/scripts/verify_vault_package.py \
  "$RUN_TMP/solvenotes-notes-clean.zip" \
  --sidecar "$RUN_TMP/solvenotes-notes-PACKAGE-MANIFEST.json"

python3 skill/solvenotes-vault-maintainer/scripts/package_workspace.py \
  --root /path/to/solvenotes \
  --output "$RUN_TMP/solvenotes-workspace.zip" \
  --manifest-output "$RUN_TMP/solvenotes-workspace-BUILD-MANIFEST.json"

python3 skill/solvenotes-vault-maintainer/scripts/verify_workspace_package.py \
  "$RUN_TMP/solvenotes-workspace.zip" \
  --sidecar "$RUN_TMP/solvenotes-workspace-BUILD-MANIFEST.json"
```

Before changing the formal Notes lock, run
`validate_notes_candidate.py --notes-root ... --skills-root ... --skills-ref ...`.
It installs the target commit and its dependency closure in a temporary
location, runs `vault-full` against the real Notes vault through an override
lock, and leaves the formal lock unchanged. Package construction is not part of
the default candidate gate. Add `--verify-package` only when the user requests
an export and local guidance permits package mode. Only after the applicable
candidate checks pass should `update_notes_skill_lock.py --write` be used.

Candidate validation deliberately runs `vault-full`, not reviewed local code.
When the release closes a dependency-backed execution gap, update the formal
lock after the candidate passes, then run `vault-runtime` against the clean
Skills commit and updated lock before committing Notes. Report the two gates
separately; neither a passing candidate full gate nor an optional package check
implies ONNX or Spark execution.

The Notes learning package embeds a deterministic file manifest and excludes
Git metadata, macOS sidecar files, Obsidian local workspace/graph state, hidden
CI infrastructure, caches, compiled files, and previous exports. Verify it
without extraction before delivery. The workspace diagnostic package
intentionally keeps only the necessary hidden CI files under `notes/.github/`.
It must not write an archive into the vault by default.

`package_workspace.py` is a separate maintainer diagnostic package for the
four-part workspace (`AGENT.md`, `agent/`, `notes/`, and `skills/`). It keeps
source files but excludes Git history, local Obsidian state, caches, archives,
local configuration, and machine-specific metadata. It writes a non-secret
`BUILD-MANIFEST.json` into the ZIP and to the explicitly selected sidecar
path; both outputs should remain outside the workspace.

`online` is an explicit, read-only external URL audit. It is separate from
`quick`, `full`, and ordinary CI. It deduplicates HTTP(S) URLs from Markdown,
stores response records under `$SOLVENOTES_TMP_ROOT/solvenotes-web-cache` by default, and
distinguishes redirects, authentication/paywalls, robots or rate limits,
temporary failures, and confirmed missing resources. Use
`--offline-cache-only` for a repeatable cache-only report. Unit tests use
mocked responses; transport status alone is not a semantic or visual review.
`--timeout` bounds one request and `--total-timeout` bounds the whole scan.

`vault-runtime` is likewise explicit and separate from `vault-full` and
ordinary public CI. It first checks the pinned optional environment, then
executes only Python fences immediately preceded by an exact `python-e2e`
marker. Missing dependencies, unsupported Java, no marked coverage, timeout,
excessive output, or a nonzero example exit must fail; none may be reported as
a passing skip. It is a reviewed-local-code gate rather than an OS sandbox and
must not run on untrusted pull requests. Read the algorithm skill's
`references/python-runtime-validation.md` before using this mode.

For the complete workspace surface, run
`check_workspace_guidance.py --workspace-root /path/to/solvenotes`. It checks
the singular `agent/` boundary, portable guidance paths, the Notes lock, and
that the Notes workflow does not carry a second Skills SHA. It is a local
guidance check, not a replacement for Notes content validation.
The companion `check_documented_commands.py` checks script paths named by the
workspace guidance and Skill documentation without executing arbitrary shell
blocks; only paths that resolve to real files are accepted.

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
scope. Compile only marked C++17 examples. When dependency-level execution is
requested, also run `vault-runtime` and report its executed-block count. Run
the package builder and inspect its ZIP listing before delivering an export.
Keep generated reports and caches outside `/notes`.

## Handoff Boundaries

- `$obsidian-vault-organizer` owns reusable vault link, duplicate, navigation,
  and note-quality methods.
- `$ppt-to-md-for-obsidian` owns local courseware extraction and source
  coverage methods.
- `$algorithm-job-notes-for-obsidian` owns the nine-direction taxonomy,
  algorithm-job route checks, marked C++ examples, and the reviewed
  dependency-backed Python runtime marker.
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
- Ordinary Python fenced examples are parsed with `ast` without executing
  them; the separate `vault-runtime` gate may execute only reviewed
  `python-e2e` blocks and must fail if declared dependencies are unavailable;
- context-sensitive naturalness candidates, high-confidence placeholders, and
  exact repeated paragraphs, sentences, and language-like list items without
  mechanically rewriting formal prose;
- clean export contents and absence of local Obsidian state.

Checks should report context and confidence. A checker may fail on a confirmed
structural violation, but it must not rewrite a note or classify every mention
of a word such as “保证” or “解决” as a factual error.
