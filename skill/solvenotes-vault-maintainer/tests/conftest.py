"""Configure deterministic, standalone tests for the vault maintainer."""

from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_TEST_VAULT = SKILL_ROOT / "fixtures" / "solvenotes-mini-vault"


def configure_test_vault(environ: MutableMapping[str, str]) -> Path:
    """Use an explicit vault override or the bundled non-sensitive fixture."""

    configured = environ.get("SOLVENOTES_VAULT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    environ["SOLVENOTES_VAULT_ROOT"] = str(BUNDLED_TEST_VAULT)
    return BUNDLED_TEST_VAULT


TEST_VAULT = configure_test_vault(os.environ)
ALGORITHM_SKILL_ROOT = SKILL_ROOT.parent / "algorithm-job-notes-for-obsidian"
if not ALGORITHM_SKILL_ROOT.is_dir():
    installed_parent = SKILL_ROOT.parent
    ALGORITHM_SKILL_ROOT = installed_parent / "algorithm-job-notes-for-obsidian"
if ALGORITHM_SKILL_ROOT.is_dir():
    sys.path.insert(0, str(ALGORITHM_SKILL_ROOT / "scripts"))
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

for import_root in (SKILL_ROOT, SKILL_ROOT / "scripts"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))


@pytest.fixture(scope="session", autouse=True)
def _run_from_skill_root():
    previous = Path.cwd()
    os.chdir(SKILL_ROOT)
    try:
        yield
    finally:
        os.chdir(previous)
