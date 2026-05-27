# notes-to-scientific-ppt

Codex skill for turning Obsidian or Markdown notes into detailed, vivid, scientifically rigorous PowerPoint decks.

Use this skill when the source starts from notes. For local PPT/PPTX/PDF courseware extraction, use [`ppt-to-md-for-obsidian`](../ppt-to-md-for-obsidian). For vault-only cleanup, use [`obsidian-vault-organizer`](../obsidian-vault-organizer).

## Install

Clone this repository, then install this skill into the matching Codex skill directory. By default this is `~/.codex/skills` on macOS/Linux and `%USERPROFILE%\.codex\skills` on Windows, unless `CODEX_HOME` is set.

macOS/Linux:

```bash
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git "${TMPDIR:-/tmp}/codex-obsidian-skills"
cd "${TMPDIR:-/tmp}/codex-obsidian-skills"
python3 scripts/install_skill.py --skill notes-to-scientific-ppt --self-check
```

Windows PowerShell:

```powershell
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git "$env:TEMP\codex-obsidian-skills"
cd "$env:TEMP\codex-obsidian-skills"
py scripts\install_skill.py --skill notes-to-scientific-ppt --self-check
```

On Windows, replace `py` with `python` if the Python launcher is not installed.

Install development dependencies only when running tests:

```bash
python3 -m pip install -r requirements-dev.txt
```

```powershell
py -m pip install -r requirements-dev.txt
```

## What It Produces

- A deck brief that inventories source notes, headings, links, figures, tables, formulas, and missing evidence.
- An evidence ledger that maps notes to proof objects, assumptions, and structural gaps.
- A scientific claim spine for the PPT.
- A draft slide backlog for turning note sections into claim-title slides or appendix items.
- An editable PPTX deck when paired with the bundled `Presentations` skill.
- Optional speaker notes and appendix slides for formulas, raw evidence, and extended comparisons.

The skill is designed for lab meetings, paper reading talks, thesis defenses, research proposals, progress reports, and technical teaching decks.

## Create A Deck Brief

Scan one note or a folder of notes:

```bash
python3 scripts/outline_note_deck.py examples/sample-notes --out "${TMPDIR:-/tmp}/scientific_deck_brief.md" --title "Blind Image Denoising"
```

```powershell
py scripts\outline_note_deck.py examples\sample-notes --out "$env:TEMP\scientific_deck_brief.md" --title "Blind Image Denoising"
```

Use `--mode paper-reading`, `--mode proposal`, `--mode progress-report`, `--mode teaching`, or `--mode defense` when the talk type is known. The default `--mode auto` infers the mode from headings and note content.

The deck brief is not the final deck. It is a source audit and planning artifact used before building slides.

## Validation

Validate the skill metadata and bundled-resource references:

```bash
python3 scripts/validate_skill.py
python3 -m compileall scripts
python3 -m pytest
```

```powershell
py scripts\validate_skill.py
py -m compileall scripts
py -m pytest
```

## Safety

Do not invent experiments, metrics, citations, or paper conclusions. If notes do not support a claim, mark it as a gap or discussion question.

## License

MIT. See [LICENSE](LICENSE).
