# Security

These skills are intended for local note workflows. They do not require network access for validation, link checking, vault quality checks, or PPTX/PDF text extraction.

## Source File Safety

- Source courseware, papers, datasets, and raw materials are read-only by default.
- Scripts write outputs only to paths provided by the user or to temporary validation directories.
- The update script does not create backups and only prunes stale files when `--prune` is explicitly passed.

## Sensitive Data

Do not commit private decks, student data, proprietary vaults, credentials, API keys, or generated notes containing sensitive material. Use minimal synthetic fixtures for tests.

## Reporting

Report security-sensitive issues privately to the repository owner. For normal bugs, use GitHub issues with a minimal reproducible example.
