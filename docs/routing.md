# Skill Routing

Use this guide when a task could match more than one skill. Route by the user's starting material first, then by the requested final output.

## Trigger Boundaries

| Starting point | User intent | Use this skill | Do not start with |
| --- | --- | --- | --- |
| URL, webpage course, online book, public reading list, local HTML, or direct PDF/PPT/transcript URL | Collect accessible sources, create `source_manifest.md`, scaffold or write Obsidian web-course notes | `web-course-notes-for-obsidian` | `ppt-to-md-for-obsidian` unless a permitted file has already been downloaded locally |
| Local PPT/PPTX/PDF lecture files or courseware folders | Extract slide/page text, build source coverage, write course notes and review pages | `ppt-to-md-for-obsidian` | `web-course-notes-for-obsidian` unless the input is still a web page or URL list |
| Existing Obsidian vault or Markdown note collection | Repair links, merge duplicates, improve navigation, validate note quality, clean stale files | `obsidian-vault-organizer` | `ppt-to-md-for-obsidian` unless source extraction is still required |
| Existing Markdown/Obsidian notes or notes folder | Create a scientific deck brief or editable PPTX research deck | `notes-to-scientific-ppt` | Source-collection skills unless the notes do not exist yet |

## Copy-Paste Examples

```text
Use $web-course-notes-for-obsidian for these course URLs. Build source_manifest.md first, keep inaccessible sources marked, then create source-linked Obsidian notes.
```

```text
Use $ppt-to-md-for-obsidian for these local PPT/PPTX/PDF courseware files. Extract the source text, build a coverage map, and write Obsidian course notes with formulas and review pages.
```

```text
Use $obsidian-vault-organizer for this existing vault. Audit links, duplicate stems, navigation, and note quality before editing; keep source files read-only.
```

```text
Use $notes-to-scientific-ppt for this notes folder. Create a deck brief first, then build an editable scientific PPTX skeleton with claim, formula, evidence, limitations, and appendix slides.
```

## Mixed Workflows

### Web Sources To Local Courseware To Notes

1. Start with `web-course-notes-for-obsidian` when the user gives course pages, online books, paper lists, or direct PDF/PPT URLs.
2. Record every source in `source_manifest.md`, including inaccessible or failed URLs.
3. If the user legitimately downloads a PDF/PPT/PPTX from the web source and asks for slide/page extraction, hand off that local file to `ppt-to-md-for-obsidian`.
4. Keep the original URL provenance in the notes or manifest so the local file does not lose source context.

Example:

```text
First use $web-course-notes-for-obsidian to inventory these URLs. After I download the linked lecture PDFs locally, use $ppt-to-md-for-obsidian on the downloaded files and preserve the URL provenance.
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
3. Generate a deck brief before building a PPTX skeleton so slide claims stay grounded in the notes.

Example:

```text
Use $obsidian-vault-organizer to clean this finished course-note folder, then use $notes-to-scientific-ppt to turn the cleaned notes into a research-style PPTX deck.
```

## Routing Heuristic

- If the input is a web address, route to `web-course-notes-for-obsidian`.
- If the input is a local slide/PDF courseware file, route to `ppt-to-md-for-obsidian`.
- If the input is already a vault or note folder and the desired output is still notes, route to `obsidian-vault-organizer`.
- If the input is already notes and the desired output is a deck, route to `notes-to-scientific-ppt`.
