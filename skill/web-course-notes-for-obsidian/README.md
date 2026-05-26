# web-course-notes-for-obsidian

Codex skill for turning course video websites, PPT/slide websites, book websites, and mixed online learning resources into Obsidian-ready notes.

Use this skill when the source starts from URLs. For local PPT/PPTX/PDF files, use [`ppt-to-md-for-obsidian`](../ppt-to-md-for-obsidian). For existing vault cleanup, use [`obsidian-vault-organizer`](../obsidian-vault-organizer).

## Install

Clone this repository, then install this skill into the matching Codex skill directory:

```bash
git clone https://github.com/blacksheep1118/codex-obsidian-skills.git /tmp/codex-obsidian-skills
cd /tmp/codex-obsidian-skills
python3 scripts/install_skill.py --skill web-course-notes-for-obsidian --self-check
```

The bundled source collector uses only the Python standard library. Install development dependencies only when running tests:

```bash
python3 -m pip install -r requirements-dev.txt
```

## What It Produces

- `source_manifest.md` with URLs, titles, descriptions, and detected resource types.
- Obsidian Markdown notes from course videos, slide pages, book chapters, or mixed learning pages.
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

The script detects page titles, descriptions, canonical URLs, and links that look like videos, slides, PDFs, transcripts, book pages, chapters, or generic course pages.

## Validation

Validate the skill metadata and bundled-resource references:

```bash
python3 scripts/validate_skill.py
python3 -m compileall scripts
python3 -m pytest
```

## Safety

The skill does not bypass logins, paywalls, DRM, robots restrictions, or disabled downloads. For book websites, generate study notes and summaries rather than reproducing the source text.

## License

MIT. See [LICENSE](LICENSE).
