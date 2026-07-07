# codex-obsidian-skills

[![Validate Skills](https://github.com/blacksheep1118/codex-obsidian-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/blacksheep1118/codex-obsidian-skills/actions/workflows/validate.yml)

Codex skills for turning courseware and Markdown note collections into organized Obsidian vaults and research presentations. The repository focuses on practical study-note workflows: extracting slide content, rewriting it into readable Markdown, maintaining navigation pages, repairing links, turning notes into rigorous PPTX decks, and keeping existing vaults coherent.

This is a skill collection, not a single monolithic skill. Each installable skill lives under [`skill/`](skill/) and keeps its own `SKILL.md`, scripts, references, examples, README, and LICENSE so it can be copied directly into `CODEX_HOME/skills` or the default Codex skills directory.

The project is distributed through GitHub commits, branches, tags, and CI. Do not hand-compress the repository or commit generated archives; keep the Git tree clean and let CI block caches, macOS resource files, and generated outputs.

## Skills

| Skill | Use it when | Main outputs |
| --- | --- | --- |
| [`web-course-notes-for-obsidian`](skill/web-course-notes-for-obsidian) | The task starts from course video websites, PPT/slide websites, book websites, direct PDF/PPT URLs, or mixed online learning URLs. | Source manifests, classified note folders, URL-linked learning maps, detailed note scaffolds, chapter notes, reading notes, review pages. |
| [`ppt-to-md-for-obsidian`](skill/ppt-to-md-for-obsidian) | The task starts from local PPT, PPTX, PDF courseware, or slide-derived files. | Extracted text, cleaned Markdown input, chapter notes, course maps, review pages, Obsidian links. |
| [`obsidian-vault-organizer`](skill/obsidian-vault-organizer) | The task starts from an existing Obsidian vault or Markdown note directory. | Link audits, repaired references, merged duplicate notes, navigation pages, vault cleanup reports. |
| [`notes-to-scientific-ppt`](skill/notes-to-scientific-ppt) | The task starts from Obsidian or Markdown notes and asks for a PPT/PPTX research presentation. | Source inventories, evidence ledgers, scientific claim spines, draft slide backlogs, rigorous PPTX deck plans, speaker-note guidance. |

The skills are split so their trigger boundaries stay clear. Use `web-course-notes-for-obsidian` when the task starts from URLs. Use `ppt-to-md-for-obsidian` when the task starts from local slide/courseware files. Use `obsidian-vault-organizer` when the task is vault cleanup. Use `notes-to-scientific-ppt` when the task starts from notes and the desired output is a research PPT.

See [Skill Routing](docs/routing.md) for cross-skill boundaries and mixed workflow handoffs.

## What This Helps With

- Convert lecture slides into readable Obsidian study notes instead of raw slide dumps.
- Turn course video, slide, and book websites into source-linked study notes.
- Preserve formulas, variable explanations, chapter order, and Chinese course-note style.
- Generate or maintain navigation pages such as `00_课程总览.md` and `00_学习地图.md`.
- Turn finished notes into detailed, vivid, research-rigorous PPTX deck briefs and slide plans.
- Keep detailed and concise review pages separate.
- Validate Markdown links, Obsidian wiki links, and self-links.
- Respect source-file boundaries: courseware, papers, and datasets stay read-only unless the user explicitly asks otherwise.

## Install

Clone the repository, then install one or all skill folders into the Codex skills directory. The destination folder name must match the `name` field in that skill's `SKILL.md`.

Default install locations:

- macOS/Linux: `~/.codex/skills`
- Windows: `%USERPROFILE%\.codex\skills`
- Any platform: set `CODEX_HOME` to install under `CODEX_HOME/skills`

macOS/Linux:

```bash
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git "${TMPDIR:-/tmp}/codex-obsidian-skills"
cd "${TMPDIR:-/tmp}/codex-obsidian-skills"
python3 scripts/install_skill.py --all --self-check
```

Windows PowerShell:

```powershell
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git "$env:TEMP\codex-obsidian-skills"
cd "$env:TEMP\codex-obsidian-skills"
py scripts\install_skill.py --all --self-check
```

On Windows, replace `py` with `python` if the Python launcher is not installed.

Installing from a GitHub clone is the normal path. The install and update scripts copy only the skill contents and automatically ignore caches, macOS resource files, Python bytecode, build directories, distribution metadata, and generated `converted_pptx/` outputs. You do not need to compress the repository before installing.

Install only one skill when needed:

```bash
python3 scripts/install_skill.py --skill ppt-to-md-for-obsidian --self-check
python3 scripts/install_skill.py --skill obsidian-vault-organizer --self-check
python3 scripts/install_skill.py --skill web-course-notes-for-obsidian --self-check
python3 scripts/install_skill.py --skill notes-to-scientific-ppt --self-check
```

```powershell
py scripts\install_skill.py --skill ppt-to-md-for-obsidian --self-check
py scripts\install_skill.py --skill obsidian-vault-organizer --self-check
py scripts\install_skill.py --skill web-course-notes-for-obsidian --self-check
py scripts\install_skill.py --skill notes-to-scientific-ppt --self-check
```

Check what would happen without writing files:

```bash
python3 scripts/install_skill.py --all --dry-run --self-check
```

```powershell
py scripts\install_skill.py --all --dry-run --self-check
```

Install PPT/PDF extraction dependencies only when you need to run the bundled conversion scripts:

```bash
python3 -m pip install -r ~/.codex/skills/ppt-to-md-for-obsidian/requirements.txt
```

```powershell
py -m pip install -r "$env:USERPROFILE\.codex\skills\ppt-to-md-for-obsidian\requirements.txt"
```

When developing one skill, install only that skill's validation dependencies in the environment you are using for that skill:

```bash
cd skill/ppt-to-md-for-obsidian
python3 -m pip install -r requirements-dev.txt
```

```powershell
cd skill\ppt-to-md-for-obsidian
py -m pip install -r requirements-dev.txt
```

Update installed skills from a fresh checkout:

```bash
git pull
python3 scripts/update_installed_skills.py --all --prune --self-check
```

```powershell
git pull
py scripts\update_installed_skills.py --all --prune --self-check
```

`update_installed_skills.py` does not create backups. Use `--dry-run` first when you want an audit of the changes.

## Quick Start

After installing, ask Codex for the workflow you want:

```text
Use $web-course-notes-for-obsidian for these course URLs. Build source_manifest.md first, keep inaccessible sources marked, then create source-linked Obsidian notes.
```

```text
Use $ppt-to-md-for-obsidian for these local PPT/PPTX/PDF courseware files. Extract the source text, build a coverage map, and write Obsidian course notes with formulas and review pages.
```

```text
Use $obsidian-vault-organizer for this existing vault. Audit links, duplicate stems, navigation, and note quality before editing; keep source files read-only.
```

```text
Use $notes-to-scientific-ppt for this notes folder. Create a deck brief first, then build an editable scientific PPTX skeleton with claim, formula, evidence, limitations, and appendix slides.
```

When a task crosses sources, notes, cleanup, and deck creation, follow the handoff examples in [Skill Routing](docs/routing.md).

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
    ├── notes-to-scientific-ppt/
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
- `create_web_notes.py`: classify URL collections into existing note folders, write `source_manifest.md`, and create detailed note scaffolds that must be expanded from source content before delivery.
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

The notes-to-scientific-ppt skill includes:

- `outline_note_deck.py`: scan Markdown or Obsidian notes and create a source inventory, evidence ledger, mode-specific scientific deck spine, draft slide backlog, and coverage checklist before PPT construction.
- `validate_skill.py`: validate skill metadata and bundled-resource references.

Root management tools include:

- `install_skill.py`: copy one or all skills into a Codex skills directory and run a self-check.
- `update_installed_skills.py`: refresh installed skill folders from this repository without backups.
- `validate_all.py`: run the full CI-style validation suite locally.
- `check_repo_hygiene.py`: fail if Git tracks cache files, macOS resource files, logs, scratch files, or generated outputs; use `--scan-worktree` for local ignored/untracked cleanup audits.
- `check_openai_yaml_sync.py`: check `SKILL.md` and `agents/openai.yaml` consistency.
- `sync_shared_resources.py`: check or rewrite skill-local copies generated from canonical shared scripts and templates.
- `check_shared_link_checker.py`: compatibility wrapper for the shared-resource synchronization check.

## Validation

GitHub Actions runs repository hygiene and root tests across Ubuntu, macOS, and Windows. Skill-local tests run in a separate matrix where each job installs only that skill's own `requirements-dev.txt`, so missing skill dependencies are not hidden by another skill's requirements.

Before committing, run:

```bash
python3 scripts/check_repo_hygiene.py
python3 -m pytest -q
python3 scripts/validate_all.py --quick
```

```powershell
py scripts\check_repo_hygiene.py
py -m pytest -q
py scripts\validate_all.py --quick
```

The root `python -m pytest` entry point is the fast repository check and only collects tests from the root `tests/` directory. `scripts/validate_all.py --quick` runs compile, repo hygiene, metadata sync, root tests, and skill validators without sample pipeline or deck smoke runs.

`validate_all.py` runs its pytest subprocesses with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` so unrelated globally installed pytest plugins do not change local or CI validation behavior. Set `VALIDATE_ALL_ENABLE_PYTEST_PLUGIN_AUTOLOAD=1` only when intentionally debugging with external pytest plugins.

`scripts/check_repo_hygiene.py` checks Git-tracked files by default, which is the right mode for CI and pre-push validation. Run `python3 scripts/check_repo_hygiene.py --scan-worktree` when you want a local deep-clean check that also reports ignored or untracked caches, logs, scratch files, and generated outputs.

When a skill changes, also run that skill's isolated test and validator commands below after installing only that skill's `requirements-dev.txt`. This mirrors the GitHub Actions skill matrix and catches missing per-skill dependencies before push.

To debug the validation suite, list stable step ids or run one skill only:

```bash
python3 scripts/validate_all.py --list-steps
python3 scripts/validate_all.py --skill notes
python3 scripts/validate_all.py --skill notes-to-scientific-ppt
```

```powershell
py scripts\validate_all.py --list-steps
py scripts\validate_all.py --skill notes
py scripts\validate_all.py --skill notes-to-scientific-ppt
```

Full validation, including skill tests and sample smoke runs:

```bash
python3 scripts/validate_all.py
```

```powershell
py scripts\validate_all.py
```

Focused checks are also available:

```bash
python3 scripts/check_repo_hygiene.py
python3 scripts/check_repo_hygiene.py --scan-worktree
python3 scripts/check_openai_yaml_sync.py
python3 scripts/sync_shared_resources.py --check
python3 scripts/install_skill.py --all --dry-run --self-check
```

```powershell
py scripts\check_repo_hygiene.py
py scripts\check_repo_hygiene.py --scan-worktree
py scripts\check_openai_yaml_sync.py
py scripts\sync_shared_resources.py --check
py scripts\install_skill.py --all --dry-run --self-check
```

To validate a single skill in isolation, use a fresh environment when possible, install only that skill's `requirements-dev.txt`, then run that skill's tests and validator:

```bash
cd skill/ppt-to-md-for-obsidian
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
python3 scripts/validate_skill_repo.py
```

```powershell
cd skill\ppt-to-md-for-obsidian
py -m pip install -r requirements-dev.txt
py -m pytest -q
py scripts\validate_skill_repo.py
```

```bash
cd skill/obsidian-vault-organizer
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
python3 scripts/validate_skill.py
```

```powershell
cd skill\obsidian-vault-organizer
py -m pip install -r requirements-dev.txt
py -m pytest -q
py scripts\validate_skill.py
```

```bash
cd skill/web-course-notes-for-obsidian
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
python3 scripts/validate_skill.py
```

```powershell
cd skill\web-course-notes-for-obsidian
py -m pip install -r requirements-dev.txt
py -m pytest -q
py scripts\validate_skill.py
```

```bash
cd skill/notes-to-scientific-ppt
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
python3 scripts/validate_skill.py
```

```powershell
cd skill\notes-to-scientific-ppt
py -m pip install -r requirements-dev.txt
py -m pytest -q
py scripts\validate_skill.py
```

## Documentation

- [Compatibility](docs/compatibility.md)
- [Dry-run organization mode](docs/dry-run-mode.md)
- [License policy](docs/license-policy.md)
- [Skill routing](docs/routing.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Changelog](CHANGELOG.md)

## Design Principles

- Keep each skill directory independently installable.
- Keep the root README user-facing; keep skill behavior inside each `SKILL.md`.
- Keep each skill's trigger boundary, handoff path, output contract, and validation expectations explicit.
- Keep each skill's quick start and evidence/assumption gate close to the workflow so agents can scope work before editing.
- Prefer scripts for deterministic, repeatable work such as extraction, cleanup, and link checks.
- Prefer references for longer style or workflow guidance that should be loaded only when needed.
- Avoid moving source files unless the user explicitly requests it.
- Keep Obsidian links local, meaningful, and placed where concepts first become relevant.
- Do not commit caches, `__pycache__`, `*.pyc`, macOS AppleDouble files, `.DS_Store`, build outputs, converted PPTX directories, or temporary test output.

## License

MIT. See [LICENSE](LICENSE).
