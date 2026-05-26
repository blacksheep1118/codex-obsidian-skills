# Validation Checks

Run checks after creating or updating Obsidian notes.

## Basic Shell Checks

```bash
find notes -name '*.md' | wc -l
find notes -name '.DS_Store' -print
rg -n '<<<<<<<|=======|>>>>>>>' notes --glob '*.md'
rg -n '相关知识链接|TODO|FIXME|待补|待完善' notes --glob '*.md'
```

## Review Page Coverage

Each course/topic directory should have:

- one detailed review page,
- one concise review page,
- overview links to both.

`概念索引`-style cross-course index directories may be exempt when they are not a course.

## Link Checks

For a robust check, parse both Markdown links and Obsidian wiki links:

- `[text](path/to/file.md)`
- `[[path/to/file|label]]`
- `[[file stem]]`

Report broken links and self-links before making content claims.
