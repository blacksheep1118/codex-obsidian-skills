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
    root = Path(configured).expanduser() if configured else BUNDLED_TEST_VAULT
    environ["SOLVENOTES_VAULT_ROOT"] = str(root)
    if root.resolve() == BUNDLED_TEST_VAULT.resolve():
        # A caller's private registry must never contaminate the public fixture.
        environ["SOLVENOTES_MANIFEST_ROOT"] = str(BUNDLED_TEST_VAULT.parent / "vault_sources")
    elif not environ.get("SOLVENOTES_MANIFEST_ROOT", "").strip():
        environ["SOLVENOTES_MANIFEST_ROOT"] = str(root.parent / "vault_sources")
    return root


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
