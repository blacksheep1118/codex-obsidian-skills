# ppt-to-md-for-obsidian skills

This repository contains two Codex skills under [`skill/`](skill/):

- [`skill/ppt-to-md-for-obsidian`](skill/ppt-to-md-for-obsidian): convert PPT/PPTX/PDF courseware into Obsidian-ready Markdown notes, course maps, cross-links, and review pages.
- [`skill/obsidian-vault-organizer`](skill/obsidian-vault-organizer): organize, repair, merge, and validate existing Obsidian vaults or Markdown note collections.

The two skills are split so their trigger boundaries stay clear. Use `ppt-to-md-for-obsidian` when the task starts from slide/courseware extraction. Use `obsidian-vault-organizer` when the task starts from an existing vault or notes directory.

## Install

Clone the repository, then copy the skill folder you want into `$CODEX_HOME/skills` or `~/.codex/skills`. The destination folder name must match the `name` field in that skill's `SKILL.md`.

```bash
git clone https://github.com/blacksheep1118/ppt-to-md-for-obsidian.git /tmp/ppt-to-md-for-obsidian
mkdir -p ~/.codex/skills/ppt-to-md-for-obsidian ~/.codex/skills/obsidian-vault-organizer
cp -R /tmp/ppt-to-md-for-obsidian/skill/ppt-to-md-for-obsidian/. ~/.codex/skills/ppt-to-md-for-obsidian/
cp -R /tmp/ppt-to-md-for-obsidian/skill/obsidian-vault-organizer/. ~/.codex/skills/obsidian-vault-organizer/
```

Install PPT/PDF extraction dependencies only if you need to run the bundled conversion scripts:

```bash
python3 -m pip install -r ~/.codex/skills/ppt-to-md-for-obsidian/requirements.txt
```

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

## License

MIT. See [LICENSE](LICENSE).
