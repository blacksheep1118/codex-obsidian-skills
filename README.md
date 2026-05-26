# codex-obsidian-skills

[![Validate Skills](https://github.com/blacksheep1118/codex-obsidian-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/blacksheep1118/codex-obsidian-skills/actions/workflows/validate.yml)

Codex skills for turning courseware and Markdown note collections into organized Obsidian vaults. The repository focuses on practical study-note workflows: extracting slide content, rewriting it into readable Markdown, maintaining navigation pages, repairing links, and keeping existing vaults coherent.

This is a skill collection, not a single monolithic skill. Each installable skill lives under [`skill/`](skill/) and keeps its own `SKILL.md`, scripts, references, examples, README, and LICENSE so it can be copied directly into `$CODEX_HOME/skills`.

## Skills

| Skill | Use it when | Main outputs |
| --- | --- | --- |
| [`web-course-notes-for-obsidian`](skill/web-course-notes-for-obsidian) | The task starts from course video websites, PPT/slide websites, book websites, or mixed online learning URLs. | Source manifests, URL-linked course maps, chapter notes, reading notes, review pages. |
| [`ppt-to-md-for-obsidian`](skill/ppt-to-md-for-obsidian) | The task starts from local PPT, PPTX, PDF courseware, or slide-derived files. | Extracted text, cleaned Markdown input, chapter notes, course maps, review pages, Obsidian links. |
| [`obsidian-vault-organizer`](skill/obsidian-vault-organizer) | The task starts from an existing Obsidian vault or Markdown note directory. | Link audits, repaired references, merged duplicate notes, navigation pages, vault cleanup reports. |

The skills are split so their trigger boundaries stay clear. Use `web-course-notes-for-obsidian` when the task starts from URLs. Use `ppt-to-md-for-obsidian` when the task starts from local slide/courseware files. Use `obsidian-vault-organizer` when the task starts from an existing vault or notes directory.

## What This Helps With

- Convert lecture slides into readable Obsidian study notes instead of raw slide dumps.
- Turn course video, slide, and book websites into source-linked study notes.
- Preserve formulas, variable explanations, chapter order, and Chinese course-note style.
- Generate or maintain navigation pages such as `00_课程总览.md` and `00_学习地图.md`.
- Keep detailed and concise review pages separate.
- Validate Markdown links, Obsidian wiki links, and self-links.
- Respect source-file boundaries: courseware, papers, and datasets stay read-only unless the user explicitly asks otherwise.

## Install

Clone the repository, then install one or both skill folders into `$CODEX_HOME/skills` or `~/.codex/skills`. The destination folder name must match the `name` field in that skill's `SKILL.md`.

```bash
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git /tmp/codex-obsidian-skills
cd /tmp/codex-obsidian-skills
python3 scripts/install_skill.py --all --self-check
```

Install only one skill when needed:

```bash
python3 scripts/install_skill.py --skill ppt-to-md-for-obsidian --self-check
python3 scripts/install_skill.py --skill obsidian-vault-organizer --self-check
python3 scripts/install_skill.py --skill web-course-notes-for-obsidian --self-check
```

Check what would happen without writing files:

```bash
python3 scripts/install_skill.py --all --dry-run --self-check
```

Install PPT/PDF extraction dependencies only when you need to run the bundled conversion scripts:

```bash
python3 -m pip install -r ~/.codex/skills/ppt-to-md-for-obsidian/requirements.txt
```

Install validation dependencies only when developing the skills:

```bash
python3 -m pip install -r skill/ppt-to-md-for-obsidian/requirements-dev.txt
python3 -m pip install -r skill/obsidian-vault-organizer/requirements-dev.txt
python3 -m pip install -r skill/web-course-notes-for-obsidian/requirements-dev.txt
```

Update installed skills from a fresh checkout:

```bash
git pull
python3 scripts/update_installed_skills.py --all --prune --self-check
```

`update_installed_skills.py` does not create backups. Use `--dry-run` first when you want an audit of the changes.

## Quick Start

After installing, ask Codex for the workflow you want:

```text
把这个课程视频网站、PPT 网站和书籍网站整理成 Obsidian 笔记，先生成 source_manifest.md。
```

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
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── .github/workflows/validate.yml
├── docs/
├── fixtures/
├── scripts/
├── tests/
└── skill/
    ├── web-course-notes-for-obsidian/
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── LICENSE
    │   ├── agents/
    │   ├── examples/
    │   ├── references/
    │   ├── scripts/
    │   └── tests/
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

The web course notes skill includes:

- `collect_web_sources.py`: collect titles, descriptions, and learning-resource links from course video, slide, book, and mixed learning URLs.
- `validate_skill.py`: validate skill metadata and bundled-resource references.

The PPT skill includes deterministic helpers for the fragile parts of courseware conversion:

- `extract_pptx_text.py`: extract slide text, tables, and speaker notes from `.pptx`.
- `convert_ppt_to_pptx.py`: convert legacy `.ppt` with LibreOffice before extraction.
- `extract_pdf_text.py`: extract raw PDF text with `pypdf` and optional `pdfplumber`.
- `clean_latex_from_ppt.py`: normalize formula and Unicode noise from extracted text.
- `ppt_to_obsidian_pipeline.py`: run source extraction, cleanup, and manifest creation.
- `check_obsidian_links.py`: validate Markdown and Obsidian wiki links.
- `check_course_notes.py`: validate expected course overview, review pages, template residue, and formula fences.

The vault organizer skill includes:

- `check_obsidian_links.py`: validate existing notes or vault directories.
- `check_vault_quality.py`: report empty files, conflict markers, unbalanced fences/math, duplicate note stems, and leftover template text.
- `validate_skill.py`: validate skill metadata and bundled-resource references.

Root management tools include:

- `install_skill.py`: copy one or all skills into a Codex skills directory and run a self-check.
- `update_installed_skills.py`: refresh installed skill folders from this repository without backups.
- `validate_all.py`: run the full CI-style validation suite locally.
- `check_openai_yaml_sync.py`: check `SKILL.md` and `agents/openai.yaml` consistency.
- `check_shared_link_checker.py`: keep shared link-checker copies synchronized.

## Validation

GitHub Actions runs the full validation suite across Python 3.9, 3.11, and 3.12. Locally, run:

```bash
python3 scripts/validate_all.py
```

Focused checks are also available:

```bash
python3 scripts/check_openai_yaml_sync.py
python3 scripts/check_shared_link_checker.py
python3 scripts/install_skill.py --all --dry-run --self-check
```

Skill-local checks:

```bash
cd skill/ppt-to-md-for-obsidian
python3 -m compileall scripts
python3 -m pytest
python3 scripts/check_obsidian_links.py examples/sample-course/notes
python3 scripts/check_course_notes.py examples/sample-course/notes
```

```bash
cd skill/obsidian-vault-organizer
python3 -m compileall scripts
python3 scripts/check_obsidian_links.py ../ppt-to-md-for-obsidian/examples/sample-course/notes
python3 scripts/check_vault_quality.py ../../fixtures/vault-clean
```

```bash
cd skill/web-course-notes-for-obsidian
python3 -m compileall scripts
python3 -m pytest
python3 scripts/validate_skill.py
python3 scripts/collect_web_sources.py examples/sample-web-course/index.html --out /tmp/web_course_source_manifest.md
```

## Documentation

- [Compatibility](docs/compatibility.md)
- [Dry-run organization mode](docs/dry-run-mode.md)
- [License policy](docs/license-policy.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Changelog](CHANGELOG.md)

## Design Principles

- Keep each skill directory independently installable.
- Keep the root README user-facing; keep skill behavior inside each `SKILL.md`.
- Prefer scripts for deterministic, repeatable work such as extraction, cleanup, and link checks.
- Prefer references for longer style or workflow guidance that should be loaded only when needed.
- Avoid moving source files unless the user explicitly requests it.
- Keep Obsidian links local, meaningful, and placed where concepts first become relevant.

## License

MIT. See [LICENSE](LICENSE).
