# Validation Checks

Run checks after creating or updating Obsidian notes.

## Contents

- [Basic Shell Checks](#basic-shell-checks)
- [Scripted Checks](#scripted-checks)
- [Review Page Coverage](#review-page-coverage)
- [Source Coverage Audit](#source-coverage-audit)
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

Strict course-note check for long courseware, exam review, or user-requested coverage audits:

```bash
python3 scripts/check_course_notes.py --strict-depth --require-coverage-audit notes
```

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

Strict source ownership check for repositories where sources live beside the notes vault:

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

The checker treats both roots as trust boundaries: `--mapping` entries and
paper-note `source_files` must resolve beneath the selected source/notes roots.
Absolute paths, `../` escapes, and symlinks resolving outside those roots are
reported as blockers instead of being opened or counted as source evidence.
When source and note directory names differ, pass the complete explicit mapping
(for example `All-in-One : Unified Image Restoration=all-in-one,dehaze=去雾,医学人工智能导论=医学人工智能`); strict reconciliation then checks those aliases instead of guessing.
Known standalone note systems (`概念索引`, `模板`, `游戏数值策划`, `科研方法论`,
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

Treat `CHAPTER_MISMATCH_SOURCE_LINK`, `CHAPTER_MISMATCH_NOTE_SOURCE`, and `NONCANONICAL_SOURCE_REF` as blockers before delivery or upload.

## Review Page Coverage

Each course/topic directory should have:

- one detailed review page,
- one concise review page,
- overview links to both.

When the user explicitly requests a single exam review file, the two-review-page requirement may be replaced by one `考试复习` or `复习笔记` file, but the overview must link it and strict-depth validation should use `--allow-exam-review`.

`概念索引`-style cross-course index directories may be exempt when they are not a course. Use `--skip-dir <name>` for each exempt directory name instead of placing this decision in the pipeline config.

## Source Coverage Audit

For multi-file courseware, produce a source coverage note before final delivery. It should state:

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
