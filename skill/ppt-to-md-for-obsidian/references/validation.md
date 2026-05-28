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

If the user requested one exam review file instead of separate detailed and concise review pages:

```bash
python3 scripts/check_course_notes.py --strict-depth --allow-exam-review --require-coverage-audit notes
```

Use stricter thresholds when the source material is large:

```bash
python3 scripts/check_course_notes.py --strict-depth --allow-exam-review --require-coverage-audit --min-chapter-lines 250 --min-exam-review-lines 800 notes
```

## Review Page Coverage

Each course/topic directory should have:

- one detailed review page,
- one concise review page,
- overview links to both.

When the user explicitly requests a single exam review file, the two-review-page requirement may be replaced by one `考试复习` or `复习笔记` file, but the overview must link it and strict-depth validation should use `--allow-exam-review`.

`概念索引`-style cross-course index directories may be exempt when they are not a course.

## Source Coverage Audit

For multi-file courseware, produce a source coverage note before final delivery. It should state:

- which source files were used,
- which chapter or review note covers each in-scope source file,
- which source sections were excluded because the user marked them out of scope,
- which formulas, examples, or diagrams were noisy and need manual review.

Do not treat a short concept list as sufficient coverage when the source includes derivations, examples, algorithms, or calculation procedures.

## Link Checks

For a robust check, parse both Markdown links and Obsidian wiki links:

- `[text](path/to/file.md)`
- `[[path/to/file|label]]`
- `[[file stem]]`

Report broken links and self-links before making content claims.

`scripts/check_obsidian_links.py` implements this check for local Markdown vaults.
