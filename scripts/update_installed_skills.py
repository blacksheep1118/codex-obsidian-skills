#!/usr/bin/env python3
"""Update installed skills from this repository without creating backups."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from install_skill import copy_skill, default_destination, discover_skills, selected_skills, self_check_selected


def main() -> int:
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
    parser.add_argument("--self-check", action="store_true", help="Validate installed skill metadata after updating.")
    args = parser.parse_args()

    if args.destination and args.codex_home:
        parser.error("--destination and --codex-home are mutually exclusive")

    destination_root = args.destination.expanduser() if args.destination else default_destination(args.codex_home)
    all_skills = discover_skills()
    skills = selected_skills(all_skills, args.skill, args.all)

    missing = [name for name in skills if not (destination_root / name).exists()]
    if missing and not args.dry_run:
        print(f"ERROR: cannot update missing installed skills: {', '.join(missing)}", file=sys.stderr)
        print("Run scripts/install_skill.py first, or pass --dry-run to inspect actions.", file=sys.stderr)
        return 1

    for name, source in skills.items():
        copy_skill(source, destination_root / name, dry_run=args.dry_run, prune=args.prune)

    if args.self_check and not args.dry_run:
        return self_check_selected(destination_root, skills)

    print(f"updated_skills {len(skills)} destination={destination_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
