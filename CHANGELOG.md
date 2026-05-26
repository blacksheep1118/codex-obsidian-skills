# Changelog

All notable changes to this repository are documented here.

## Unreleased

- Added `web-course-notes-for-obsidian` for course video websites, PPT/slide websites, book websites, and mixed online learning resources.
- Added web source manifest collection, examples, tests, and CI validation for the new skill.
- Added cross-platform install, update, validation, and development documentation for macOS/Linux shells and Windows PowerShell.
- Added Windows-aware LibreOffice discovery, platform-neutral temporary directories, Windows-style `file://` URL normalization tests, and macOS/Windows CI coverage.
- Pinned development pytest dependencies below 9.0 and kept platform-specific LibreOffice paths as raw strings so Python 3.9 and Windows validation paths remain installable and stable.
- Updated GitHub Actions checkout/setup-python actions to v6 and declared read-only contents permission for validation jobs.
- Forced UTF-8 output for validation CLIs that print Obsidian paths, avoiding Windows non-UTF-8 console failures.
- Decoded subprocess output as UTF-8 in test helpers so Windows CI can assert validator output containing Chinese paths.
- Added direct web-resource note creation so URL inputs can be classified into an existing notes folder, create `source_manifest.md`, and add detailed Obsidian note scaffolds.
- Forced UTF-8 output for web source and note-creation CLIs so Windows can print Chinese note paths.
- Strengthened the web note workflow so generated URL notes use detailed vault-style scaffolds and must be expanded from source content before final delivery.

## v0.1.0 - 2026-05-26

- Initial public skill collection with `ppt-to-md-for-obsidian` and `obsidian-vault-organizer`.
- Split courseware conversion from vault-only organization.
- Added skill-local README, LICENSE, validation, examples, references, and OpenAI metadata.
- Added root install, update, self-check, and full validation scripts.
- Added shared Obsidian link-checker synchronization validation.
- Added vault quality and course-note output checkers.
- Added fixtures, before/after examples, non-course examples, compatibility docs, safety docs, and contribution guidance.
