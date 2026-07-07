---
name: web-course-notes-for-obsidian
description: Use when the starting source is a URL, webpage course, online book/chapter, reading list, local HTML, or direct PDF/PPT/transcript URL and the user wants Obsidian web-course notes, source_manifest.md, learning maps, or per-link notes; Chinese triggers include 网页课程, 在线书籍, PDF链接整理. Use $ppt-to-md-for-obsidian instead after permitted sources become local PPT/PPTX/PDF courseware; use $obsidian-vault-organizer for vault-only cleanup.
---

# Web Course Notes For Obsidian

## Goal

Turn user-provided learning websites into an Obsidian note system. The input may be a course video page, course index, PPT/slide page, book or chapter site, public reading list, or a mix of URLs.

Use only sources the user can legitimately access. Do not bypass logins, paywalls, DRM, robots restrictions, anti-bot controls, or platform terms. For copyrighted books, produce study notes, outlines, citations, and short summaries rather than reconstructing or copying the text.

## Default Outputs

For each course, book, or topic collection, prefer:

- A topic folder inside the user's notes directory. Reuse an existing category folder when the source clearly belongs there; otherwise create a new folder such as `网络资源/<collection-title>/`.
- `00_学习地图.md` or `00_课程总览.md` as the entry point.
- Numbered detailed notes such as `01_导论.md`, `02_核心概念.md`, paper notes, or chapter-based names.
- `source_manifest.md` with URLs, titles, source types, access status, and what each source contributed.
- Per-link notes such as `L01_<title>.md` when the source is a reading list, topic preview, paper list, syllabus, bibliography, or the user asks for each link to be handled separately.
- `知识点详细版_含公式.md` when the material is course-like.
- `知识点精简复习版_含公式.md` or `快速复习.md` for review.

Keep source URLs in notes or frontmatter so provenance stays visible.

## Handoff Boundaries

Use this skill when the starting point is web sources or local HTML. If a source becomes a local PPT/PPTX/PDF courseware file that needs extraction, use `$ppt-to-md-for-obsidian`. If the user asks for vault-only cleanup, broken-link repair, or duplicate-note merging after notes exist, use `$obsidian-vault-organizer`.

## Quick Start

1. Classify each URL as course, video, slide/PPT, PDF, book/chapter, reading list, or mixed catalog.
2. Build `source_manifest.md` before drafting notes, including access status and what each source contributes.
3. Choose the target category by inspecting nearby folders and notes when a notes directory is provided.
4. Expand scaffolds into detailed source-linked notes only after accessible content has been read or extracted.
5. Run source-coverage, scaffold-residue, link, and anti-template checks before the final response.

## Evidence And Assumption Gate

Treat page titles, canonical URLs, abstracts, transcripts, tables of contents, PDFs, slides, and user-provided excerpts as evidence. Mark inaccessible, authenticated, paywalled, ambiguous, or client-rendered helper URLs separately. Do not infer detailed claims from a URL title alone; report remaining source gaps when full reading or login access is required.

## Workflow

1. Clarify source boundaries.
   - Identify whether each URL is a video page, course index, slides/PPT/PDF page, book/chapter page, or mixed catalog.
   - Ask the user before using authenticated pages if browser access, cookies, downloads, or paid content are involved.
   - Do not download or mirror large source collections unless the user explicitly asks and the source allows it.

2. Build a source manifest.
   - Use `scripts/collect_web_sources.py` when a deterministic URL inventory helps.
   - Direct PDF/PPT/transcript/book URLs should be recorded as resources without attempting to parse binary content as HTML.
   - Capture titles, canonical URLs, descriptions, source type, and links to slides, videos, transcripts, chapters, and PDFs.
   - Process sources independently. If one URL or local HTML file fails, keep it in `source_manifest.md` with `access_status`, source type guess, and a concise error instead of dropping the source or failing the whole manifest.
   - For client-rendered pages, record both the visible page URL and any legitimate public data endpoint or static bundle used only to locate the endpoint. Mark helper URLs as provenance, not learning material.
   - Record inaccessible or ambiguous sources instead of silently skipping them.

3. Place notes in the vault.
   - If the user provides an Obsidian notes directory, inspect existing top-level folders and classify the collection into the closest existing folder.
   - If no existing folder fits, create a new folder under the notes directory, preferably `网络资源/<collection-title>/`.
   - Use `scripts/create_web_notes.py --notes-dir <notes-dir> <url...>` to create the collection folder, `source_manifest.md`, `00_学习地图.md`, and detailed note scaffolds.
   - Use `--category <folder>` when the user or context clearly identifies the destination category.
   - `--language auto` is the default. It writes Chinese scaffolds when user inputs, collected titles, or descriptions contain Chinese characters and English scaffolds otherwise. Use `--language zh|en` only when the scaffold language should be explicit.
   - Treat script-created scaffolds as unfinished. Do not deliver them as final notes until the accessible source content has been read, extracted, and rewritten into the scaffold.

4. Extract only appropriate content.
   - Prefer official transcripts/captions for videos when available.
   - Prefer page headings, abstracts, tables of contents, slide titles, and user-provided excerpts for books.
   - For direct PDF/PPT URLs, record the URL first, then extract the accessible content when allowed. If the source becomes a local courseware file, hand off to `$ppt-to-md-for-obsidian`.
   - If the user supplies an existing Obsidian vault, use `$obsidian-vault-organizer` after drafting.

5. Generate notes.
   - Match the final-note language to the user and source context: Chinese for Chinese input, English for English input, unless the user requests otherwise.
   - Inspect 1-3 nearby notes in the target category before writing final notes, then match their density, navigation style, formula treatment, and review style.
   - Convert fragments into explanations, not web-page dumps.
   - Add formulas, variable meanings, examples, assumptions, and failure cases when present.
   - For reading lists and paper lists, create one independent note per source link when the user asks for detailed organization or when the list is the main artifact. Each per-link note should include source role, problem addressed, method or content mechanism, connection to the topic, limitations, and what to inspect when reading or reproducing. Do not stop at a table of links.
   - For paper-like resources, include problem background, method overview, mechanism details, formulas and variables, experiments or evidence, comparison with related methods, advantages, limits, open questions, reproduction/application notes, and a concise review section.
   - Link concepts where they first become relevant.
   - Cite source URLs near the sections they support.
   - Remove scaffold residue before final delivery. A note that still contains `status: scaffold`, `待补充`, or TODO-style placeholders is incomplete and must be reported as unfinished, not presented as done.
   - Avoid templated per-link notes. Repeated headings are acceptable only if the body contains source-specific mechanisms, formulas, datasets, risks, or reading questions. Replace phrases like "important", "valuable", and "helpful" with concrete reasons and checks.

6. Validate before finishing.
   - Check local Obsidian links with `$obsidian-vault-organizer`.
   - Run `scripts/check_web_notes.py <collection-dir> --source <user-url>` with every user-supplied URL or local source, and add `--per-link-notes` when the user requested per-link notes.
   - Check that `source_manifest.md` covers every URL the user supplied, including inaccessible or failed sources.
   - For each URL in `source_manifest.md`, verify there is a corresponding per-link note when per-link notes were requested or the source is a reading list. Include helper endpoints and client-rendered provenance URLs as separate notes if they are listed in the manifest.
   - Check that generated notes do not contain long copied passages from books or web pages.
   - Check that final notes are comparable in detail to existing notes in the destination folder.
   - Run an anti-template audit on per-link notes: flag very short notes, identical heading patterns, vague "value/importance" language without concrete mechanisms, and notes that lack limitations or reading/reproduction checks.
   - If a quality issue is found late, either fix it before delivery or add a `质量审查` note that clearly states what is complete, what is only a guide, and what would require full source-level reading.

## Source Policy

Read `references/source-policy.md` when a source is authenticated, paywalled, copyrighted, robots-restricted, or ambiguous.

## Output Style

Read `references/note-output.md` when deciding how to structure notes for course videos, slide sites, book sites, or mixed web resources.

## Output Contract

The final response should include:

- collection folder path and whether it reused an existing category or created a new one,
- `source_manifest.md` path and source coverage summary for every user-supplied URL,
- note files created or updated, including per-link notes when required,
- inaccessible, authenticated, paywalled, ambiguous, or copyright-limited sources,
- validation performed, including source coverage, scaffold residue, link checks, and anti-template review when applicable,
- remaining source gaps that would require full reading, login access, or user-provided material.

If the run only produced scaffolds, say they are unfinished scaffolds and do not present them as final notes.

## Bundled Resources

- `scripts/collect_web_sources.py`: collect titles, descriptions, access status, errors, and learning-resource links from URL or local HTML inputs.
- `scripts/create_web_notes.py`: classify sources into a notes directory, create a collection folder, and write `source_manifest.md`, `00_学习地图.md`, and detailed note scaffolds that must be expanded before final delivery.
- `scripts/check_web_notes.py`: validate finalized web-note collections for source coverage, scaffold residue, and per-link note coverage when required.
- `references/source-policy.md`: source access, copyright, attribution, and safety rules.
- `references/note-output.md`: note structures for video courses, PPT sites, book sites, and mixed web learning resources.
