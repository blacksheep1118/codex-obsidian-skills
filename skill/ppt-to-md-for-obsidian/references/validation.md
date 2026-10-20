# Validation Checks

Run checks after creating or updating Obsidian notes.

## Contents

- [Basic Shell Checks](#basic-shell-checks)
- [Scripted Checks](#scripted-checks)
- [Rendered Text And Fonts](#rendered-text-and-fonts)
- [Conversion Failures And Derived Copies](#conversion-failures-and-derived-copies)
- [Source Tables And Model Conditions](#source-tables-and-model-conditions)
- [Replacement Constructions](#replacement-constructions)
- [Review Page Coverage](#review-page-coverage)
- [Solvenotes Manifest-Only Coverage](#solvenotes-manifest-only-coverage)
- [Generic Source Coverage Audit](#generic-source-coverage-audit)
- [Link Checks](#link-checks)

## Basic Shell Checks

macOS/Linux:

```bash
find notes -name '*.md' | wc -l
find notes -name '.DS_Store' -print
rg -n '<<<<<<<|=======|>>>>>>>' notes --glob '*.md'
rg -n '相关知识链接|TODO|FIXME|待补|待完善' notes --glob '*.md'
```

Windows PowerShell:

```powershell
(Get-ChildItem notes -Recurse -Filter *.md).Count
Get-ChildItem notes -Recurse -Force -Filter .DS_Store
Select-String -Path (Get-ChildItem notes -Recurse -Filter *.md).FullName -Pattern '<<<<<<<|=======|>>>>>>>'
Select-String -Path (Get-ChildItem notes -Recurse -Filter *.md).FullName -Pattern '相关知识链接|TODO|FIXME|待补|待完善'
```

## Scripted Checks

Check Obsidian links:

```bash
python3 scripts/check_obsidian_links.py notes
```

```powershell
py scripts\check_obsidian_links.py notes
```

Validate this skill repository:

```bash
python3 scripts/validate_skill_repo.py
```

```powershell
py scripts\validate_skill_repo.py
```

Compile scripts:

```bash
python3 -m compileall scripts
```

```powershell
py -m compileall scripts
```

Run tests:

```bash
python3 -m pytest
```

```powershell
py -m pytest
```

Run the deterministic pipeline:

```bash
python3 scripts/ppt_to_obsidian_pipeline.py --config skill-config.example.yaml
```

```powershell
py scripts\ppt_to_obsidian_pipeline.py --config skill-config.example.yaml
```

For a generic vault whose local contract requires a separate audit page, use:

```bash
python3 scripts/check_course_notes.py --strict-depth --require-coverage-audit notes
```

Do not use `--require-coverage-audit` for Solvenotes. Its local contract requires a self-contained external `source_manifest.md` and forbids both in-vault manifests and the legacy audit page.

Exclude non-course generated index or audit folders by directory name when validating a broader notes tree:

```bash
python3 scripts/check_course_notes.py --skip-dir 概念索引 --skip-dir 生成审查 notes
```

```powershell
py scripts\check_course_notes.py --skip-dir 概念索引 --skip-dir 生成审查 notes
```

If the user requested one exam review file instead of separate detailed and concise review pages:

```bash
python3 scripts/check_course_notes.py --strict-depth --allow-exam-review --require-coverage-audit notes
```

Use stricter thresholds when the source material is large:

```bash
python3 scripts/check_course_notes.py --strict-depth --allow-exam-review --require-coverage-audit --min-chapter-lines 250 --min-exam-review-lines 800 notes
```

## Rendered Text And Fonts

Text extraction and visible glyphs can disagree: a PDF converted from Chinese
slides can contain searchable text while showing only punctuation, numbers, or
Latin letters. Before reviewing a converted deck, render a text-dense page and
a formula/table page, then open the images. Successful conversion, page counts,
and nonempty `pdftotext` output do not establish readable visual evidence.

If the rendered text is missing, inspect `pdffonts` and the converter's font
configuration. When LibreOffice uses Fontconfig, point `FONTCONFIG_FILE` to a
small task-local configuration that names existing font directories and a
writable task-local `<cachedir>`. On macOS, `/System/Library/Fonts/Supplemental`
may contain usable CJK fonts such as Songti or Arial Unicode; verify their
presence rather than assuming it. Set `XDG_CACHE_HOME` inside the same task
temporary directory and, if needed, `SAL_FONTPATH` to the verified font directory.
Use a fresh `-env:UserInstallation=file:///...` profile inside that task directory
so a prior conversion's cached fallback fonts are not reused. Keep the source
slides and global font configuration unchanged.

Reconvert and reopen the affected rendered pages. Check for clipping and changed
line breaks as well as restored glyphs: substitute fonts may change layout.
Record the pages actually inspected and any remaining animation, notes, or
layout limitations. Withdraw a missing-glyph limitation only after this readback;
do not mark all pages visually reviewed from a successful sample.

## Conversion Failures And Derived Copies

A converter load error does not establish that the source is empty or
unrecoverable. Inspect its actual file signature and available read-only
extraction before concluding that evidence is unavailable; an extension can
misidentify an older Office binary file. Legacy PPT text records may include
masters or obsolete objects, so record order alone does not establish slide
order, slide count, or full visual coverage.

If a specific malformed metadata field is demonstrated against the published
format specification, a minimal repair may be tried on a task-local copy.
Do not patch by guesswork or alter the original. Record original/derived hashes,
the field and offset, old/new values, and the specification. Verify the exact
byte or stream difference and that unrelated text and media streams are
unchanged. A successful conversion of this derivative still requires rendered
page review and reconciliation with the original extraction. Preserve this
provenance with the external audit evidence before cleaning temporary files;
never silently present a repaired derivative as the untouched source.

## Source Tables And Model Conditions

Read figures and tables visually as well as through extracted text. Check arrow
direction versus level, axes, units, dates, footnotes, omitted rows, and whether
multiple classification columns agree. If a source gives conflicting criteria
without a priority rule, retain that limitation rather than inventing a unique
classification algorithm. Match dated rules to the actual version of the
original document, not its filename or a later summary.

When a course table is wrong, separate its literal transcription from a
corrected teaching table. Put the independently verified value and unit in the
teaching table, and briefly note the source's differing label or value. Label
added conditions and use an independent derivation or counterexample where
possible. Examples include ratio denominators, average versus end-of-period
balances, expected versus realized quantities, percentage numbers versus decimal
rates, and per-share versus aggregate values. Keep empirical lifecycle labels or
historical performance rankings scoped to their source; algebraic or static
checks do not verify those observations. Synchronize any corrected units,
symbols, domains, and examples across chapter and review copies.

Compare a displayed formula with numeric values in the same source, including
chart legends. A formula slide and a software screenshot may use incompatible
conventions; recompute both before choosing and explicitly name the adopted
definition. Distinguish price multiples from interval proportions and their
reference direction. Check strict versus non-strict boundaries, initialization,
and zero denominators instead of testing only a typical input.

For origin or authorship claims, distinguish invention, co-development,
popularization, and later extensions. Check the primary publisher or author
for corrections; a repeated textbook attribution can still be incomplete.
Record unverified historical claims as such rather than silently certifying
them through agreement with the slides.

Separate a published taxonomy from the subset actually measured in a dataset.
A conceptual category can be excluded from the reported estimate. Preserve
bullet indentation and diagram nesting: a subtype must not become an additional
peer category merely because text extraction flattens the slide.

For ratios and accounting examples, establish the population, period, unit and
boundary before calculating. Aggregate a ratio from its totals or the correct
denominator weights, not an unweighted average. Distinguish energy from power,
and payments between parties from resources consumed across the whole system;
a fee can be one party's cost and another's revenue. A lower intensity with a
higher total does not by itself establish a causal rebound effect.

Treat a policy proposal, an exploratory framework, enacted law and an individual
judgment as different evidence. Read operative conditions and exceptions in the
applicable primary text. Do not project a later framework into an earlier
judgment or infer legal status from a classroom label. Similarly, distinguish a
parameter-region diagram from a universal conclusion: if the model equations
are unavailable, record that its boundaries have not been independently derived.

For payoff tables, reconstruct each cell from the stated assumptions and test
best responses against every relevant opponent choice or state. A higher
expected payoff under a chosen probability distribution is not pointwise strict
dominance. State the probability domain, accounting period, common terms that
cancel, any fixed-income or fixed-cost assumptions, and the decision criterion
(such as risk neutrality). Include equality and a counterexample when a source
jumps from an expected comparison to an unconditional claim.

A company publication can establish what the company reported at that date;
it does not independently establish a causal improvement or its current
architecture. Distinguish a descriptive taxonomy from a required sequence of
stages, and preserve case dates when later evidence has not been checked.

Check the measurement object as well as its unit: output, welfare, revenue,
resource cost and transfers answer different questions. A missing welfare term
is not automatically an error in a production statistic; a redistribution alone
does not establish lost aggregate output. Compare multi-period costs and benefits
on a consistent present-value basis, and distinguish a proposed explanation from
an empirically identified cause.

Read each component's statistical boundary in the cited edition before applying
one common rule. A framework can use cross-border goods statistics alongside
resident/non-resident services statistics. Likewise, an excluded ordering method
may still be a valid delivery method. Keep definition, national survey coverage,
platform intermediation fees and the underlying transaction value distinct.

## Replacement Constructions

Use this check specifically when a newly proposed grammar, language decomposition,
or other construction is meant to overturn an existing theoretical conclusion.
For a grammar `G` claimed to generate `L`, establish both directions: every
string generated by `G` satisfies the definition of `L` (soundness), and every
string in `L` has a derivation in `G` (completeness). State the induction
parameter and verify the base case and recursive step; do not infer either
inclusion from a few matching examples.

For recursive productions, expand at least two recursive levels when practical
and check positive as well as negative examples. This is a useful way to catch
bad nesting, but it is not a mechanical requirement for unrelated theoretical
proofs. For example, `T → a T b c | ε` yields `aabcbc` after two recursive
steps. If the intended language is `{a^n b^n c^n : n ≥ 0}`, that word is not in
the language, while the valid target word `aabbcc` shows the missing block-order
case. A one-step check would see only `abc` and miss the defect.

Finite enumeration can expose a counterexample but cannot prove a universal
claim. Likewise, showing that two CFL components overlap does not alone prove
that their union is inherently ambiguous: it may show ambiguity of one chosen
grammar, whereas inherent ambiguity quantifies over every equivalent grammar.
Use a complete proof or an authoritative source for that stronger conclusion;
otherwise preserve the source's statement and mark independent verification as
unfinished.

## Solvenotes Manifest-Only Coverage

Run these external maintainer commands from the Solvenotes Skills repository:

```bash
export SOLVENOTES_VAULT_ROOT=/path/to/solvenotes/notes
# Optional; omit to use Notes.parent / "vault_sources".
export SOLVENOTES_MANIFEST_ROOT=/path/to/solvenotes/vault_sources
python3 skill/solvenotes-vault-maintainer/scripts/check_source_coverage.py --json
SOLVENOTES_SOURCE_ROOT=/path/to/source-root \
  python3 skill/solvenotes-vault-maintainer/scripts/check_source_files.py --strict --json
```

The first command validates the formal manifest schema, mappings, statuses, dates, target links, limitations, and the absence of legacy audit pages. The strict source command checks source existence, unit counts, extractability, and blank/OCR/visual limitations. Formal manifests mirror the Notes-relative course/topic directory under the external root; their note targets resolve against the corresponding Notes directory. Reject roots inside Notes, including symlink resolutions. Keep private mappings out of the public Skills repository and preserve note `source_files` and source citations. Missing required manifests or a missing source root are FAIL/unavailable for the relevant coverage check, never an empty PASS. Temporary ledgers also stay outside the vault.

The bundled generic strict source ownership check below is for other repositories where sources live beside the notes vault. For Solvenotes, use the external maintainer commands above; do not copy manifests into Notes to satisfy a generic checker:

```bash
python3 scripts/check_source_coverage.py \
  --source-root /path/to/course-root \
  --notes-root /path/to/course-root/notes \
  --mapping '数学模型=数学模型,编译原理=编译原理' \
  --require-course-prefixed-source-refs

# Strict mode also discovers same-name source/note directories (including
# cs231n), checks manifest/audit/note ownership separately, reconciles source
# directories, and validates local paper-note source ownership.
python3 scripts/check_source_coverage.py \
  --source-root /path/to/course-root \
  --notes-root /path/to/course-root/notes \
  --strict \
  --require-course-prefixed-source-refs
```

The checker treats both roots as trust boundaries. Mapping paths must remain
beneath the selected source/notes roots. A paper-note `source_files` entry or
local body source reference must use the exact root-relative spelling of an
existing regular file. Absolute paths, `../` escapes, case aliases, directory
targets, and every leaf or ancestor symlink (including broken links) are
reported as blockers instead of being opened or counted as source evidence.
When source and note directory names differ, pass the complete explicit mapping
(for example `All-in-One : Unified Image Restoration=all-in-one,dehaze=去雾,医学人工智能导论=医学人工智能`); strict reconciliation then checks those aliases instead of guessing.
Known standalone note systems (`概念索引`, `模板`, `游戏数值策划`, `科研方法论`,
`算法岗学习笔记`, `学习路径`,
or a matching standalone `note_type`) are excluded from course source-dir
reconciliation and should not be added as fake source mappings.

For this check, do not treat `course_note_issues 0` as enough. The strict source pass should also show:

- `missing_source_mappings 0`
- `four_way_source_issues 0`
- `source_dir_reconciliation_issues 0`
- `paper_source_ownership_issues 0`
- `text_hygiene_issues 0`
- `source_table_issues 0`
- `note_source_ownership_issues 0`
- `coverage_evidence_issues 0`

Treat `MANIFEST_TARGET_OWNER_MISMATCH`, `BODY_SOURCE_OWNER_MISMATCH`, and `NONCANONICAL_SOURCE_REF` as blockers before delivery or upload.

## Review Page Coverage

Each course/topic directory should have:

- one detailed review page,
- one concise review page,
- overview links to both.

When the user explicitly requests a single exam review file, the two-review-page requirement may be replaced by one `考试复习` or `复习笔记` file, but the overview must link it and strict-depth validation should use `--allow-exam-review`.

`概念索引`-style cross-course index directories may be exempt when they are not a course. Use `--skip-dir <name>` for each exempt directory name instead of placing this decision in the pipeline config.

## Generic Source Coverage Audit

For a non-Solvenotes vault whose local guidance requires a separate coverage note, produce it before final delivery. It should state:

- which source files were used,
- which chapter or review note covers each in-scope source file,
- which source sections were excluded because the user marked them out of scope,
- which formulas, examples, or diagrams were noisy and need manual review.

Do not treat a short concept list as sufficient coverage when the source includes derivations, examples, algorithms, or calculation procedures.

When moving page-level supplement lines between notes, rerun the source ownership check and a direct `rg` for the moved source filenames in the old notes. The old notes should not retain source-evidence lines for the moved PPT/PDF.

## Link Checks

For a robust check, parse both Markdown links and Obsidian wiki links:

- `[text](path/to/file.md)`
- `[[path/to/file|label]]`
- `[[file stem]]`

Report broken links and self-links before making content claims.

`scripts/check_obsidian_links.py` implements this check for local Markdown vaults.
