# obsidian-vault-organizer

Codex skill for organizing, repairing, merging, and validating existing Obsidian vaults or Markdown note collections.

Use this skill when the source of truth is already a vault or notes directory. It focuses on local guidance, source-file safety, navigation pages, duplicate-note cleanup, cross-links, review pages, and vault validation. For PPT/PPTX/PDF slide extraction and courseware conversion, use [`ppt-to-md-for-obsidian`](../ppt-to-md-for-obsidian).

## Install

Clone this repository, then install this skill into the matching Codex skill directory. By default this is `~/.codex/skills` on macOS/Linux and `%USERPROFILE%\.codex\skills` on Windows, unless `CODEX_HOME` is set.

macOS/Linux:

```bash
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git "${TMPDIR:-/tmp}/codex-obsidian-skills"
cd "${TMPDIR:-/tmp}/codex-obsidian-skills"
python3 scripts/install_skill.py --skill obsidian-vault-organizer --self-check
```

Windows PowerShell:

```powershell
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git "$env:TEMP\codex-obsidian-skills"
cd "$env:TEMP\codex-obsidian-skills"
py scripts\install_skill.py --skill obsidian-vault-organizer --self-check
```

On Windows, replace `py` with `python` if the Python launcher is not installed.

If you want to run the bundled skill validator, install PyYAML:

```bash
python3 -m pip install PyYAML
```

```powershell
py -m pip install PyYAML
```

The Obsidian link checker itself only uses the Python standard library.

## What It Handles

- Vault and note-directory audits.
- Broken Markdown and Obsidian wiki links.
- Self-links, duplicate same-topic notes, empty files, and conflict markers.
- Navigation pages such as `00_课程总览.md`, `00_学习地图.md`, indexes, and review pages.
- Project-local guidance from `AGENT.md`, `agent.md`, and files under `agent/`.
- Source-file safety when notes are derived from courseware, papers, datasets, or other materials.

## Repository Layout

```text
.
├── SKILL.md
├── README.md
├── LICENSE
├── requirements-dev.txt
├── agents/
│   └── openai.yaml
├── references/
│   ├── obsidian-style.md
│   ├── project-vault-workflow.md
│   └── validation.md
└── scripts/
    ├── check_obsidian_links.py
    ├── check_vault_quality.py
    ├── link_inventory.py
    └── validate_skill.py
```

## Usage

Example prompts:

```text
检查这个 Obsidian vault，修复断链并更新课程总览。
```

```text
把这些重复主题笔记合并，保留更完整的解释和公式。
```

```text
按本地 AGENT.md 的规则整理 notes 目录，不要移动源资料。
```

Dry-run prompt:

```text
先 dry-run 审计这个 vault，列出断链、重复主题、拟合并文件和拟修改文件，不要改文件。
```

## Link Check

Run the bundled checker against a local vault or notes directory:

```bash
python3 scripts/check_obsidian_links.py path/to/notes
```

```powershell
py scripts\check_obsidian_links.py path\to\notes
```

It covers Markdown links, `[[wiki]]`, `[[path/to/file]]`, and `[[path/to/file|alias]]`.

Before and after broad cleanup, capture link coverage for comparison:

```bash
python3 scripts/link_inventory.py path/to/notes --format json --out before-links.json
python3 scripts/link_inventory.py path/to/notes --format markdown --out after-links.md
```

The inventory includes per-file Markdown links, wiki links, external links, unique targets, total counts, and directory-level counts.

## Quality Check

Run the read-only quality checker against a local vault or notes directory:

```bash
python3 scripts/check_vault_quality.py path/to/notes
```

```powershell
py scripts\check_vault_quality.py path\to\notes
```

It reports empty files, conflict markers, unbalanced code fences, unbalanced block math, duplicate note stems, and leftover template text.

The default profile is generic and only applies broadly reusable quality checks. Use the solvenotes profile only for solvenotes-specific study-note residue:

```bash
python3 scripts/check_vault_quality.py --profile solvenotes path/to/notes
```

Add custom residue patterns with `--pattern-file`. Plain lines are treated as literal text; lines starting with `regex:` or `re:` are compiled as regular expressions.

See [../../docs/dry-run-mode.md](../../docs/dry-run-mode.md) for the expected dry-run report shape when using this skill from the full repository.

## Validation

Validate the skill metadata and bundled-resource references:

```bash
python3 scripts/validate_skill.py
python3 -m compileall scripts
```

```powershell
py scripts\validate_skill.py
py -m compileall scripts
```

## License

MIT. See [LICENSE](LICENSE).
