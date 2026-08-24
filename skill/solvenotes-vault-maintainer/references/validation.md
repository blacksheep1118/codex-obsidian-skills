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
bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh vault-runtime
bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh github-ready
```

The requirements for these profiles have one machine-readable source:
`references/validation-profiles.json`. `doctor.py --profile PROFILE --strict`
reads that contract, and every expensive root or vault entry point runs the
corresponding preflight first.

The tool gates validate the Skill implementation; the vault gates validate
external learning content without rerunning the Skill test suite. Compatibility
aliases `quick` and `full` map to `vault-quick` and `vault-full`. `vault-full`
runs source-manifest, link, frontmatter, formula, table, heading,
example, language, algorithm-job, and C++ checks; `github-ready` adds hygiene,
large-file, public-readiness, and Git-status checks.

`vault-runtime` is a separate, explicit gate for reviewed dependency-backed
Python examples. It uses the interpreter selected by
`SOLVENOTES_PYTHON_BIN`, requires the pinned optional environment from the
algorithm skill's `requirements-runtime.txt`, and executes only fences with an
exact `python-e2e` marker. Its dependencies do not belong in
`requirements-dev.txt` or ordinary public CI. Missing dependencies, Java below
17, absent marked coverage, timeout, excessive output, and nonzero exit are
failures rather than skips. See the algorithm skill's
`references/python-runtime-validation.md` for the marker and setup contract.

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
compiled. Ordinary Python fences are parsed for syntax; unknown code blocks
are never executed. The separate `vault-runtime` command executes only exact,
reviewed `python-e2e` blocks.

## Source and template boundaries

`source_manifest.md` remains versioned beside the course or topic it proves,
but the formal statistics and learning views exclude it. Templates are kept
under `.obsidian/templates/` with `note_type: template`; they are writing
scaffolds, not course notes. Generated reports and intermediate inventories go
to one task-specific `RUN_TMP` outside the workspace. Point `TMPDIR` at it when
invoking helpers that use system temporary directories, and remove that exact
directory after the final checks.

## Clean export

Only when the user requests an export and local workspace guidance permits
package mode, create the package outside the vault:

```bash
python3 skill/solvenotes-vault-maintainer/scripts/package_vault.py \
  --root "$SOLVENOTES_VAULT_ROOT" \
  --output /tmp/solvenotes-notes-clean.zip \
  --manifest-output /tmp/solvenotes-notes-PACKAGE-MANIFEST.json

python3 skill/solvenotes-vault-maintainer/scripts/verify_vault_package.py \
  /tmp/solvenotes-notes-clean.zip \
  --sidecar /tmp/solvenotes-notes-PACKAGE-MANIFEST.json
```

The package excludes `.git`, caches, `__MACOSX`, `.DS_Store`, `._*`, compiled
files, `.obsidian/workspace.json`, `.obsidian/graph.json`, and prior exports.
The verifier rejects duplicate, absolute, traversing, symlink, cache, and local
workspace entries, then recomputes every recorded size and digest. A successful
package command alone is not delivery evidence; the verifier must also pass.
