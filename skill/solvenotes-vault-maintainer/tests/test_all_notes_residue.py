import pytest
from check_all_notes import residue_markers


@pytest.mark.parametrize(
    "line",
    [
        "模板 `.format` 占位符不能证明输入字段已送入请求；源码注释中的占位符同样只是描述。",
        "README 明确称训练/评估脚本待补；仓库该提交同时包含 train.py。",
        "作者仓库 README 将 Release training codes 列在 TODO 中。",
        "异常多的已发现页面可提示可疑站点，再由人工确认并用 URL filter 排除。",
        "The source marks the remaining release item TBD in its status note.",
    ],
)
def test_source_descriptions_are_not_open_residue(line: str) -> None:
    assert residue_markers(line) == []


def test_actual_placeholders_and_task_markers_are_reported_once_per_line() -> None:
    text = (
        "TODO补公式\n"
        "- [ ] FIXME: add an example\n"
        "TBD\n"
        "在此填写实验边界\n"
        "待补充证明\n"
        "<待填写>\n"
    )

    assert residue_markers(text) == [
        (1, "open task marker"),
        (2, "open task marker"),
        (3, "open task marker"),
        (4, "在此填写"),
        (5, "待补充"),
        (6, "<待填写>"),
    ]


def test_code_examples_are_excluded_but_prose_task_is_reported() -> None:
    text = (
        "Code `TODO: not a placeholder` stays code.\n"
        "```text\n"
        "FIXME: fenced code stays code\n"
        "```\n"
        "TODO\n"
    )

    assert residue_markers(text) == [(5, "open task marker")]


def test_frontmatter_is_not_scanned_as_note_prose() -> None:
    text = "---\nnote_type: course_note\nstatus: TODO\n---\n\n正文正常。\n"

    assert residue_markers(text) == []


def test_unicode_replacement_character_remains_residue() -> None:
    assert residue_markers("corrupted text: �") == [(1, "�")]
    assert residue_markers("```text\n�\n```\n") == []
