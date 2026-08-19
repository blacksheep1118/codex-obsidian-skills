from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "cv",
    "nlp_llm",
    "recommendation",
    "search",
    "speech",
    "robotics",
    "automotive",
    "embodied_ai",
    "ai_infra",
}


def test_canonical_direction_table_is_closed():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    table = text.split("## Canonical direction set", 1)[1].split(
        "## Evidence And Assumption Gate", 1
    )[0]
    ids = {
        line.split("|", 2)[1].strip().strip("`")
        for line in table.splitlines()
        if line.startswith("| `")
    }
    assert ids == EXPECTED
    assert len(ids) == 9


def test_skill_forbids_new_top_level_routes():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "do not create a tenth" in text.lower()
    assert "Delete obsolete route files" in text
    assert "official recruitment pages" in text
