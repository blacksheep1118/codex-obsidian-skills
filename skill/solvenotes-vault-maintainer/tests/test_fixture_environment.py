"""Keep the public test vault paired with its synthetic evidence registry."""

from conftest import BUNDLED_TEST_VAULT, configure_test_vault


def test_default_fixture_discards_private_manifest_override(tmp_path):
    env = {"SOLVENOTES_MANIFEST_ROOT": str(tmp_path / "private")}
    assert configure_test_vault(env) == BUNDLED_TEST_VAULT
    assert env["SOLVENOTES_MANIFEST_ROOT"] == str(BUNDLED_TEST_VAULT.parent / "vault_sources")


def test_explicit_bundled_fixture_also_discards_private_manifest_override(tmp_path):
    env = {
        "SOLVENOTES_VAULT_ROOT": str(BUNDLED_TEST_VAULT),
        "SOLVENOTES_MANIFEST_ROOT": str(tmp_path / "private"),
    }
    configure_test_vault(env)
    assert env["SOLVENOTES_MANIFEST_ROOT"] == str(BUNDLED_TEST_VAULT.parent / "vault_sources")


def test_custom_fixture_uses_its_own_default_sibling(tmp_path):
    env = {"SOLVENOTES_VAULT_ROOT": str(tmp_path / "notes")}
    configure_test_vault(env)
    assert env["SOLVENOTES_MANIFEST_ROOT"] == str(tmp_path / "vault_sources")


def test_explicit_custom_fixture_pair_is_preserved(tmp_path):
    env = {
        "SOLVENOTES_VAULT_ROOT": str(tmp_path / "notes"),
        "SOLVENOTES_MANIFEST_ROOT": str(tmp_path / "custom-evidence"),
    }
    expected = dict(env)
    configure_test_vault(env)
    assert env == expected
