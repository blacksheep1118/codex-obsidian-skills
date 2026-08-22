# Algorithm-job contract

This reference keeps the stable contract close to the skill without repeating
the vault's project-specific instructions.

## Canonical IDs

```text
cv
nlp_llm
recommendation
search
speech
robotics
automotive
embodied_ai
ai_infra
```

These IDs are the complete top-level algorithm-job set. A technical keyword is
not an ID. Map it by task and context, then link to the shared core concept.
The bundled `scripts/algorithm_job_taxonomy.py` is the machine-readable center
for this contract; do not hand-write a second direction list in a scanner or
test.

## Migration decisions

| Legacy presentation | Destination |
|---|---|
| RAG, Agent, Prompt, LLM Evaluation, alignment | NLP / LLM; retrieval links Search |
| advertising, CTR/CVR, multi-objective ranking | Recommendation |
| autonomous driving, intelligent driving, vehicle perception | Automotive |
| multimodal, VLM, video-language, audio-language | CV, NLP / LLM, Speech, Automotive, Robotics, or Embodied AI by task |
| reinforcement learning, policy optimization | Robotics, Embodied AI, or NLP / LLM alignment |
| GNN, knowledge graph | Recommendation, Search, CV, Robotics, or NLP / LLM support topic |
| time-series | Recommendation, Speech, Robotics, or Automotive support topic |
| MLOps, serving, deployment | AI Infra when model-serving or training related |

If no destination has enough value, remove the route and its empty index. Do
not leave a deprecated page just to preserve a filename; Git history remains
the archive.

## Required migration evidence

Before deleting a route, record in a temporary file:

- source paths and unique sections;
- destination page and inserted links;
- aliases, tags, frontmatter, matrix columns, and config entries changed;
- links and tests updated;
- final link-inventory comparison.

Do not put this ledger in the vault. Keep only the durable learning content.

## Quality gates

Every direction entry should expose a learner-facing route, prerequisites,
implementation artifact, evaluation protocol, interview prompts, and project
evidence. P0 common foundations must include Python, C++17, DSA, mathematics,
ML/DL, PyTorch, Linux, SQL, system basics, experiments, and communication.

Runnable code requires an explicit marker, self-contained inputs, stated
dependencies, and a recorded compile/test command. Unknown code fences are not
automatically executable.

Ordinary Python fences are syntax-checked only. Dependency-backed examples use
the exact `python-e2e` marker and the separate runtime gate described in
`python-runtime-validation.md`; that gate must fail on missing dependencies,
unsupported Java, timeout, or nonzero exit rather than reporting a skip as
coverage.

The read-only `scripts/check_algorithm_job_vault.py` checks route-shaped
navigation, frontmatter and required entries. It must allow technical prose
to mention a cross-topic while rejecting that same topic when it is configured
as a top-level route.

Official JD entries require company, role, one canonical direction, stage,
location, check date, URL, and uncertainty/status notes. Small samples must
not be summarized as market percentages.

## Cleanup acceptance

```text
all core maps: nine directions only
all job_track/direction enums: nine IDs only
all obsolete route files/directories: removed or explicitly required redirect
all useful legacy material: migrated
links: no broken targets after rename/delete
quality checks: repository-specific full suite passed
```
