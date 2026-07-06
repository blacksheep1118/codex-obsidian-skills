#!/usr/bin/env python3
"""Compatibility wrapper for shared resource synchronization checks."""

from __future__ import annotations

import sys


from sync_shared_resources import sync


def main() -> int:
    mismatches = sync(write=False)
    if mismatches:
        print("shared_link_checker_validation failed", file=sys.stderr)
        for mismatch in mismatches:
            print(f"ERROR: {mismatch}", file=sys.stderr)
        return 1

    print("shared_link_checker_validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
