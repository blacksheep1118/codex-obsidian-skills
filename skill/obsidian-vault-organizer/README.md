# obsidian-vault-organizer

Codex skill for organizing, repairing, merging, and validating existing Obsidian vaults or Markdown note collections.

Use this skill when the source of truth is already a vault or notes directory. It focuses on local guidance, source-file safety, navigation pages, duplicate-note cleanup, cross-links, review pages, and vault validation. For PPT/PPTX/PDF slide extraction and courseware conversion, use [`ppt-to-md-for-obsidian`](../ppt-to-md-for-obsidian).

## Install

Clone this repository, then copy this skill subdirectory into the matching Codex skill directory:

```bash
git clone https://github.com/blacksheep1118/ppt-to-md-for-obsidian.git /tmp/ppt-to-md-for-obsidian
mkdir -p ~/.codex/skills
cp -R /tmp/ppt-to-md-for-obsidian/skill/obsidian-vault-organizer ~/.codex/skills/obsidian-vault-organizer
```

If you want to run the bundled skill validator, install PyYAML:

```bash
python3 -m pip install PyYAML
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

## Link Check

Run the bundled checker against a local vault or notes directory:

```bash
python3 scripts/check_obsidian_links.py path/to/notes
```

It covers Markdown links, `[[wiki]]`, `[[path/to/file]]`, and `[[path/to/file|alias]]`.

## Validation

Validate the skill metadata and bundled-resource references:

```bash
python3 scripts/validate_skill.py
```

## License

MIT. See [LICENSE](LICENSE).
