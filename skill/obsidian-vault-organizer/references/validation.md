# Validation Checks

Run checks after creating or updating Obsidian notes.

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

Adjust `notes` to the resolved vault path.

## Scripted Link Check

Check Obsidian links:

```bash
python3 scripts/check_obsidian_links.py notes
```

```powershell
py scripts\check_obsidian_links.py notes
```

The checker scans Markdown inline destinations, used full/collapsed/shortcut reference links, and Obsidian wikilinks, while masking fenced code, inline code, HTML comments, and Obsidian comments. Reference labels use case-folding and whitespace normalization; an unused definition is not counted as a link. It checks Markdown heading anchors, nested heading paths, and explicit block IDs, excluding a leading Obsidian YAML property block from anchor discovery. Format-specific fragments on attachments and dynamic heading/block search links are recognized but cannot be resolved to one fixed target statically. The checker covers examples such as:

- `[text](path/to/file.md)`
- `[[path/to/file|label]]`
- `[[file stem]]`
- `[display text][reference]`, `[display text][]`, and `[reference]` with a matching `[reference]: path/to/file.md "title"` definition

The generic command scans Markdown files under the selected root, including hidden folders such as `.obsidian/templates`. The Solvenotes maintainer gate uses its existing learning-note inventory and excludes `.obsidian/templates` from both source and Markdown target resolution. The checker tests whether a destination resolves within the selected vault. It does not judge whether a link is useful, whether the relationship is conceptually correct, or whether a backlink should exist. Review those choices in context; do not add reciprocal links just to make links mechanically bidirectional.

Reference-definition parsing currently covers single-line, unquoted definitions (with an optional same-line title). Multiline definitions, definitions inside blockquotes/list containers, and Markdown image embeds require separate manual review; do not report those forms as validated by this checker.

Report broken links and self-links before making content claims.

## Temporary Presentation Text Boundary

`scripts/extract_presentation_text.py` is a last-resort text-hint extractor for manual source comparison. Preserve its leading extraction metadata: both PPTX ZIP/XML and legacy OLE/CFB paths are partial, perform no OCR or complete visual/layout inspection, and do not provide dependable speaker-note coverage. Do not count the metadata as course content or use the text artifact alone to claim complete slide coverage.

## Strict Solvenotes Report Gate

Reject legacy audit/report pages in each Solvenotes course directory:

```bash
python3 scripts/check_vault_quality.py --strict-study --profile solvenotes --forbid-report-notes /path/to/course
```

Solvenotes always reports `99_内容覆盖审查.md` and audit/report note types as `REPORT_NOTE`, even when a typed sibling manifest exists or the generic compatibility flag is supplied. Keep the self-contained `source_manifest.md` in the external store selected by `SOLVENOTES_MANIFEST_ROOT` (default `Notes.parent / "vault_sources"`), mirroring the course/topic path relative to Notes. Neither manifests nor temporary ledgers belong in Notes. Preserve note `source_files` and source citations; a missing required manifest makes provenance and source coverage FAIL/unavailable, never an empty PASS, but does not block independent factual verification against adequate authoritative sources. Report these results separately. See `solvenotes-profile.md` for nested-topic skip rules.

For a non-Solvenotes vault that deliberately retains the typed legacy pair, the generic profile can opt in explicitly:

```bash
python3 scripts/check_vault_quality.py --profile generic --forbid-report-notes --allow-formal-coverage-audits /path/to/course
```

## Manual Review

Before finishing substantial edits, confirm:

- source files were not modified unless explicitly requested,
- no duplicate same-topic note was introduced,
- navigation pages link newly added or renamed notes,
- review pages remain separate when the vault expects detailed and concise versions,
- block math delimiters are balanced,
- empty files and conflict markers are absent.
