# Scientific PPT QA

## Blocking Gates

- Source gate: every non-obvious claim is backed by a note file, source URL, figure, table, experiment, or explicitly marked inference.
- Brief gate: the deck brief includes source inventory, evidence ledger, mode-specific spine, draft slide backlog, and missing-input questions before PPT construction.
- Skeleton gate: when `scripts/build_scientific_deck.py` is used, treat the PPTX as an editable skeleton generated from the brief, not a finished deck. Replace every placeholder proof-object block before final delivery.
- Coverage gate: the deck brief maps important note sections to slides or appendix; important material is not silently dropped.
- Formula gate: key equations include variable definitions, intuition, assumptions, and at least one sentence on why the formula matters.
- Evidence gate: results slides include task, dataset or source context, metric names, units, and interpretation.
- Limitation gate: the deck states failure modes, missing evidence, assumptions, or open questions when present in the notes.
- Visual gate: every main slide has a claim title and a proof object; no main slide is just paragraphs.
- Density gate: slides are detailed enough for research discussion but not overloaded. Move dense derivations and raw tables to appendix.
- Export gate: if a PPTX is produced, render previews/contact sheet and iterate visible layout, overlap, truncation, and readability issues.

## Brief To PPTX Skeleton

`outline_note_deck.py` produces the source audit and slide plan. `build_scientific_deck.py` consumes that plan to create an editable PPTX skeleton with title, claim, formula, evidence/table, limitations, and appendix index slides.

The skeleton should contain concise proof-object placeholders only. Do not paste long note paragraphs into slides. During finalization, each placeholder must become a concrete mechanism diagram, formula bridge, result table, comparison matrix, limitation panel, or appendix item backed by the source notes.

## Final Review Questions

- Could a technical audience challenge the main claim and find the supporting evidence quickly?
- Are all formulas and variables readable at presentation size?
- Does each slide explain why the audience should care?
- Are limitations honest and specific?
- Does the deck preserve the note's rigor while making the story easier to follow?
