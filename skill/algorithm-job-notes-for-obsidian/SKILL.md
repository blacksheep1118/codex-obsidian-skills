---
name: algorithm-job-notes-for-obsidian
description: Use when maintaining algorithm-job learning notes, internship or recruiting maps, interview preparation, or direction-aware Obsidian vaults; enforce the nine directions, executable algorithms, and evidence-first JD analysis. Use $obsidian-vault-organizer for generic vault cleanup and $ppt-to-md-for-obsidian for local courseware extraction.
---

# Algorithm Job Notes for Obsidian

Maintain an algorithm-job knowledge base that a learner can navigate, study,
implement, review, and use in interviews. This skill is a specialization of
the vault workflow: it adds a closed direction taxonomy, migration rules, and
evidence contracts. It does not turn every technical topic into a job route.

## Quick Start

1. Read the target vault's `AGENT.md`, the relevant navigation pages, and the
   local `references/solvenotes-profile.md` when it exists.
2. Run `git status --short --branch` in every repository in scope. Preserve
   unrelated user changes; do not reset, clean, commit, or push unless asked.
3. Read the current algorithm-job map, role map, coverage matrix, interview
   entry, JD sample page, and review pages before adding content.
4. Compare every configured direction against the canonical set below. Treat
   route headings, frontmatter, aliases, tags, `job_tracks`, matrix columns,
   examples, tests, skills, and agents as configuration surfaces.
5. Migrate unique useful content to P0 foundations or one of the nine
   directions, update links and metadata, then remove obsolete route files.
6. Validate links, frontmatter, examples, formulas, code markers, and the
   repository's own full checks before writing a final response.

For a real vault scan, run the bundled read-only checker after the vault's
own quick gate:

```bash
python3 scripts/check_algorithm_job_vault.py /path/to/vault --json
```

The checker reads one canonical taxonomy from
`scripts/algorithm_job_taxonomy.py`. It inspects navigation headings, matrix
headers, route-shaped table/list rows, frontmatter direction fields, required
direction entries and the DSA/C++/training/ML handoff. It deliberately does
not reject a normal body sentence that mentions RL, GNN, RAG, multimodal
models or time-series. It never edits the vault.

## Canonical direction set

This is the only algorithm-job top-level direction set. Keep the IDs stable.
Do not create a tenth direction or ID when a new technology appears.

| id | label | boundary |
|---|---|---|
| `cv` | CV | image/video understanding, restoration, generation, vision foundation models |
| `nlp_llm` | NLP / LLM | NLP, language models, training, alignment, evaluation, RAG, Agent, language multimodality |
| `recommendation` | 推荐 | user/content matching, recall, ranking, feedback, long-term value, experiments |
| `search` | 搜索 | query/document relevance, indexing, retrieval, ranking, search evaluation |
| `speech` | 语音 | audio signals, ASR, TTS, speaker, audio understanding, speech multimodality |
| `robotics` | 机器人 | perception, state estimation, localization, mapping, planning, control, robot systems |
| `automotive` | 汽车算法 | ADAS/autonomous driving perception, fusion, prediction, planning, vehicle deployment |
| `embodied_ai` | 具身智能 | vision-language-action, policy learning, robot data, world models, Sim2Real |
| `ai_infra` | AI Infra | training/inference systems, GPU/CUDA, parallelism, kernels, serving, profiling |

Do not add `multimodal`, `reinforcement_learning`, `gnn`, `time_series`,
`rag`, `agent`, `aigc`, `diffusion`, `advertising`, `risk_control`,
`data_science`, `autonomous_driving`, or `mlops` as top-level IDs. They are
topics, evidence types, or aliases that must be mapped as follows:

- RAG, Agent, Prompt Engineering, LLM Evaluation, and alignment → `nlp_llm`;
  retrieval implementation links to `search`.
- Multimodal → map by task to `cv`, `nlp_llm`, `speech`, `robotics`,
  `automotive`, or `embodied_ai`; keep one core explanation and add application
  links.
- RL → `robotics` or `embodied_ai`, or an alignment subsection under `nlp_llm`.
- GNN and knowledge graphs → a support topic under `recommendation`, `search`,
  `cv`, `robotics`, or `nlp_llm`.
- Time-series → a support topic under `recommendation`, `speech`, `robotics`,
  or `automotive`, with explicit time-split evaluation.
- Diffusion → `cv`, `embodied_ai`, or `nlp_llm` according to the generated object.
- Advertising → migrate CTR/CVR, ranking, multi-objective, feature, experiment,
  and attribution content into `recommendation`; remove an advertising route.
- Autonomous driving, intelligent driving, and vehicle perception → `automotive`.
- MLOps, ordinary platform operations, and deployment work → `ai_infra` only
  when it serves model training, inference, or algorithm delivery; otherwise
  keep it as limited general engineering context.

## Evidence And Assumption Gate

Before editing, separate facts, local conventions, and assumptions:

- Use the vault's current filename, frontmatter, link, and source-manifest
  rules. Do not invent a second schema.
- Use official recruitment pages for current JD claims. Record company, role,
  direction, internship/graduate/full-time stage, location, check date, URL,
  and status uncertainty. Never fabricate a JD or generalize a small sample
  into a market percentage.
- Mark a code block as runnable only when it is self-contained, has its
  dependencies stated, and has been run or compiled. Do not extract and run
  every unknown Markdown fence.
- Dependency-backed Python examples use the exact `python-e2e` marker and the
  explicit runtime gate; ordinary Python fences remain syntax-only. When such
  execution is in scope, read
  [references/python-runtime-validation.md](references/python-runtime-validation.md)
  before running anything. Missing dependencies are a failure of that explicit
  gate, not a passing skip.
- Keep technical mentions of RL, multimodal, GNN, advertising, medicine, or
  time-series when they are part of a course, paper, project, or application;
  the prohibition concerns top-level job classification, not vocabulary.
- Keep source files outside the notes vault read-only. Put temporary scans and
  migration maps outside the vault; never create audit or cleanup report notes.

## Direction-Cleanup Workflow

Use this workflow whenever the task includes route cleanup or taxonomy repair:

1. Enumerate current top-level directions from navigation, route headings,
   folders, frontmatter, tags, `job_tracks`, matrices, JD tables, skills,
   agents, tests, and examples.
2. Compute the set difference from the nine IDs in this file; report the
   evidence in temporary files, not in the vault.
3. For each extra route, read its actual content and classify it as P0
   foundation, a nine-direction internal topic, or low-value redundancy.
4. Extract unique explanations, formulas, examples, and links before deleting
   anything. Preserve source URLs and the best existing prose.
5. Merge the useful material into the smallest suitable foundation or direction
   page. Prefer links to duplicated explanations.
6. Replace links, aliases, headings, frontmatter fields, tags, matrix columns,
   JD categories, tests, examples, skill routes, and agent rules.
7. Delete obsolete route files, directories, empty placeholders, and duplicate
   entrances after link replacement. Do not leave “deprecated”, “old entry”,
   or “see new page” stubs unless the local vault explicitly requires redirects.
8. Run the link inventory before and after. Investigate unexplained link loss;
   zero broken links alone is not enough.
9. Search for old route names and inspect each hit to distinguish a natural
   technical mention from a remaining top-level job definition.

## Learning Quality Contract

Organize the route as P0 common foundations, P1 direction core, and P2
cross-direction extensions. The main map must offer executable 4-week, 8-week,
12-week, pre-7-day, and pre-24-hour plans. Prefer artifacts over reading
counts: timed coding, C++17 compilation, hand-written ML/DL implementations,
project evidence, mock interviews, and redo results.

The DSA contract should cover recognition signal, naive solution and bottleneck,
invariant, algorithm steps, correctness, time/space complexity, runnable C++17,
optional Python, boundary cases, counterexamples, exercises with answers, oral
version, and variants. The C++ interview layer owns STL semantics, comparator
contracts, iterator invalidation, integer overflow, `size_t`, `lower_bound`,
`upper_bound`, heap defaults, and lifetime boundaries. Engineering pages own
RAII, ownership, concurrency, Sanitizer, ABI, build, and Python/C++ interfaces.

The ML/DL/PyTorch layer should train numerical stability and shape reasoning:
linear/logistic regression, MSE and gradients, stable Softmax/Cross Entropy,
kNN, k-means, PCA, Attention, LayerNorm, BatchNorm, IoU/NMS/Top-K, metrics,
autograd, `detach`, `no_grad`, `inference_mode`, `train/eval`, AMP, checkpoint,
DDP, and FSDP. Keep one detailed explanation per cross-topic concept.

Projects and interviews must ask for data split/leakage, baseline, loss,
metrics, ablation, seeds, bad cases, training/inference cost, deployment,
failure boundaries, and the candidate's exact contribution. A mother question
bank should provide a 30-second answer, a two-minute answer, follow-ups, common
mistakes, and links rather than hundreds of shallow definitions.

## Output Contract

The final response must state the vault and repositories actually changed,
important migrations/deletions, the current nine-direction result, and exact
validation commands with PASS/FAIL. Distinguish static validation from
unexecuted GUI, training, checkpoint-load, OCR, or dependency-backed end to
end work. State whether commit or push occurred. Do not claim an installed
skill mirror changed when only the source repository was edited.

## Validate before finishing

Run the local commands appropriate to the repositories in scope. For the
Solvenotes vault, prefer the project maintainer from the Skills repository
root: `bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh quick`
first and `bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh full`
last. Use the maintainer's targeted checks for frontmatter, links, examples,
and formulas; use this Skill's own
`skill/algorithm-job-notes-for-obsidian/scripts/check_cpp_examples.py` for
marked C++ blocks. Use the repository's own `scripts/` and `tests/` rather
than inventing a parallel validator. Use `references/` for project-specific
rules and validation details.

For this skill's direction-aware behavior, run the isolated scanner tests and
validator as well:

```bash
python3 -m pytest skill/algorithm-job-notes-for-obsidian/tests
python3 skill/algorithm-job-notes-for-obsidian/scripts/validate_skill.py
```

When the request explicitly requires dependency-backed Python execution, use
the separate `vault-runtime` profile with a reviewed environment. Do not add
ONNX, PyTorch, or PySpark to `requirements-dev.txt` or ordinary public CI; the
known-good optional set lives in `requirements-runtime.txt`.

The scanner tests use small temporary Vault fixtures covering a valid nine-
direction map, a missing direction, an extra RL route, natural RL prose, a
combined route, stale frontmatter, and missing DSA/C++ entries. Unknown code
fences remain outside the runnable-code check; only the vault's explicit
`<!-- runnable: cpp17 -->` marker is eligible for compilation.

For the source skill repository, run its root hygiene, pytest, metadata,
install dry-run, and full validator commands; run the changed skill's isolated
tests and validator as well. For an agents directory without Git or tests,
perform a deterministic rule scan and report that it is a file-level check.

## Handoff Boundaries

- Use `$obsidian-vault-organizer` for generic vault link repair, duplicate
  merging, navigation, and note-quality cleanup. This skill owns the algorithm
  job taxonomy and migration decisions.
- Use `$ppt-to-md-for-obsidian` when local PPT/PPTX/PDF courseware extraction is
  the starting task; do not claim extracted text is visual OCR.
- Use `$web-course-notes-for-obsidian` when collecting URL-based course or
  paper sources; preserve its source-manifest contract.
- Use `$notes-to-scientific-ppt` when the desired output is a scientific deck,
  not a notes-vault route.
- Edit the source skill under `/solvenotes/skills`. Do not edit an installed
  mirror directly; use the repository's documented install/check flow only
  when the user explicitly requests synchronization.

## Bundled Resources

- `references/algorithm-job-contract.md`: compact contract for direction IDs,
  migration, evidence, and validation.
- `scripts/algorithm_job_taxonomy.py` and
  `scripts/check_algorithm_job_vault.py`: the single taxonomy and the
  read-only structural scanner for this skill.
- `scripts/check_cpp_examples.py`: compiles and runs only self-contained C++17
  blocks preceded by `<!-- runnable: cpp17 -->`; unknown Markdown fences are
  never executed. Its synchronized `scripts/run_with_timeout.py` helper kills
  the complete compiler/example process tree on timeout.
- `scripts/check_python_runtime_examples.py` and
  `references/python-runtime-validation.md`: execute only reviewed
  `python-e2e` blocks in isolated temporary working directories, with declared
  dependency and Java checks, bounded process trees, and hard failure on
  missing runtime coverage.
- `scripts/`: use the repository-level validators and install scripts; do not
  create a second installation mechanism inside this skill.
- `references/`: read the vault's local profile and validation notes before
  making broad changes.
