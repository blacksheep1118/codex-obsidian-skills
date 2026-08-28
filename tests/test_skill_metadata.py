from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_openai_yaml_sync  # noqa: E402
import install_skill  # noqa: E402
from shared.skill_metadata import (  # noqa: E402
    MetadataValidationError,
    load_skill_frontmatter,
    validate_openai_yaml,
    validate_skill_metadata,
)


def write_skill(
    root: Path,
    *,
    frontmatter: str | None = None,
    openai_yaml: str | None = None,
) -> Path:
    skill = root / "demo-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        frontmatter
        or "---\nname: demo-skill\ndescription: Use when a demonstration skill is required.\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    agents = skill / "agents"
    agents.mkdir()
    (agents / "openai.yaml").write_text(
        openai_yaml
        or (
            "interface:\n"
            '  display_name: "Demo Skill"\n'
            '  short_description: "Run a structured demonstration workflow"\n'
            '  default_prompt: "Use $demo-skill to demonstrate this workflow."\n'
            "policy:\n"
            "  allow_implicit_invocation: true\n"
        ),
        encoding="utf-8",
    )
    return skill


def test_structured_skill_metadata_accepts_current_schema(tmp_path: Path):
    skill = write_skill(tmp_path)

    metadata = validate_skill_metadata(skill)

    assert metadata["name"] == "demo-skill"
    assert install_skill.self_check_skill(skill) == []


def test_every_installable_skill_carries_its_license():
    skill_directories = sorted(
        path for path in (ROOT / "skill").iterdir() if (path / "SKILL.md").is_file()
    )

    assert skill_directories
    assert [path.name for path in skill_directories if not (path / "LICENSE").is_file()] == []


@pytest.mark.parametrize(
    ("frontmatter", "message"),
    [
        ("---\n- demo-skill\n---\n", "must be a YAML mapping"),
        ("---\nname: 123\ndescription: Valid description\n---\n", "name must be a non-empty string"),
        (
            "---\nname: demo-skill\ndescription: Valid description\nunexpected: true\n---\n",
            "unexpected frontmatter keys",
        ),
        ("---\nname: Demo_Skill\ndescription: Valid description\n---\n", "lowercase letters"),
    ],
    ids=("not-mapping", "nonstring-name", "unexpected-key", "invalid-name"),
)
def test_frontmatter_schema_rejects_wrong_shapes(tmp_path: Path, frontmatter: str, message: str):
    skill = write_skill(tmp_path, frontmatter=frontmatter)

    with pytest.raises(MetadataValidationError, match=message):
        load_skill_frontmatter(skill / "SKILL.md", expected_name=skill.name)


def test_frontmatter_rejects_legacy_extra_keys(tmp_path: Path):
    skill = write_skill(
        tmp_path,
        frontmatter="---\nname: demo-skill\ndescription: Valid description\nlicense: MIT\n---\n",
    )

    with pytest.raises(MetadataValidationError, match="unexpected frontmatter keys: license"):
        load_skill_frontmatter(skill / "SKILL.md", expected_name=skill.name)


def test_frontmatter_rejects_duplicate_yaml_keys(tmp_path: Path):
    skill = write_skill(
        tmp_path,
        frontmatter=(
            "---\n"
            "name: demo-skill\n"
            "name: replaced-name\n"
            "description: Valid description\n"
            "---\n"
        ),
    )

    with pytest.raises(MetadataValidationError, match="duplicate YAML key 'name'"):
        load_skill_frontmatter(skill / "SKILL.md", expected_name=skill.name)


@pytest.mark.parametrize(
    ("short_description", "message"),
    [
        ('"too short"', "25-64"),
        (f'"{"x" * 65}"', "25-64"),
        ("42", "non-empty string"),
    ],
)
def test_openai_yaml_enforces_short_description_type_and_length(
    tmp_path: Path,
    short_description: str,
    message: str,
):
    skill = write_skill(
        tmp_path,
        openai_yaml=(
            "interface:\n"
            '  display_name: "Demo Skill"\n'
            f"  short_description: {short_description}\n"
            '  default_prompt: "Use $demo-skill to demonstrate this workflow."\n'
        ),
    )

    with pytest.raises(MetadataValidationError, match=message):
        validate_openai_yaml(skill / "agents" / "openai.yaml", skill.name)


@pytest.mark.parametrize(
    "prompt",
    [
        "Use $demo-skill-extra to run this workflow.",
        "Use $prefix-demo-skill to run this workflow.",
    ],
)
def test_openai_yaml_requires_exact_default_prompt_skill_token(tmp_path: Path, prompt: str):
    skill = write_skill(
        tmp_path,
        openai_yaml=(
            "interface:\n"
            '  display_name: "Demo Skill"\n'
            '  short_description: "Run a structured demonstration workflow"\n'
            f'  default_prompt: "{prompt}"\n'
        ),
    )

    with pytest.raises(MetadataValidationError, match="exact token"):
        validate_openai_yaml(skill / "agents" / "openai.yaml", skill.name)
    assert "exact token" in install_skill.self_check_skill(skill)[0]


def test_openai_yaml_requires_quoted_string_values(tmp_path: Path):
    skill = write_skill(
        tmp_path,
        openai_yaml=(
            "interface:\n"
            "  display_name: Demo Skill\n"
            '  short_description: "Run a structured demonstration workflow"\n'
            '  default_prompt: "Use $demo-skill to demonstrate this workflow."\n'
        ),
    )

    with pytest.raises(MetadataValidationError, match="string value 'Demo Skill' must be quoted"):
        validate_openai_yaml(skill / "agents" / "openai.yaml", skill.name)


def test_openai_yaml_accepts_package_local_regular_icons_and_hex_color(tmp_path: Path):
    skill = write_skill(
        tmp_path,
        openai_yaml=(
            "interface:\n"
            '  display_name: "Demo Skill"\n'
            '  short_description: "Run a structured demonstration workflow"\n'
            '  icon_small: "./assets/small.png"\n'
            '  icon_large: "./assets/large.svg"\n'
            '  brand_color: "#a1B2c3"\n'
            '  default_prompt: "Use $demo-skill to demonstrate this workflow."\n'
        ),
    )
    assets = skill / "assets"
    assets.mkdir()
    (assets / "small.png").write_bytes(b"png")
    (assets / "large.svg").write_text("<svg/>\n", encoding="utf-8")

    validate_openai_yaml(skill / "agents" / "openai.yaml", skill.name)


@pytest.mark.parametrize(
    ("icon", "message"),
    (
        ("/absolute/icon.svg", "relative path"),
        ("../outside.svg", "relative path"),
        ("C:\\\\icons\\\\icon.svg", "relative path"),
        ("./assets/missing.svg", "does not exist"),
    ),
)
def test_openai_yaml_rejects_invalid_icon_paths(
    tmp_path: Path,
    icon: str,
    message: str,
):
    skill = write_skill(
        tmp_path,
        openai_yaml=(
            "interface:\n"
            '  display_name: "Demo Skill"\n'
            '  short_description: "Run a structured demonstration workflow"\n'
            f'  icon_small: "{icon}"\n'
            '  default_prompt: "Use $demo-skill to demonstrate this workflow."\n'
        ),
    )

    with pytest.raises(MetadataValidationError, match=message):
        validate_openai_yaml(skill / "agents" / "openai.yaml", skill.name)


def test_openai_yaml_rejects_icon_symlink(tmp_path: Path):
    skill = write_skill(
        tmp_path,
        openai_yaml=(
            "interface:\n"
            '  display_name: "Demo Skill"\n'
            '  short_description: "Run a structured demonstration workflow"\n'
            '  icon_small: "./assets/icon.svg"\n'
            '  default_prompt: "Use $demo-skill to demonstrate this workflow."\n'
        ),
    )
    assets = skill / "assets"
    assets.mkdir()
    outside = tmp_path / "outside.svg"
    outside.write_text("<svg/>\n", encoding="utf-8")
    try:
        (assets / "icon.svg").symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(MetadataValidationError, match="must not contain symlinks"):
        validate_openai_yaml(skill / "agents" / "openai.yaml", skill.name)


@pytest.mark.parametrize("color", ("blue", "#12345", "#1234567", "123456", "#GG0000"))
def test_openai_yaml_rejects_non_rrggbb_brand_color(tmp_path: Path, color: str):
    skill = write_skill(
        tmp_path,
        openai_yaml=(
            "interface:\n"
            '  display_name: "Demo Skill"\n'
            '  short_description: "Run a structured demonstration workflow"\n'
            f'  brand_color: "{color}"\n'
            '  default_prompt: "Use $demo-skill to demonstrate this workflow."\n'
        ),
    )

    with pytest.raises(MetadataValidationError, match="#RRGGBB"):
        validate_openai_yaml(skill / "agents" / "openai.yaml", skill.name)


def test_openai_yaml_rejects_duplicate_nested_keys(tmp_path: Path):
    skill = write_skill(
        tmp_path,
        openai_yaml=(
            "interface:\n"
            '  display_name: "Demo Skill"\n'
            '  display_name: "Replacement"\n'
            '  short_description: "Run a structured demonstration workflow"\n'
            '  default_prompt: "Use $demo-skill to demonstrate this workflow."\n'
        ),
    )

    with pytest.raises(MetadataValidationError, match="duplicate YAML key 'display_name'"):
        validate_openai_yaml(skill / "agents" / "openai.yaml", skill.name)


def test_root_metadata_wrapper_and_installer_reject_scalar_interface(tmp_path: Path):
    skill = write_skill(tmp_path, openai_yaml='interface: "not a mapping"\n')

    with pytest.raises(SystemExit):
        check_openai_yaml_sync.validate_openai_yaml(skill, skill.name)
    assert "interface must be a mapping" in install_skill.self_check_skill(skill)[0]


@pytest.mark.parametrize(
    ("dependency_yaml", "message"),
    (
        ("  unexpected: []\n", "unexpected dependencies keys"),
        (
            "  tools:\n"
            "    - type: \"mcp\"\n"
            "      value: \"github\"\n"
            "      unexpected: \"x\"\n",
            "unexpected dependencies.tools\\[0\\] keys",
        ),
        (
            "  tools:\n"
            "    - type: \"mcp\"\n",
            "value must be a non-empty string",
        ),
        (
            "  tools:\n"
            "    - type: \"mcp\"\n"
            "      value: \"\"\n",
            "value must be a non-empty string",
        ),
    ),
)
def test_openai_yaml_enforces_dependency_schema(
    tmp_path: Path,
    dependency_yaml: str,
    message: str,
) -> None:
    skill = write_skill(
        tmp_path,
        openai_yaml=(
            "interface:\n"
            '  display_name: "Demo Skill"\n'
            '  short_description: "Run a structured demonstration workflow"\n'
            '  default_prompt: "Use $demo-skill to demonstrate this workflow."\n'
            "dependencies:\n"
            f"{dependency_yaml}"
        ),
    )

    with pytest.raises(MetadataValidationError, match=message):
        validate_openai_yaml(skill / "agents" / "openai.yaml", skill.name)
