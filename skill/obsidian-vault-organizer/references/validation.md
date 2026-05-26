# Validation Checks

Run checks after creating or updating Obsidian notes.

## Basic Shell Checks

```bash
find notes -name '*.md' | wc -l
find notes -name '.DS_Store' -print
rg -n '<<<<<<<|=======|>>>>>>>' notes --glob '*.md'
rg -n '相关知识链接|TODO|FIXME|待补|待完善' notes --glob '*.md'
```

Adjust `notes` to the resolved vault path.

## Scripted Link Check

Check Obsidian links:

```bash
python3 scripts/check_obsidian_links.py notes
```

The checker covers:

- `[text](path/to/file.md)`
- `[[path/to/file|label]]`
- `[[file stem]]`

Report broken links and self-links before making content claims.

## Manual Review

Before finishing substantial edits, confirm:

- source files were not modified unless explicitly requested,
- no duplicate same-topic note was introduced,
- navigation pages link newly added or renamed notes,
- review pages remain separate when the vault expects detailed and concise versions,
- block math delimiters are balanced,
- empty files and conflict markers are absent.
