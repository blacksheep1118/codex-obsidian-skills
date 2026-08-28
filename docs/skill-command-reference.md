# Skill Command Reference

Run these commands from the repository root unless a section explicitly changes directory. The root [README](../README.md) contains installation, routing, and full validation commands; this page preserves the skill-specific command examples outside the installable skill folders.

## Web Course Notes

Use `web-course-notes-for-obsidian` when the inputs are URLs or local HTML. Its collector uses the Python standard library and records inaccessible inputs instead of dropping them.

Collect one or more sources into a manifest:

```bash
python3 skill/web-course-notes-for-obsidian/scripts/collect_web_sources.py \
  skill/web-course-notes-for-obsidian/examples/sample-web-course/index.html \
  --out source_manifest.md
```

Create a language-aware collection scaffold in an external staging directory:

```bash
python3 skill/web-course-notes-for-obsidian/scripts/create_web_notes.py \
  https://example.com/course \
  --staging-dir /tmp/web-course-staging \
  --language auto
```

The command prints the staged collection path. Use `--category`, `--root-folder-name`, or `--map-note-name` to mirror the eventual vault layout. Read the accessible sources, replace every placeholder, and validate every user-supplied source:

```bash
python3 skill/web-course-notes-for-obsidian/scripts/check_web_notes.py \
  /tmp/web-course-staging/Web\ Resources/course \
  --source https://example.com/course \
  --per-link-notes
```

After validation, move or copy the completed collection into the chosen vault category. The compatibility form `--publish --notes-dir /path/to/notes` creates a new scaffold directly in the vault; use it only when the user explicitly wants an in-vault draft.

Direct PDF, PPT, transcript, and book URLs are inventoried without parsing binary content as HTML. Once a permitted source becomes a local PPT/PPTX/PDF file, hand it to `ppt-to-md-for-obsidian`.

## Local PPT, PPTX, And PDF Courseware

Use `ppt-to-md-for-obsidian` for deterministic local extraction and raw-artifact preparation. The extracted Markdown is input for rewriting, not a final note.

Extract PPTX text, tables, and speaker notes when the runtime exposes them:

```bash
python3 skill/ppt-to-md-for-obsidian/scripts/extract_pptx_text.py \
  path/to/slides.pptx \
  --out extracted.md
```

Convert a legacy PPT with LibreOffice, then extract the resulting PPTX:

```bash
python3 skill/ppt-to-md-for-obsidian/scripts/convert_ppt_to_pptx.py \
  path/to/slides.ppt \
  --out-dir converted_pptx
```

If LibreOffice is unavailable, the one-command pipeline can fall back to read-only OLE/CFB text-record extraction. That fallback is partial text evidence and does not establish complete slide or visual coverage.

Run the same partial fallback explicitly when you need to inspect its text-record output:

```bash
python3 skill/ppt-to-md-for-obsidian/scripts/extract_legacy_ppt_text.py \
  path/to/slides.ppt \
  --out extracted.md
```

Extract PDF text:

```bash
python3 skill/ppt-to-md-for-obsidian/scripts/extract_pdf_text.py \
  path/to/slides.pdf \
  --out extracted.md
```

The PDF extractor tries `pypdf`, `pdfplumber`, and `pdftotext`, records page and character coverage, and flags low-text/image-only sources that still need OCR or manual inspection.

Clean common formula-extraction noise:

```bash
python3 skill/ppt-to-md-for-obsidian/scripts/clean_latex_from_ppt.py \
  extracted.md \
  --unicode-math \
  --out cleaned.md
```

Run the configured extraction/cleanup pipeline:

```bash
python3 skill/ppt-to-md-for-obsidian/scripts/ppt_to_obsidian_pipeline.py \
  --config skill/ppt-to-md-for-obsidian/skill-config.example.yaml
```

The pipeline writes `raw_extracted/`, `cleaned/`, `pipeline_manifest.md`, and optional `notes_skeleton/` outputs. It disambiguates same-named sources and records fallback, blank-page/slide, and media limitations.

Check a completed course-note folder:

```bash
python3 skill/ppt-to-md-for-obsidian/scripts/check_obsidian_links.py /path/to/notes
python3 skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py /path/to/notes
```

For strict source ownership in a generic course repository:

```bash
python3 skill/ppt-to-md-for-obsidian/scripts/check_source_coverage.py \
  --source-root /path/to/course-root \
  --notes-root /path/to/course-root/notes \
  --mapping 'source-course=note-course' \
  --require-course-prefixed-source-refs
```

Project-local validators override generic assumptions. In particular, follow the Solvenotes manifest-only contract described by the skill reference instead of creating a generic coverage-audit note.

## Existing Vault Organization

Use `obsidian-vault-organizer` after notes exist and the remaining work is link repair, duplicate cleanup, navigation, or quality validation.

Check links:

```bash
python3 skill/obsidian-vault-organizer/scripts/check_obsidian_links.py /path/to/vault
```

Capture link counts outside the vault before and after broad edits:

```bash
python3 skill/obsidian-vault-organizer/scripts/link_inventory.py \
  /path/to/vault \
  --format json \
  --out /path/outside/vault/before-links.json
```

Check note quality:

```bash
python3 skill/obsidian-vault-organizer/scripts/check_vault_quality.py /path/to/vault
```

Use repeatable `--skip-dir <root-relative-directory>` arguments only for explicitly out-of-scope subtrees. Use `--strict-study`, `--profile`, and project-local pattern files when the vault contract requires stronger residue checks.

## Notes To Scientific PPT

Use `notes-to-scientific-ppt` when Markdown or Obsidian notes are the starting source and an editable research deck is the requested output.

Create a deterministic deck brief before building slides:

```bash
python3 skill/notes-to-scientific-ppt/scripts/outline_note_deck.py \
  /path/to/notes \
  --mode paper-reading \
  --out deck-brief.md
```

Build an editable PPTX skeleton from that brief:

```bash
python3 skill/notes-to-scientific-ppt/scripts/build_scientific_deck.py \
  deck-brief.md \
  --out scientific-deck.pptx
```

Reopen and verify the package; add rendering only when LibreOffice/Poppler are available:

```bash
python3 skill/notes-to-scientific-ppt/scripts/verify_pptx.py \
  scientific-deck.pptx
```

Add `--render` to render when LibreOffice/Poppler are available. Use `--require-render` when rendering is a blocking gate; it implies `--render` and returns nonzero if the render tools are unavailable or rendering fails.

The brief and verifier support evidence-first construction, but they do not replace slide-by-slide visual review of the rendered deck.
