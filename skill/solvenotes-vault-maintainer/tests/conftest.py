"""Test the external-vault maintenance package against a real or fixture vault."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VAULT = SKILL_ROOT.parents[2] / "notes"
os.environ.setdefault("SOLVENOTES_VAULT_ROOT", str(DEFAULT_VAULT))
ALGORITHM_SKILL_ROOT = SKILL_ROOT.parent / "algorithm-job-notes-for-obsidian"
if not ALGORITHM_SKILL_ROOT.is_dir():
    installed_parent = SKILL_ROOT.parent
    ALGORITHM_SKILL_ROOT = installed_parent / "algorithm-job-notes-for-obsidian"
if ALGORITHM_SKILL_ROOT.is_dir():
    sys.path.insert(0, str(ALGORITHM_SKILL_ROOT / "scripts"))
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
