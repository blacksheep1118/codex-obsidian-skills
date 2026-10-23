# Sentence-Level Evidence Review

Read this reference when a user explicitly requests sentence- or claim-level review, or when the task requires creating or reconciling audit units, source/evidence IDs and locators, hashes, or an evidence-producing audit record. Ordinary note maintenance and routine source checks use the main skill's evidence gate; this procedure does not require an audit ledger for those tasks.

Keep any task-generated snapshots and ledgers in `RUN_TMP`, and follow the main skill's privacy, source, and permission boundaries. The detailed rules below preserve the review invariants for tasks that actually use sentence-level records.

## Contents

- [Claim units and scope](#claim-units-and-scope)
- [Evidence snapshots and mutable inputs](#evidence-snapshots-and-mutable-inputs)
- [Record structure and source mapping](#record-structure-and-source-mapping)
- [Semantic and technical claim checks](#semantic-and-technical-claim-checks)

## Claim units and scope

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

## Evidence snapshots and mutable inputs

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
- When a mutable note is cited as evidence and may be edited during the task,
  preserve its exact pre-edit bytes and SHA-256 in `RUN_TMP` before editing it.
  Bind the reviewed claim to that snapshot and track later bytes as a separate
  version; a mutable path alone does not preserve the evidence actually reviewed.

## Record structure and source mapping

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

## Semantic and technical claim checks

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
- For code claims that a field reaches rendered output or a request, trace
  template placeholders, conditional final `payload` assembly, and how callers
  consume returned values or status; parameter names, comments, intermediate
  assignments, or a callee's success flag alone do not prove end-to-end behavior.
- For reductions and decision procedures, check the yes/no mapping direction
  for every case, including malformed encodings when the map is total. A
  structural PASS does not establish semantic correctness.
- Before comparing metrics, verify each metric's objective direction: higher,
  lower, or a target range may be preferred depending on the metric.
