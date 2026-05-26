# codex-obsidian-skills

[![Validate Skill](https://github.com/blacksheep1118/codex-obsidian-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/blacksheep1118/codex-obsidian-skills/actions/workflows/validate.yml)

Codex skills for turning courseware and Markdown note collections into organized Obsidian vaults. The repository focuses on practical study-note workflows: extracting slide content, rewriting it into readable Markdown, maintaining navigation pages, repairing links, and keeping existing vaults coherent.

This is a skill collection, not a single monolithic skill. Each installable skill lives under [`skill/`](skill/) and keeps its own `SKILL.md`, scripts, references, examples, and README.

## Skills

| Skill | Use it when | Main outputs |
| --- | --- | --- |
| [`ppt-to-md-for-obsidian`](skill/ppt-to-md-for-obsidian) | The task starts from PPT, PPTX, PDF courseware, or slide-derived materials. | Extracted text, cleaned Markdown input, chapter notes, course maps, review pages, Obsidian links. |
| [`obsidian-vault-organizer`](skill/obsidian-vault-organizer) | The task starts from an existing Obsidian vault or Markdown note directory. | Link audits, repaired references, merged duplicate notes, navigation pages, vault cleanup reports. |

The two skills are split so their trigger boundaries stay clear. Use `ppt-to-md-for-obsidian` when the task starts from slide/courseware extraction. Use `obsidian-vault-organizer` when the task starts from an existing vault or notes directory.

## What This Helps With

- Convert lecture slides into readable Obsidian study notes instead of raw slide dumps.
- Preserve formulas, variable explanations, chapter order, and Chinese course-note style.
- Generate or maintain navigation pages such as `00_课程总览.md` and `00_学习地图.md`.
- Keep detailed and concise review pages separate.
- Validate Markdown links, Obsidian wiki links, and self-links.
- Respect source-file boundaries: courseware, papers, and datasets stay read-only unless the user explicitly asks otherwise.

## Install

Clone the repository, then copy one or both skill folders into `$CODEX_HOME/skills` or `~/.codex/skills`. The destination folder name must match the `name` field in that skill's `SKILL.md`.

```bash
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git /tmp/codex-obsidian-skills
mkdir -p ~/.codex/skills/ppt-to-md-for-obsidian ~/.codex/skills/obsidian-vault-organizer
cp -R /tmp/codex-obsidian-skills/skill/ppt-to-md-for-obsidian/. ~/.codex/skills/ppt-to-md-for-obsidian/
cp -R /tmp/codex-obsidian-skills/skill/obsidian-vault-organizer/. ~/.codex/skills/obsidian-vault-organizer/
```

Install PPT/PDF extraction dependencies only when you need to run the bundled conversion scripts:

```bash
python3 -m pip install -r ~/.codex/skills/ppt-to-md-for-obsidian/requirements.txt
```

Install validation dependencies only when developing the skills:

```bash
python3 -m pip install -r skill/ppt-to-md-for-obsidian/requirements-dev.txt
python3 -m pip install -r skill/obsidian-vault-organizer/requirements-dev.txt
```

## Quick Start

After installing, ask Codex for the workflow you want:

```text
把这组 PPT 课件转成 Obsidian 章节笔记，保留公式解释、课程总览和复习页。
```

```text
检查这个 Obsidian vault，修复断链，合并重复主题笔记，并更新学习地图。
```

```text
把新增 PDF 课件合并进已有课程笔记，不要移动或改名源文件。
```

When a task includes both source courseware and an existing vault, start with `ppt-to-md-for-obsidian` for extraction and drafting, then use `obsidian-vault-organizer` for vault cleanup and link validation.

## Repository Layout

```text
.
├── README.md
├── LICENSE
├── .github/workflows/validate.yml
└── skill/
    ├── ppt-to-md-for-obsidian/
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── LICENSE
    │   ├── agents/
    │   ├── examples/
    │   ├── references/
    │   ├── scripts/
    │   └── tests/
    └── obsidian-vault-organizer/
        ├── SKILL.md
        ├── README.md
        ├── LICENSE
        ├── agents/
        ├── references/
        └── scripts/
```

## Bundled Tools

The PPT skill includes deterministic helpers for the fragile parts of courseware conversion:

- `extract_pptx_text.py`: extract slide text, tables, and speaker notes from `.pptx`.
- `convert_ppt_to_pptx.py`: convert legacy `.ppt` with LibreOffice before extraction.
- `extract_pdf_text.py`: extract raw PDF text with `pypdf` and optional `pdfplumber`.
- `clean_latex_from_ppt.py`: normalize formula and Unicode noise from extracted text.
- `ppt_to_obsidian_pipeline.py`: run source extraction, cleanup, and manifest creation.
- `check_obsidian_links.py`: validate Markdown and Obsidian wiki links.

The vault organizer skill includes:

- `check_obsidian_links.py`: validate existing notes or vault directories.
- `validate_skill.py`: validate skill metadata and bundled-resource references.

## Validation

GitHub Actions validates both skill folders. Locally, run:

```bash
cd skill/ppt-to-md-for-obsidian
python3 scripts/validate_skill_repo.py
python3 -m pytest
```

```bash
cd skill/obsidian-vault-organizer
python3 scripts/validate_skill.py
python3 -m compileall scripts
```

For a fuller local pass:

```bash
cd skill/ppt-to-md-for-obsidian
python3 -m compileall scripts
python3 -m pytest
python3 scripts/check_obsidian_links.py examples/sample-course/notes
```

```bash
cd skill/obsidian-vault-organizer
python3 -m compileall scripts
python3 scripts/check_obsidian_links.py ../ppt-to-md-for-obsidian/examples/sample-course/notes
```

## Design Principles

- Keep each skill directory independently installable.
- Keep the root README user-facing; keep skill behavior inside each `SKILL.md`.
- Prefer scripts for deterministic, repeatable work such as extraction, cleanup, and link checks.
- Prefer references for longer style or workflow guidance that should be loaded only when needed.
- Avoid moving source files unless the user explicitly requests it.
- Keep Obsidian links local, meaningful, and placed where concepts first become relevant.

## License

MIT. See [LICENSE](LICENSE).
