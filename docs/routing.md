# Skill Routing

Use this guide when a task could match more than one skill. Route by the user's starting material first, then by the requested final output.

## Trigger Boundaries

| Starting point | User intent | Use this skill | Do not start with |
| --- | --- | --- | --- |
| URL, webpage course, online book, public reading list, local HTML, or direct PDF/PPT/transcript URL | Collect accessible sources, create `source_manifest.md`, scaffold or write URL-based course, book, or paper notes | `web-course-notes-for-obsidian` | `ppt-to-md-for-obsidian` unless a permitted file has already been downloaded locally and needs extraction |
| Local PPT/PPTX/PDF lecture files or courseware folders | Extract slide/page text, build source coverage, write course notes and review pages | `ppt-to-md-for-obsidian` | `web-course-notes-for-obsidian` unless the source is still a web page or URL list |
| Local research-paper PDF and a request for a source-backed paper note, or notes to use before a deck | Extract the paper, verify its bibliographic identity, and write a note covering method, evidence, reproducibility, and failure boundaries | `ppt-to-md-for-obsidian` | `web-course-notes-for-obsidian` when the task starts from a URL; `notes-to-scientific-ppt` until paper notes exist |
| Solvenotes workspace with its Notes and Skills repositories | Run repository-wide validation, maintain lock/provenance and packaging boundaries, migrate maintenance tooling, or coordinate several note skills | `solvenotes-vault-maintainer` | `obsidian-vault-organizer` when the scope includes Skills, version locks, packages, or workspace-level release checks |
| Existing algorithm-job Obsidian notes, recruiting maps, interview routes, or direction cleanup | Enforce the nine canonical directions, migrate extra routes, strengthen DSA/C++17/ML evidence, and validate JD mappings | `algorithm-job-notes-for-obsidian` | `obsidian-vault-organizer` when the request changes the nine-direction taxonomy; generic cleanup that leaves the taxonomy untouched may start there |
| Existing Obsidian vault or Markdown note collection | Repair links, merge duplicates, improve navigation, validate note quality, clean stale files | `obsidian-vault-organizer` | `ppt-to-md-for-obsidian` unless source extraction is still required |
| Existing Markdown/Obsidian notes or notes folder | Create a scientific deck brief and finished editable PPTX presentation; the bundled builder starts from a skeleton | `notes-to-scientific-ppt` | Source-collection skills unless the notes do not exist yet |

The bundled scientific-deck builder creates an editable PPTX skeleton. Treat it
as a draft until slide-specific content and proof objects are completed and the
rendered slides have been manually inspected. If authoring or rendering tools are
unavailable, deliver the brief and clearly label the PPTX as a skeleton, with
the remaining work stated.

## Copy-Paste Examples

```text
Use $web-course-notes-for-obsidian for these course URLs. Build source_manifest.md first, keep inaccessible sources marked, then create source-linked Obsidian notes.
```

```text
Use $ppt-to-md-for-obsidian for these local PPT/PPTX/PDF courseware files. Extract the source text, build a coverage map, and write Obsidian course notes with formulas and review pages.
```

```text
Use $ppt-to-md-for-obsidian for this local research-paper PDF. Verify the paper's bibliographic details from the paper or an official record, then write a source-backed note with its method, evidence, reproducibility limits, and failure boundaries.
```

```text
Use $obsidian-vault-organizer for this existing vault. Audit links, duplicate stems, navigation, and note quality before editing; keep source files read-only.
```

```text
Use $solvenotes-vault-maintainer for this Solvenotes workspace. Keep maintenance artifacts outside Notes, run the repository-wide gates, and preserve the Notes-to-Skills version lock until the Skills changes are committed.
```

```text
Use $algorithm-job-notes-for-obsidian for this algorithm-job vault. Compare all route, frontmatter, JD, skill, and agent directions with the nine canonical IDs; migrate unique material, delete obsolete route files, and run the full validation suite.
```

```text
Use $notes-to-scientific-ppt for this notes folder. Create a deck brief and finished editable PPTX with claim, formula, evidence, limitations, and appendix slides, starting from the builder skeleton. Finish the slide content and inspect the rendered deck before delivery. If suitable authoring or rendering tools are unavailable, label the PPTX as a skeleton and list the remaining work.
```

## Mixed Workflows

### Web Sources To Local Courseware Or Paper Notes

1. Start with `web-course-notes-for-obsidian` when the user gives course pages, online books, paper lists, or direct PDF/PPT URLs.
2. Record every source in `source_manifest.md`, including inaccessible or failed URLs.
3. If the user legitimately downloads a courseware PDF/PPT/PPTX and asks for slide/page extraction, or downloads a research-paper PDF and asks for a paper note, hand off that local file to `ppt-to-md-for-obsidian`.
4. Keep the original URL provenance in the notes or manifest so the local file does not lose source context.

Example:

```text
First use $web-course-notes-for-obsidian to inventory these URLs. After I download the linked course PDFs or paper PDF locally, use $ppt-to-md-for-obsidian for extraction and course or paper notes, preserving the original URL provenance.
```

### Course Notes To Vault Cleanup

1. Use `ppt-to-md-for-obsidian` while slide/PDF extraction, source coverage, formulas, examples, or course-note drafting are still active.
2. After notes exist and remaining work is link repair, duplicate cleanup, navigation, or vault-wide validation, hand off to `obsidian-vault-organizer`.
3. Run vault link and quality checks after cleanup before claiming the course notes are ready.

Example:

```text
Use $ppt-to-md-for-obsidian to finish the course notes from these local slides. When the notes are complete, use $obsidian-vault-organizer to repair links, merge duplicate topic notes, and update navigation.
```

### Finished Notes To Scientific PPTX

1. Use `notes-to-scientific-ppt` only after there are actual notes, not just raw URLs or source courseware.
2. If the notes still have broken links, duplicate fragments, or weak navigation, use `obsidian-vault-organizer` first.
3. Generate a deck brief before building the PPTX so slide claims stay grounded in the notes. The bundled builder starts with a skeleton; finish slide content and visual checks before delivery.

Example:

```text
Use $obsidian-vault-organizer to clean this finished course-note folder, then use $notes-to-scientific-ppt to create a research-deck brief and PPTX skeleton. Complete slide-specific content and inspect rendered slides before calling the deck finished.
```

### Algorithm-job Notes To Generic Vault Cleanup

1. Use `algorithm-job-notes-for-obsidian` first when the task changes algorithm-job direction taxonomy, role maps, JD categories, learning routes, or interview evidence.
2. Let it migrate unique material and remove obsolete route definitions; technical mentions such as RL or multimodal may remain as mapped topics.
3. Hand off to `obsidian-vault-organizer` for generic duplicate, link, navigation, or quality cleanup after the direction contract is stable.
4. If the task starts from local courseware, use `ppt-to-md-for-obsidian` for extraction before either notes-maintenance skill.

Example:

```text
Use $algorithm-job-notes-for-obsidian to collapse this vault to the nine algorithm-job directions and strengthen the interview evidence. After the taxonomy is stable, use $obsidian-vault-organizer to run the generic link and note-quality checks.
```

## Routing Heuristic

- If the source is a web address, route to `web-course-notes-for-obsidian` first, including direct paper-PDF URLs.
- If the input is a local courseware file or a local research-paper PDF that needs a source-backed note, route to `ppt-to-md-for-obsidian`.
- If the task spans the Solvenotes Notes and Skills repositories, version locks, clean packages, or release gates, route to `solvenotes-vault-maintainer` and let it coordinate the narrower note skills.
- If the input is an existing vault and the requested change concerns algorithm-job routes, JD categories, interview maps, or nine-direction migration, route to `algorithm-job-notes-for-obsidian`.
- If the input is already a vault or note folder and the desired output is still notes, route to `obsidian-vault-organizer`.
- If the input is already notes and the desired output is a deck, route to `notes-to-scientific-ppt`.
