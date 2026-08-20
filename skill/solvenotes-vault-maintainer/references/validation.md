# Solvenotes maintenance gate

This reference describes the external validation entry point. It is not a
learning note and must never be copied into the vault.

Set the vault explicitly:

```bash
export SOLVENOTES_VAULT_ROOT=/absolute/path/to/solvenotes/notes
```

Run from the Skills repository:

```bash
bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh tool-quick
bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh tool-full
bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh vault-quick
bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh vault-full
bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh github-ready
```

The tool gates validate the Skill implementation; the vault gates validate
external learning content without rerunning the Skill test suite. Compatibility
aliases `quick` and `full` map to `vault-quick` and `vault-full`. `vault-full`
runs source-manifest, link, frontmatter, formula, table, heading,
example, language, algorithm-job, and C++ checks; `github-ready` adds hygiene,
large-file, public-readiness, and Git-status checks.

The skill-local pytest suite is standalone and uses
`fixtures/solvenotes-mini-vault` by default, matching public GitHub CI. To run
the same tests against a real vault, opt in explicitly:

```bash
cd skill/solvenotes-vault-maintainer
python3 -m pytest -q
SOLVENOTES_VAULT_ROOT=/absolute/path/to/notes python3 -m pytest -q
```

The default must never probe a sibling `notes/` directory; otherwise a local
workspace can hide a missing public test fixture.

Only code blocks immediately preceded by `<!-- runnable: cpp17 -->` are
compiled. Python fences are parsed for syntax; unknown code blocks are never
executed by the gate.

## Source and template boundaries

`source_manifest.md` remains versioned beside the course or topic it proves,
but the formal statistics and learning views exclude it. Templates are kept
under `.obsidian/templates/` with `note_type: template`; they are writing
scaffolds, not course notes. Generated reports and intermediate inventories go
to `/tmp`.

## Clean export

Create a package outside the vault:

```bash
python3 skill/solvenotes-vault-maintainer/scripts/package_vault.py \
  --root "$SOLVENOTES_VAULT_ROOT" \
  --output /tmp/solvenotes-notes-clean.zip
```

The package excludes `.git`, caches, `__MACOSX`, `.DS_Store`, `._*`, compiled
files, `.obsidian/workspace.json`, `.obsidian/graph.json`, and prior exports.
Inspect the archive itself after creation; a successful package command is not
proof that a stale local workspace reference was absent unless the archive is
listed.
