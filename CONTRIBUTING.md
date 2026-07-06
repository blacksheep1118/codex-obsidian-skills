# Contributing

This repository contains installable Codex skills under `skill/`. Keep each skill directory self-contained so it can be copied directly into `$CODEX_HOME/skills/<skill-name>`.

## Skill Structure

- The directory name must match `SKILL.md` frontmatter `name`.
- Each skill keeps its own `SKILL.md`, `agents/openai.yaml`, scripts, references, README, and LICENSE.
- Shared scripts may have a canonical root copy, but each skill must keep a local copy when the script is needed after standalone installation.
- Do not move roadmap or planning notes into README files. Report proposed next steps outside the repo docs unless they are accepted product behavior.

## Validation

Run the fast repository test entry point from the repository root while iterating:

```bash
python3 -m pytest
```

This only collects the root `tests/` directory. Run the full local validation pass before opening a PR; it runs each skill's tests and validation scripts in that skill's own working directory:

```bash
python3 scripts/validate_all.py
```

For focused checks:

```bash
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

## Release Process

1. Update `CHANGELOG.md`.
2. Run `python3 -m pytest`.
3. Run `python3 scripts/validate_all.py`.
4. Create a clean zip with `python3 scripts/package_release.py --out /tmp/skills.zip`.
5. Commit the change.
6. Create a semantic version tag such as `v0.1.0`.
7. Push `main` and the tag.

## License And Sources

The repository is MIT licensed. Each installable skill includes a copy of the license so a copied skill folder remains clear about its terms. See `docs/license-policy.md` for details.
