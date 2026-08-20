#!/usr/bin/env python3
"""Update installed skills from this repository without creating backups."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from install_skill import (
    UnsafeDestinationError,
    UnsafeSourceError,
    configure_output_encoding,
    copy_skill,
    default_destination,
    discover_skills,
    ensure_safe_destination_root,
    ensure_safe_destination_tree,
    selected_skills,
    self_check_selected,
    self_check_sources,
    SELF_CHECK_LEVELS,
)


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="Update installed Codex skills from this repository.")
    parser.add_argument("--skill", action="append", default=[], help="Skill name to update. May be repeated.")
    parser.add_argument("--all", action="store_true", help="Update every skill under skill/. This is the default.")
    parser.add_argument(
        "--destination",
        type=Path,
        help="Destination skills directory. Defaults to CODEX_HOME/skills or the user home .codex/skills directory.",
    )
    parser.add_argument("--codex-home", type=Path, help="Codex home used to derive the destination.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    parser.add_argument("--prune", action="store_true", help="Remove files in the installed skill that no longer exist here.")
    parser.add_argument("--self-check", action="store_true", help="Validate the installed Skill after updating (defaults to smoke level).")
    parser.add_argument(
        "--self-check-level",
        choices=SELF_CHECK_LEVELS,
        help="Self-check depth: metadata, runtime, smoke, or full. Implies --self-check.",
    )
    parser.add_argument(
        "--no-deps",
        action="store_true",
        help="Update only explicitly requested Skills; self-check reports missing required dependencies.",
    )
    args = parser.parse_args()

    if args.destination and args.codex_home:
        parser.error("--destination and --codex-home are mutually exclusive")
    if args.self_check_level:
        args.self_check = True

    destination_root = args.destination.expanduser() if args.destination else default_destination(args.codex_home)
    try:
        all_skills = discover_skills()
        skills = selected_skills(all_skills, args.skill, args.all, no_deps=args.no_deps)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.self_check and self_check_sources(skills):
        return 1

    try:
        ensure_safe_destination_root(destination_root)
        for name in skills:
            ensure_safe_destination_tree(destination_root / name)
    except (UnsafeDestinationError, UnsafeSourceError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    missing = [name for name in skills if not (destination_root / name).exists()]
    if missing and not args.dry_run:
        print(f"ERROR: cannot update missing installed skills: {', '.join(missing)}", file=sys.stderr)
        print("Run scripts/install_skill.py first, or pass --dry-run to inspect actions.", file=sys.stderr)
        return 1
    if missing and args.self_check:
        return self_check_selected(destination_root, skills, level=args.self_check_level or "smoke")

    try:
        for name, source in skills.items():
            copy_skill(source, destination_root / name, dry_run=args.dry_run, prune=args.prune)
    except (UnsafeDestinationError, UnsafeSourceError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.self_check:
        return self_check_selected(destination_root, skills, level=args.self_check_level or "smoke")

    print(f"updated_skills {len(skills)} destination={destination_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
