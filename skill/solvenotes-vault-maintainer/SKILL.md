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

- `/notes` contains notes, navigation, review pages, learning paths,
  source citations, and source metadata in note frontmatter. It contains no
  `source_manifest.md` or source-manifest history pages.
- When source coverage is needed, prepare its manifest under this task's
  `RUN_TMP` and set `SOLVENOTES_MANIFEST_ROOT` explicitly. Do not create or
  reuse sibling `vault_sources`. Use `vault-basic` for routine local checks and
  `vault-full` only with that temporary manifest. The scripts retain a sibling
  root fallback for compatibility, but the active workspace `AGENT.md` takes
  precedence. Mirror each course/topic path relative to Notes. Reject a manifest
  root inside Notes, including symlink resolutions.
- Preserve `source_files`, source URLs, and page/slide markers in learning
  notes. Resolve manifest note targets against the matching Notes directory;
  moving the manifest must not erase source ownership or weaken coverage.
  Missing, unreadable, or empty required manifests make provenance and source
  coverage FAIL/unavailable, never an empty PASS; they do not block independent
  factual verification against adequate authoritative evidence. Report source
  fidelity and independently verified correctness separately. Public synthetic
  fixtures may use `fixtures/vault_sources`;
  never copy real private mappings into the public Skills repository.
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
  vault or its private mappings. The Notes repository's hidden
  `.github/workflows/vault-quality.yml` pins this source skill to a commit.
  A real-vault source-coverage gate requires the task's temporary manifest,
  which a Notes checkout alone cannot provide. Report unavailable manifests
  explicitly instead of accepting zero files. Do not make the two repositories
  follow floating `main` branches.
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
# Only after preparing a manifest here, when source coverage is needed:
export SOLVENOTES_MANIFEST_ROOT="$RUN_TMP/source-manifests"
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

1. Read applicable `AGENTS.md` and `AGENTS.override.md` files and follow their references. Read custom `AGENT.md` files when the user, active project instructions, or an established workspace procedure explicitly designates them, then inspect Git status.
2. Create one task-specific `RUN_TMP`, point temporary-output settings such as
   `TMPDIR` at it, then run `vault-basic` for the routine source-independent
   baseline. Keep diagnostics outside the vault and clean that exact task
   directory before handoff.
3. Use the generic Obsidian skill for link/frontmatter/structure work, the
   courseware skill for source-manifest and course coverage work, and the
   algorithm skill for the nine-direction algorithm-job contract and C++
   runnable examples. Use its separate runtime contract when explicitly
   marked dependency-backed Python examples must actually execute.
4. Edit notes semantically. Preserve the external source manifests and update
   their note targets together with `source_files` when notes move. Move unique
   content before deleting obsolete pages or routes.
5. Run `vault-full` only when this task has a prepared manifest under `RUN_TMP`
   and `SOLVENOTES_MANIFEST_ROOT` points to it; compile only explicitly marked
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
  bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh vault-basic

# Run source coverage only when a task manifest is prepared under RUN_TMP.
SOLVENOTES_VAULT_ROOT=/absolute/path/to/notes \
SOLVENOTES_MANIFEST_ROOT="$RUN_TMP/source-manifests" \
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
It creates a temporary detached worktree for the target commit and installs its
dependency closure there, then validates the real Notes vault through an
override lock without changing the formal lock. Use this helper only where local
workspace rules permit temporary worktrees; otherwise validate the committed
checkout with the approved temporary install and override-lock process.
Candidate validation defaults to `vault-full`, which
requires an explicit `SOLVENOTES_MANIFEST_ROOT` and reports `source_audit: PASS`
only after the full gate succeeds. This status covers automated manifest and
source-coverage checks, not semantic or visual review. For the current source-independent local
release check, pass `--validation-profile vault-basic`; its report must say
`source_audit: NOT_RUN` and does not establish source coverage. Package
construction is not part of the default candidate gate. Add `--verify-package`
only when the user requests an export and local guidance permits package mode.
Only after the applicable candidate checks pass should
`update_notes_skill_lock.py --write` be used.

```bash
python3 skill/solvenotes-vault-maintainer/scripts/validate_notes_candidate.py \
  --notes-root /absolute/path/to/notes \
  --skills-root /absolute/path/to/skills \
  --skills-ref "$SKILLS_SHA" \
  --validation-profile vault-basic
```

The default candidate profile remains `vault-full`; selecting `vault-basic` is
explicit and records that source audit was not run. A full candidate gate must
use the task's prepared temporary manifest root. When a release closes a
dependency-backed execution gap, update the formal lock after candidate
validation, then run `vault-runtime` against the clean Skills commit and updated
lock before committing Notes. Report the selected profile and runtime gate
separately; neither a passing candidate gate nor an optional package check
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
- Before declaring numerical results conflicting, align model/configuration,
  dataset and split, metric/protocol, and version/time; matching names alone do
  not establish that they describe the same object. When transferring a result
  across chapters or versions, also verify the problem statement, data, and symbols.
- Missing courseware or manifests limits source-fidelity and coverage claims,
  not independent correctness checks. Verify against suitable authoritative
  sources when available and report the two kinds of evidence separately. A
  factual paraphrase remains a claim even when it is not verbatim or labeled
  author synthesis; that label is not evidence. A missing or mismatched
  evidence-index entry is a mapping gap, not proof the claim is false: locate
  and map support for that claim before deciding whether to retain or revise it.
- Resolve page numbers only from an explicit page/slide range or list in a locator;
  numbers in formulas, method names, or explanatory prose (for example, “11-point
  summary”) are not page identifiers. Preserve the locator and check the resolved
  page set against its explicit range or list.
- Treat browser or search-result line numbers as tool-local lookup offsets; cite the source’s own printed/physical page, section, paragraph, or stable anchor separately rather than presenting extraction offsets as source-native lines.
- When an API formula and a fixed-version implementation disagree, trace the
  actual call path and normalization, clipping, or approximation conditions.
  Record the documented contract and implementation behavior separately;
  official docs alone do not prove the implementation's numerical output.
  Check final configuration composition too: service or library defaults do
  not establish what a release bundle or profile merges. For approximations,
  set error tolerance analytically or in advance; widening it after seeing a
  discrepancy supports only a finite numerical comparison, not a theoretical
  pass. For undefined source shorthand, test plausible readings and their
  preconditions before calling it an error.
- For audit units, bind the whole-file SHA, exact physical line, and excerpt SHA
  in distinct fields; never label a whole-note SHA `range_sha256`. After line
  insertions or bulk mapping edits, preserve IDs for semantically unchanged
  units and rebind them to the exact current claim text or excerpt fingerprint.
  For changed, split, or merged units, record explicit old-to-current mappings
  rather than forcing the former segmentation or count; mark deleted units as
  retired. Bind every nested subclaim to its own current text
  as well as the enclosing excerpt, so a current outer excerpt cannot mask stale
  inner claim text. Old line numbers are navigation only and historical
  `read_ranges` remain unchanged.
  Review claim, status, and evidence deltas for unintended semantic
  migration, and fail closeout on an unexplained mismatch. When bytes
  change, update dependent records and manifests,
  including evidence `note.after_sha256` and private source-manifest fields.
  Reuse completed sentence-level reviews even when they use an older
  inventory format; a new agent, format migration, or hash change alone does
  not restart a full reread. Recheck changed claims and fill only genuinely
  uncovered scope. Keep closeout focused on review decisions, revisions, and
  source ranges rather than extending it for metadata alone.
  Before a cross-chapter shared-page edit, save its full before bytes; calculate
  coverage from the union of physical line/sentence ranges and check duplicate
  units or overlap when claiming a partition—unit count alone is not coverage.
  Classify each clause as fact, existence/mechanism, recommendation, or format.
  Use `not_a_claim` only for units with no factual, mathematical, or
  possibility assertion. Pure formatting (`$$`, standalone `\qquad`, blank
  lines), purely organizational titles (a heading asserting a fact or theorem
  remains a claim), conventions, and explicit example inputs with no asserted
  outcome qualify; a recommendation qualifies only if it makes no outcome
  claim. Equations and derived conclusions remain claims; map a multiline
  formula as one complete unit. A valid construction establishes a possibility
  claim, not real-world frequency or magnitude; untested deployment is a
  separate boundary.
  Match evidence strength to the claim: a documented mechanism or proof under
  stated assumptions can support qualitative or conditional claims without a
  real-workload benchmark; finite checks or mechanism documentation alone do
  not establish workload-specific frequency, magnitude, or performance. Mark `corrected` only when the
  claim, applicability premise, or source itself was fixed; keep neighboring
  units at their own status. Only purely structural table headers and separators,
  and non-assertive organizational lead-ins, are not claims; rows or labels that
  define tasks, enumerate interfaces or options, or assert mechanisms or costs
  remain claims. When an alternative is proposed to fix a stated defect, verify
  that it actually removes that defect (for example, content-only attention pooling over permutation-equivariant
  frame features remains permutation-invariant; replacing mean pooling alone
  does not restore order information); split mixed
  factual/recommendation clauses.
- Segment prose at semantic sentence boundaries; let unit boundaries follow
  the natural current prose, never changing punctuation or word order merely
  to preserve an earlier unit count. Keep formulas, code spans and blocks, URLs,
  and source identifiers intact while splitting; punctuation inside them is not
  a boundary, such as the semicolon in I(X;Y).
- Keep task-generated evidence snapshots and ledgers in `RUN_TMP` and remove
  them at handoff; do not create durable audit archives. When reviewing a
  user-supplied existing archive, merge new records with accepted records; a
  missing temporary copy alone does not revoke prior review. If an archive is
  explicitly required, preserve exact referenced files, unique task-relative
  paths or version keys, SHA-256 references, and distinct current versus
  historical artifacts; never key records by basename alone.
  Once a candidate, record, or map has been returned for review, never overwrite
  that path; save revisions under a new versioned path, and have the reviewer freeze
  and verify the returned path/SHA-256 before reading it.
- Before an evidence-producing run, preserve the exact script and any mutable
  input bytes with their paths and SHA-256 values; capture interpreter/version
  and execution-time identities where observable, and report unavailable
  identities rather than substituting later bytes. Capture each run under a
  unique run name; never overwrite prior stdout, stderr, or exit metadata. Let
  the child process exit, save both streams and the exit record, freeze the
  audit record, then write the outer manifest. Do not make a build depend on
  hashes for files that build has not yet produced. If a legacy capture path was
  reused and raw bytes are gone, keep only an explicitly retrospective loss
  note; never reconstruct it as the original.
- Keep semantic evidence separate from runtime status. A mathematical or
  documentary claim can be verified from its proof or source without executing
  software; a passing run supports only the behavior tested and does not
  validate the whole note.
- For claims that depend on reload or recovery behavior, check which promise the
  caller actually awaits. Distinguish synchronous candidate read/import or
  validation rejection before application side effects from a later asynchronous
  activation failure, and exercise only relevant paths the implementation can
  reach. If side effects were applied, assess rollback and rollback failure as
  separate outcomes. Verify restored state before claiming recovery.
- A paper's statement that a theorem holds supports attribution only, not
  mathematical validity. Check the proof's domain, quantifiers, dependency
  structure, and whether each condition is necessary, sufficient, or both; do
  not report a sufficient condition as necessary. For expectation or
  group-normalization arguments, retain joint randomness and the zero-variance
  definition. Record missing proof conditions as unverified instead of importing
  a guarantee from a similar theorem.
- After generating an audit record, validate field types and allowed status
  values; split mixed claims into subitems. Check that positional-argument
  errors have not placed limitations or evidence in `status`. These structural
  checks validate record shape, not the claims themselves.
- Resolve every audit-unit evidence ID against the declared source IDs and
  check its source path, hash, and page or line selector; a misspelled or
  undeclared ID does not support a claim. Each locator must support the exact
  current subclaim; do not derive a shared-page evidence locator mechanically
  from the corresponding main-note line.
- Require each declared `source_id` to be unique within its record or manifest so
  every reference names one exact source version. Reconcile aggregate counts and
  Boolean coverage flags with unit-level statuses and supporting evidence, state
  the denominator, and never let a generic `true` flag or empty references
  upgrade an `unverified` unit. When a checker claims coverage by evidence type,
  make each required branch reachable from its inputs and backed by a matching
  referenced unit; fail when a required branch is empty or filtered out. Passing
  only the surviving branches does not cover omitted evidence types.
- When a mutable note is cited as evidence and may be edited during the task,
  preserve its exact pre-edit bytes and SHA-256 in `RUN_TMP` before editing it.
  Bind the reviewed claim to that snapshot and track later bytes as a separate
  version; a mutable path alone does not preserve the evidence actually reviewed.
- For code claims that a field reaches rendered output or a request, trace
  template placeholders, conditional final `payload` assembly, and how callers
  consume returned values or status; parameter names, comments, intermediate
  assignments, or a callee's success flag alone do not prove end-to-end behavior.
- For reductions and decision procedures, check the yes/no mapping direction
  for every case, including malformed encodings when the map is total. A
  structural PASS does not establish semantic correctness.
- Before comparing metrics, verify each metric's objective direction: higher,
  lower, or a target range may be preferred depending on the metric.

## Output Contract

The final response names the real vault and repositories changed, separates
learning-content edits from maintenance migrations, reports installed-mirror
verification, and lists exact PASS/FAIL/SKIP commands. It never claims that a
GUI review, training run, checkpoint load, OCR pass, or network fetch happened
unless it actually did.

## Validate before finishing

Run `vault-basic` before editing and after source-independent changes. Run
`vault-full` only when a task manifest has been prepared under `RUN_TMP` and
`SOLVENOTES_MANIFEST_ROOT` points to it. Run the algorithm Skill scanner and
its isolated tests when algorithm-job notes are in scope. Compile only marked
C++17 examples. When dependency-level execution is requested, also run
`vault-runtime` and report its executed-block count. Run the package builder
and inspect its ZIP listing before delivering an export. Keep generated reports
and caches outside `/notes`.

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
