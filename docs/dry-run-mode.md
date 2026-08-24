# Dry-run Organization Mode

Use dry-run mode for risky vault organization tasks before editing files. The expected behavior is to report intended changes first, then wait for user approval before applying them.

## Recommended Prompt

```text
Use $obsidian-vault-organizer in dry-run mode. Audit this vault, list broken links, duplicate notes, proposed merges, proposed renames, and files that would be edited. Do not modify files yet.
```

## Dry-run Report Shape

```text
Planned edits:
- Update 00_课程总览.md to include missing chapter links.
- Rename draft note A only if the user approves.
- Merge duplicate topic notes into the more complete target.

Validation:
- broken_links: 2
- duplicate_stems: 1
- source_files_to_leave_read_only: 4
```

## Script Support

The repository management scripts support dry-run flags. Use the install dry-run only when the selected destination Skill subdirectories do not exist; the dry-run does not create the destination. Use the update dry-run to inspect an existing installation.

macOS/Linux:

```bash
python3 scripts/install_skill.py --all --destination /absolute/path/to/empty/codex-skills --dry-run --self-check
python3 scripts/update_installed_skills.py --all --dry-run --prune --self-check
```

Windows PowerShell:

```powershell
py scripts\install_skill.py --all --destination C:\path\to\empty\codex-skills --dry-run --self-check
py scripts\update_installed_skills.py --all --dry-run --prune --self-check
```

The vault quality checker is read-only by design:

```bash
python3 skill/obsidian-vault-organizer/scripts/check_vault_quality.py path/to/vault
```

```powershell
py skill\obsidian-vault-organizer\scripts\check_vault_quality.py path\to\vault
```
