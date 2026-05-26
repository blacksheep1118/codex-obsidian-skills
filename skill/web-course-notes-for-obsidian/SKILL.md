---
name: web-course-notes-for-obsidian
description: Use when the user gives course video websites, lecture/PPT websites, book websites, online course pages, documentation chapters, public reading lists, or mixed web learning resources and wants Codex to collect accessible source material, create Obsidian-ready Markdown notes, course maps, chapter notes, review pages, and source-linked study notes. Use $ppt-to-md-for-obsidian instead when the task starts from local PPT/PPTX/PDF files, and use $obsidian-vault-organizer for vault-only cleanup.
---

# Web Course Notes For Obsidian

## Goal

Turn user-provided learning websites into an Obsidian note system. The input may be a course video page, course index, PPT/slide page, book or chapter site, public reading list, or a mix of URLs.

Use only sources the user can legitimately access. Do not bypass logins, paywalls, DRM, robots restrictions, anti-bot controls, or platform terms. For copyrighted books, produce study notes, outlines, citations, and short summaries rather than reconstructing or copying the text.

## Default Outputs

For each course, book, or topic collection, prefer:

- A topic folder inside the user's notes directory. Reuse an existing category folder when the source clearly belongs there; otherwise create a new folder such as `网络资源/<collection-title>/`.
- `00_学习地图.md` or `00_课程总览.md` as the entry point.
- Numbered notes such as `01_导论.md`, `02_核心概念.md`, or chapter-based names.
- `source_manifest.md` with URLs, titles, source types, access status, and what each source contributed.
- `知识点详细版_含公式.md` when the material is course-like.
- `知识点精简复习版_含公式.md` or `快速复习.md` for review.

Keep source URLs in notes or frontmatter so provenance stays visible.

## Workflow

1. Clarify source boundaries.
   - Identify whether each URL is a video page, course index, slides/PPT/PDF page, book/chapter page, or mixed catalog.
   - Ask the user before using authenticated pages if browser access, cookies, downloads, or paid content are involved.
   - Do not download or mirror large source collections unless the user explicitly asks and the source allows it.

2. Build a source manifest.
   - Use `scripts/collect_web_sources.py` when a deterministic URL inventory helps.
   - Direct PDF/PPT/transcript/book URLs should be recorded as resources without attempting to parse binary content as HTML.
   - Capture titles, canonical URLs, descriptions, source type, and links to slides, videos, transcripts, chapters, and PDFs.
   - Record inaccessible or ambiguous sources instead of silently skipping them.

3. Place notes in the vault.
   - If the user provides an Obsidian notes directory, inspect existing top-level folders and classify the collection into the closest existing folder.
   - If no existing folder fits, create a new folder under the notes directory, preferably `网络资源/<collection-title>/`.
   - Use `scripts/create_web_notes.py --notes-dir <notes-dir> <url...>` to create the collection folder, `source_manifest.md`, `00_学习地图.md`, and starter notes.
   - Use `--category <folder>` when the user or context clearly identifies the destination category.

4. Extract only appropriate content.
   - Prefer official transcripts/captions for videos when available.
   - Prefer page headings, abstracts, tables of contents, slide titles, and user-provided excerpts for books.
   - For local or downloadable PPT/PDF files, hand off to `$ppt-to-md-for-obsidian`.
   - If the user supplies an existing Obsidian vault, use `$obsidian-vault-organizer` after drafting.

5. Generate notes.
   - Use Chinese by default when the user writes Chinese.
   - Convert fragments into explanations, not web-page dumps.
   - Add formulas, variable meanings, examples, assumptions, and failure cases when present.
   - Link concepts where they first become relevant.
   - Cite source URLs near the sections they support.

6. Validate before finishing.
   - Check local Obsidian links with `$obsidian-vault-organizer`.
   - Check that `source_manifest.md` covers every URL the user supplied.
   - Check that generated notes do not contain long copied passages from books or web pages.

## Source Policy

Read `references/source-policy.md` when a source is authenticated, paywalled, copyrighted, robots-restricted, or ambiguous.

## Output Style

Read `references/note-output.md` when deciding how to structure notes for course videos, slide sites, book sites, or mixed web resources.

## Bundled Resources

- `scripts/collect_web_sources.py`: collect titles, descriptions, and learning-resource links from URL or local HTML inputs.
- `scripts/create_web_notes.py`: classify sources into a notes directory, create a collection folder, and write `source_manifest.md`, `00_学习地图.md`, and starter notes.
- `references/source-policy.md`: source access, copyright, attribution, and safety rules.
- `references/note-output.md`: note structures for video courses, PPT sites, book sites, and mixed web learning resources.
