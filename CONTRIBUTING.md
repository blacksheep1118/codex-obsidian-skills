# Contributing

This repository contains installable Codex skills under `skill/`. Keep each skill directory self-contained so it can be copied directly into `$CODEX_HOME/skills/<skill-name>`.

The project is distributed through GitHub. Do not hand-compress the repository or commit generated archives; CI should reject caches, macOS resource files, and generated outputs before they land.

Users install directly from a GitHub clone with `scripts/install_skill.py` or refresh with `scripts/update_installed_skills.py`. These scripts ignore cache directories, macOS resource files, Python bytecode, build outputs, distribution metadata, and generated `converted_pptx/` folders during copy/update, so do not add a manual zip step to the workflow.

## Skill Structure

- The directory name must match `SKILL.md` frontmatter `name`.
- Each skill keeps its own `SKILL.md`, `agents/openai.yaml`, scripts, references, README, and LICENSE.
- Shared scripts may have a canonical root copy, but each skill must keep a local copy when the script is needed after standalone installation.
- Do not move roadmap or planning notes into README files. Report proposed next steps outside the repo docs unless they are accepted product behavior.

## Validation

Run the fast repository test entry point from the repository root while iterating:

```bash
python3 scripts/check_repo_hygiene.py
python3 -m pytest -q
python3 scripts/validate_all.py --quick
```

The root `python -m pytest` entry point only collects the root `tests/` directory. `scripts/validate_all.py --quick` runs compile, repo hygiene, metadata sync, root tests, and skill validators without sample pipeline or deck smoke runs. For focused debugging, list stable step ids or run one skill:

```bash
python3 scripts/validate_all.py --quick
python3 scripts/validate_all.py --skill notes-to-scientific-ppt
python3 scripts/validate_all.py --list-steps
```

Full validation, including skill tests and sample smoke runs:

```bash
python3 scripts/validate_all.py
```

To validate one skill the same way CI isolates it, start from a fresh environment when possible and install only that skill's dev requirements:

```bash
cd skill/<skill-name>
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
python3 scripts/validate_skill.py
```

Use `python3 scripts/validate_skill_repo.py` instead for `skill/ppt-to-md-for-obsidian`.

For focused checks:

```bash
python3 scripts/check_repo_hygiene.py
python3 scripts/check_openai_yaml_sync.py
python3 scripts/sync_shared_resources.py --check
python3 scripts/install_skill.py --all --dry-run --self-check
```

When shared script templates change, update skill-local standalone copies with:

```bash
python3 scripts/sync_shared_resources.py --write
```

## Fixtures And Examples

- Keep fixtures small enough for CI.
- Use `fixtures/` for repository-level validation inputs.
- Use skill-local `examples/` when the example should travel with an installed skill.
- Avoid including private courseware, copyrighted decks, or user data.
- Do not commit caches, `.DS_Store`, AppleDouble `._*` files, `__pycache__`, `*.pyc`, `.pytest_cache`, `.ruff_cache`, `build/`, `dist/`, `converted_pptx/`, `*.egg-info/`, `tmp/`, `.tmp/`, or `test-output/`.

## GitHub Submission Process

1. Update `CHANGELOG.md`.
2. Run `python3 scripts/check_repo_hygiene.py`.
3. Run `python3 -m pytest -q`.
4. Run `python3 scripts/validate_all.py --quick`.
5. For each changed skill, install only that skill's `requirements-dev.txt`, then run its `python3 -m pytest -q` and validator.
6. Confirm `git status --short` shows only source and documentation changes.
7. Commit the change.
8. Create a semantic version tag such as `v0.1.0` only when needed.
9. Push the branch or `main` and any tag to GitHub.

## License And Sources

The repository is MIT licensed. Each installable skill includes a copy of the license so a copied skill folder remains clear about its terms. See `docs/license-policy.md` for details.
