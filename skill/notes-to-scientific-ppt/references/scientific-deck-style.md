# Scientific Deck Style

## Core Standard

A good research deck is detailed, vivid, and rigorous at the same time:

- detailed: it preserves the mechanism, assumptions, formulas, and evidence chain;
- vivid: it uses diagrams, examples, annotated results, and failure cases to make ideas inspectable;
- rigorous: every technical claim is traceable to notes, source URLs, experiments, or clearly marked inference.

## Slide-Level Rules

- Use claim titles. Replace labels like `Method` with a conclusion such as `Noise-level estimation turns blind denoising into a supervised subproblem`.
- One slide should prove one main point. If a note section contains multiple arguments, split it across slides or move detail to appendix.
- Put a proof object on each main slide: diagram, formula bridge, result table, example panel, ablation ladder, comparison matrix, timeline, or algorithm sketch.
- Use speaker notes for the oral argument and source traceability when slide space is limited.
- Keep equations readable. Every important variable needs a definition and a short intuition.

## Research Visual System

Prefer:

- light background, dark text, restrained accent colors;
- clear hierarchy with large claim title, compact evidence block, and source footer;
- native editable diagrams and tables whenever possible;
- consistent notation, axis labels, units, and figure captions;
- appendix for derivations, raw tables, or extended source material.

Avoid:

- marketing hero pages, decorative gradient blobs, stock-like imagery, and generic icon-card grids;
- slide titles that only name a topic without making a claim;
- raw note paragraphs pasted into text boxes;
- unsupported metrics, invented citations, or overconfident conclusions;
- tiny formulas, missing variable definitions, or cropped source figures without captions.

## Vivid Research Patterns

Use these patterns when they fit the notes:

- Problem contrast: show a concrete failure case before the method.
- Equation-to-intuition bridge: pair the formula with a plain-language interpretation and variable legend.
- Mechanism pipeline: turn method steps into an inspectable flow diagram.
- Ablation ladder: show how each component changes the result or failure mode.
- Comparison matrix: compare assumptions, inputs, strengths, limits, and evidence.
- Error gallery: show where the method fails and why that matters.
- Reproduction checklist: summarize data, model, metrics, parameters, and hidden implementation risks.

## Typical Research Deck Spine

1. Title and research question.
2. Motivation: why the problem matters.
3. Gap: what existing methods or notes fail to explain.
4. Main idea or hypothesis.
5. Method overview.
6. Key mechanism 1.
7. Key mechanism 2.
8. Core formula or algorithm.
9. Experimental setup or evidence source.
10. Main results.
11. Ablation or comparison.
12. Limitations and failure cases.
13. Implications and discussion.
14. Appendix for dense technical material.
