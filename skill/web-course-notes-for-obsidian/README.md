# web-course-notes-for-obsidian

Codex skill for turning course video websites, PPT/slide websites, book websites, and mixed online learning resources into Obsidian-ready notes.

Use this skill when the source starts from URLs. For local PPT/PPTX/PDF files, use [`ppt-to-md-for-obsidian`](../ppt-to-md-for-obsidian). For existing vault cleanup, use [`obsidian-vault-organizer`](../obsidian-vault-organizer).

## Install

Clone this repository, then install this skill into the matching Codex skill directory. By default this is `~/.codex/skills` on macOS/Linux and `%USERPROFILE%\.codex\skills` on Windows, unless `CODEX_HOME` is set.

macOS/Linux:

```bash
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git "${TMPDIR:-/tmp}/codex-obsidian-skills"
cd "${TMPDIR:-/tmp}/codex-obsidian-skills"
python3 scripts/install_skill.py --skill web-course-notes-for-obsidian --self-check
```

Windows PowerShell:

```powershell
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git "$env:TEMP\codex-obsidian-skills"
cd "$env:TEMP\codex-obsidian-skills"
py scripts\install_skill.py --skill web-course-notes-for-obsidian --self-check
```

On Windows, replace `py` with `python` if the Python launcher is not installed.

The bundled source collector uses only the Python standard library. Install development dependencies only when running tests:

```bash
python3 -m pip install -r requirements-dev.txt
```

```powershell
py -m pip install -r requirements-dev.txt
```

## What It Produces

- A collection folder inside the user's Obsidian notes directory, either under a matching existing category or under a language-specific fallback root such as `网络资源/` or `Web Resources/`.
- `source_manifest.md` with original sources, canonical URLs, titles, descriptions, detected resource types, access status, and per-source errors.
- `00_学习地图.md` or `00_Learning_Map.md` as the entry point for each imported web resource collection.
- Detailed Obsidian Markdown notes from course videos, slide pages, book chapters, direct PDFs, or mixed learning pages.
- `00_课程总览.md`, `00_学习地图.md`, or `00_阅读地图.md`.
- Detailed and concise review pages when the source is course-like.
- Source-linked concept notes with visible provenance.

## Usage

Example prompts:

```text
把这个课程视频网站整理成 Obsidian 笔记，先生成 source_manifest.md，再按章节写笔记。
```

```text
把这个 PPT 网站里的课件链接收集出来，转成课程学习地图和复习页。
```

```text
根据这个书籍网站做阅读笔记，只总结和解释，不复制原文。
```

## Source Collection

Collect a source manifest from one or more URLs or local HTML files:

```bash
python3 scripts/collect_web_sources.py examples/sample-web-course/index.html --out source_manifest.md
```

```powershell
py scripts\collect_web_sources.py examples\sample-web-course\index.html --out source_manifest.md
```

The script detects page titles, descriptions, canonical URLs, and links that look like videos, slides, PDFs, transcripts, book pages, chapters, or generic course pages. It processes each input source independently: if one URL or local HTML file cannot be read, the manifest still keeps that source with an access status, source type guess, and error summary.

Direct PDF/PPT/transcript/book URLs are recorded as resources without parsing their binary content as HTML:

```bash
python3 scripts/collect_web_sources.py https://openaccess.thecvf.com/content_cvpr_2016/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf --out source_manifest.md
```

## Create Notes In A Vault

Create a folder and detailed note scaffolds from one or more URLs:

```bash
python3 scripts/create_web_notes.py https://openaccess.thecvf.com/content_cvpr_2016/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf --notes-dir ~/Desktop/solvenotes/notes
```

```powershell
py scripts\create_web_notes.py https://openaccess.thecvf.com/content_cvpr_2016/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf --notes-dir "$HOME\Desktop\solvenotes\notes"
```

The script inspects existing top-level folders under `--notes-dir`. For CVPR/image resources it prefers an existing matching folder; otherwise it creates `网络资源/<collection-title>/` for Chinese scaffolds and `Web Resources/<collection-title>/` for English scaffolds. Use `--category <folder>` to force a destination category.

`create_web_notes.py` is a deterministic placement and scaffolding helper. Its generated notes are marked `status: scaffold`; Codex should then read or extract the accessible source content, inspect nearby notes in the destination category, and replace the scaffold placeholders with a finished note before reporting the task as complete.

By default, `--language auto` chooses Chinese when the user input, collected title, or description contains Chinese characters and chooses English otherwise. The resolved language also controls fallback placement and entry note names: Chinese uses `网络资源/` and `00_学习地图.md`; English uses `Web Resources/` and `00_Learning_Map.md`. Choose scaffold language explicitly when needed:

```bash
python3 scripts/create_web_notes.py https://example.com/course --notes-dir ~/notes --language en
python3 scripts/create_web_notes.py https://example.com/course --notes-dir ~/notes --language zh
```

Use `--root-folder-name <folder>` or `--map-note-name <name.md>` when a vault needs custom placement or entry note naming.

Scaffolds are not final delivery. After Codex reads or extracts the accessible source content and rewrites the placeholders into finished notes, run `scripts/check_web_notes.py` before reporting the collection as complete.

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

Before final delivery of a generated collection, run the web-note checker with every user-supplied source:

```bash
python3 scripts/check_web_notes.py /path/to/collection --source https://example.com/course
```

Use `--per-link-notes` when the user requested one note per listed resource. The checker verifies source coverage, scaffold residue, and per-link note coverage or explicit skipped/inaccessible status.

## Safety

The skill does not bypass logins, paywalls, DRM, robots restrictions, or disabled downloads. For book websites, generate study notes and summaries rather than reproducing the source text.

## License

MIT. See [LICENSE](LICENSE).
