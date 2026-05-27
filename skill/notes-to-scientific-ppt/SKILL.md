---
name: notes-to-scientific-ppt
description: Use when the user provides Obsidian notes, Markdown notes, literature notes, paper notes, course notes, experiment notes, or a notes folder and wants Codex to turn them into a detailed, vivid, scientifically rigorous PowerPoint/PPTX research deck; also use for Chinese requests such as 基于笔记做PPT, 根据笔记生成PPT, or 科研严谨风PPT. Use this for lab meeting talks, paper reading presentations, thesis defenses, project proposals, research progress reports, and technical teaching decks. Use $ppt-to-md-for-obsidian instead when the task starts from local PPT/PPTX/PDF courseware, and use $obsidian-vault-organizer when the task is only vault cleanup.
---

# Notes To Scientific PPT

## Goal

Turn existing notes into an editable PPTX deck with a research-rigorous style: precise claims, traceable evidence, clear formulas, real mechanisms, visual explanations, and enough detail to support technical questioning.

The output should feel like a serious research presentation, not a note dump, marketing deck, or generic template.

## Default Outputs

Prefer these deliverables:

- `<topic>_deck_brief.md`: source inventory, claim spine, evidence coverage, missing inputs, and slide plan.
- `<topic>.pptx`: editable PowerPoint deck.
- Optional `<topic>_speaker_notes.md`: slide-by-slide narration when the talk is substantial.
- Optional appendix slides for dense derivations, raw tables, source excerpts, or extended comparisons.

Use Chinese by default when the user writes Chinese.

## Required Inputs

Accept one or more Markdown files, Obsidian notes, folders, or a vault path. If the user does not specify audience, talk length, or deck mode, infer them from the notes and state the assumptions in the deck brief.

Ask only when a missing input would materially change the deck, such as defense vs teaching audience, a mandatory template, or whether unpublished figures may be used.

## Workflow

1. Confirm the presentation frame.
   - Identify audience and occasion: lab meeting, reading group, course lecture, defense, proposal, progress report, or conference-style talk.
   - If the user does not specify length, assume a 15-20 minute research talk with 12-18 main slides plus optional appendix.
   - Preserve source note paths and source URLs for provenance.

2. Audit the notes before writing slides.
   - Use `scripts/outline_note_deck.py <note-or-folder...> --out <deck_brief.md>` when a deterministic source inventory helps. Use `--mode` when the deck type is known.
   - Read the important notes, not only the headings. Follow local Obsidian links when they are needed to understand definitions, formulas, or evidence.
   - Extract research question, motivation, assumptions, methods, formulas, variables, figures, tables, experiments, limitations, and open questions.
   - Treat unsupported claims as gaps. Do not invent metrics, experiments, citations, or conclusions.
   - Use the brief's evidence ledger and draft slide backlog to decide what belongs in main slides, appendix, or missing-input questions.

3. Build the scientific claim spine.
   - Use claim titles, not vague section labels. Each slide title should say the point the slide proves.
   - Convert notes into a story: problem -> gap -> hypothesis or method -> mechanism -> evidence -> limits -> implications.
   - Keep technical depth. If a formula, algorithm, or experiment is central in the notes, it must appear in the deck or appendix with explanation.

4. Design the deck plan.
   - For paper-reading decks, prefer: title, question, motivation, related framing, method intuition, mechanism, equations, implementation details, experiments, ablations, comparison, limitations, discussion, appendix.
   - For project/proposal decks, prefer: problem, prior gap, hypothesis, method, data, evaluation, milestones, risks, expected contribution.
   - For teaching decks, prefer: concept ladder, examples, mechanism diagrams, worked formulas, common mistakes, summary.
   - Read `references/scientific-deck-style.md` before designing a substantial deck.
   - Read `references/deck-modes.md` when choosing between paper-reading, proposal, progress-report, teaching, or defense modes.

5. Build the PPTX.
   - Use the bundled `Presentations` skill when available for editable PPTX creation, rendering, and export.
   - Use visual proof objects: mechanism diagrams, equation-to-intuition bridges, result tables, ablation ladders, before/after examples, failure-case panels, or comparison matrices.
   - Prefer light, high-contrast, restrained research styling. Avoid decorative gradients, generic icon cards, marketing hero layouts, and unsupported visual drama.
   - Cite source note filenames or source URLs in quiet footers, speaker notes, or appendix where useful.

6. Validate before finishing.
   - Read `references/deck-qa.md` and apply its gates.
   - Every main slide should have one claim, one proof object, and a clear takeaway.
   - Check formula slides for variable definitions, interpretation, and assumptions.
   - Check evidence slides for source traceability and no invented facts.
   - Render previews/contact sheet if a PPTX is produced, then iterate weak slides before final delivery.

## Output Contract

The final response should include:

- final PPTX path when a deck was produced,
- deck brief path,
- source coverage summary,
- unresolved assumptions or missing evidence,
- validation performed, including preview/render checks when applicable.

## Bundled Resources

- `scripts/outline_note_deck.py`: scan Markdown/Obsidian notes and create a source inventory, evidence ledger, mode-specific scientific deck spine, draft slide backlog, and coverage checklist.
- `scripts/validate_skill.py`: validate this skill's structure and referenced bundled resources.
- `references/scientific-deck-style.md`: style and content rules for detailed, vivid, research-rigorous decks.
- `references/deck-modes.md`: mode-specific slide spine and proof-object guidance.
- `references/deck-qa.md`: QA gates for scientific accuracy, slide density, evidence, formulas, and visual polish.
