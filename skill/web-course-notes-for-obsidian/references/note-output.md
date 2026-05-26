# Note Output Patterns

## Vault Placement

When a notes directory is provided, put each imported collection in one deterministic folder. Reuse an existing top-level category when the source clearly matches it, such as `计算机视觉` for CVPR/image papers. If no category fits, create `网络资源/<collection-title>/`.

Each collection folder should contain:

- `source_manifest.md`,
- `00_学习地图.md`,
- one or more numbered source or chapter notes.

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

Create `source_manifest.md` first, then group notes by topic rather than by URL. Use URL-level provenance under each section so later edits can trace where each claim came from.
