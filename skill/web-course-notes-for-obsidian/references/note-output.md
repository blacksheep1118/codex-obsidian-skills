# Note Output Patterns

## Vault Placement

When a notes directory is provided, put each imported collection in one deterministic folder. Reuse an existing top-level category when the source clearly matches it, such as `计算机视觉` for CVPR/image papers. If no category fits, create `网络资源/<collection-title>/`.

Each collection folder should contain:

- `source_manifest.md`,
- `00_学习地图.md`,
- one or more numbered source or chapter notes.

`scripts/create_web_notes.py` defaults to `--language auto`: Chinese inputs, titles, or descriptions produce Chinese scaffolds; English-only inputs produce English scaffolds. Use `--language zh` or `--language en` when the user explicitly wants one language.

## Detailed Note Standard

Script-created notes are scaffolds, not final deliverables. They become final only after the accessible source content has been read or extracted and the placeholders have been rewritten. A final note should be comparable to nearby notes in the destination vault folder and should not contain `status: scaffold`, `待补充`, `To complete`, or TODO placeholders.

Before final delivery, run:

```bash
python3 scripts/check_web_notes.py <collection-dir> --source <user-url-or-local-source>
```

Repeat `--source` for every user-supplied URL or local HTML file. Add `--per-link-notes` when the source is a reading list, paper list, syllabus, bibliography, or the user asked for per-link notes.

Before finalizing, inspect 1-3 existing notes in the target category and match the local style for:

- navigation links and backlinks,
- section depth,
- formula formatting and variable explanations,
- examples, experiments, or application notes,
- concise review summaries.

For paper-like, PDF, or single-resource notes, prefer this structure:

- `相关` and `导航`,
- `来源` and `材料定位`,
- `问题背景`,
- `方法总览`,
- `关键机制`,
- `关键公式与变量`,
- `实验与案例` or `证据`,
- `方法比较`,
- `优点`,
- `缺点`,
- `未解决的问题`,
- `复现或应用要点`,
- `精简复习`.

Use source URLs for provenance, but rewrite explanations in your own words. Do not copy long source passages.

## Video Course Site

Prefer:

- `00_课程总览.md`
- one note per lecture or module,
- timestamped source references when transcripts are available,
- formula and concept explanations near the relevant lecture section,
- `知识点详细版_含公式.md`,
- `知识点精简复习版_含公式.md`.

Each lecture note should include source URL, lecture title, prerequisites, key concepts, mechanism, examples, formulas, and follow-up links.

## PPT Or Slide Website

Prefer a structure close to the slide order:

- overview page,
- numbered chapter notes,
- source manifest linking each slide deck,
- cleanup notes for extraction noise.

If the site provides local `.ppt`, `.pptx`, or `.pdf` files, use `$ppt-to-md-for-obsidian` for extraction.

## Book Or Chapter Website

Prefer:

- `00_阅读地图.md`,
- one note per chapter or concept cluster,
- concept glossary,
- theorem/formula notes when relevant,
- `快速复习.md`.

Summarize and explain. Do not copy long passages.

## Mixed Learning Resource List

Create `source_manifest.md` first, then group notes by topic rather than by URL unless the user asks for per-link notes. The manifest should preserve inaccessible sources with access status and error summaries instead of dropping them. Use URL-level provenance under each section so later edits can trace where each claim came from.

When per-link notes are required, each learning resource in `source_manifest.md` needs either a corresponding note that cites the URL or an explicit skipped/inaccessible status.
