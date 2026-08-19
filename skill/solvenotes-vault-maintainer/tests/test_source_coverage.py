import sys
from pathlib import Path

import check_source_coverage as csc
import pytest
from check_source_coverage import coverage_contract_issues, issue_code, manifest_issues


def frontmatter(note_type: str) -> str:
    return f'---\nnote_type: "{note_type}"\n---\n\n# Test\n'


def sourced_frontmatter(note_type: str, sources: list[str]) -> str:
    items = "\n".join(f'  - "{source}"' for source in sources)
    return f'---\nnote_type: "{note_type}"\nsource_files:\n{items}\n---\n\n# Test\n'


def markdown_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.md"))


def contract_index(root: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for path in root.rglob("*.md"):
        relative = path.relative_to(root).as_posix()
        no_suffix = relative.removesuffix(".md")
        for key in (relative, no_suffix, path.name, path.stem):
            index.setdefault(key, []).append(path)
    return index


def write_manifest(
    root: Path,
    *,
    source: str = "course/slides/shared.pdf",
    kind: str = "`.pdf`",
    count: str = "2",
    method: str = "pdftotext-page",
    links: str = "[[course/note]]",
    status: str = "已映射：文本抽取与目标映射已记录；不构成逐页语义覆盖证明",
    example_status: str = "已复核：源资料未提供独立例题；生成补充题保持标记",
    limitations: str = "未见文本层空白页；图片与公式对象未做视觉/OCR 核验",
    checked: str = "2026-08-07",
    note_type: str = "source_manifest",
    extra_text: str = "",
) -> Path:
    course = root / "course"
    course.mkdir()
    (course / "note.md").write_text(frontmatter("course_note"), encoding="utf-8")
    manifest = course / "source_manifest.md"
    manifest.write_text(
        frontmatter(note_type)
        + "\n| 源文件 | 类型 | 页/slide/记录数 | 抽取方式 | 对应笔记 | 覆盖状态 | 例题状态 | 限制说明 | 最后检查日期 |\n"
        + "|---|---|---:|---|---|---|---|---|---|\n"
        + f"| `{source}` | {kind} | {count} | {method} | {links} | {status} | {example_status} | {limitations} | {checked} |\n"
        + extra_text,
        encoding="utf-8",
    )
    return manifest


def test_source_manifest_is_authoritative_without_audit_page(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path)

    assert coverage_contract_issues(tmp_path, markdown_files(tmp_path)) == []
    assert manifest_issues(tmp_path, manifest, contract_index(tmp_path)) == ([], 1)


def test_nested_formal_manifest_uses_the_same_contract(tmp_path: Path) -> None:
    nested = tmp_path / "course" / "topic"
    nested.mkdir(parents=True)
    (nested / "note.md").write_text(frontmatter("paper_note"), encoding="utf-8")
    manifest = nested / "source_manifest.md"
    manifest.write_text(
        frontmatter("source_manifest")
        + "\n| 源文件 | 类型 | 页/slide/记录数 | 抽取方式 | 对应笔记 | 覆盖状态 | 例题状态 | 限制说明 | 最后检查日期 |\n"
        + "|---|---|---:|---|---|---|---|---|---|\n"
        + "| `course/topic/paper.pdf` | `.pdf` | 3 | pdftotext-page | [[course/topic/note]] | "
        + "已映射：文本抽取与目标映射已记录；不构成逐页语义覆盖证明 | "
        + "已复核：源资料未提供独立例题 | 未见文本层空白页；图片未做视觉/OCR 核验 | 2026-08-07 |\n",
        encoding="utf-8",
    )

    assert coverage_contract_issues(tmp_path, markdown_files(tmp_path)) == []
    assert manifest_issues(tmp_path, manifest, contract_index(tmp_path)) == ([], 1)


def test_nested_web_source_manifest_is_formal_without_fake_page_counts(tmp_path: Path) -> None:
    topic = tmp_path / "course" / "web-topic"
    topic.mkdir(parents=True)
    manifest = topic / "source_manifest.md"
    manifest.write_text(
        frontmatter("source_manifest")
        + "\n| 来源 | URL | 类型 | 访问状态 | 用途 |\n"
        + "|---|---|---|---|---|\n"
        + "| Official paper | https://example.org/paper.pdf | paper PDF | 可访问 | 支撑专题阅读 |\n",
        encoding="utf-8",
    )

    assert coverage_contract_issues(tmp_path, markdown_files(tmp_path)) == []
    assert manifest_issues(tmp_path, manifest, contract_index(tmp_path)) == ([], 0)


def test_main_does_not_scan_symlinked_manifest_neighbor(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    course = tmp_path / "course"
    course.mkdir()
    manifest = course / "source_manifest.md"
    manifest.write_text("# Local manifest\n", encoding="utf-8")
    outside = tmp_path / "outside-note.md"
    outside.write_text(
        "- 来源：`outside.pdf`；页/slide：1；主题：outside\n"
        "- 来源：`outside.pdf`；页/slide：1；主题：outside\n",
        encoding="utf-8",
    )
    linked = course / "linked-note.md"
    linked.symlink_to(outside)
    original_read_text = csc.read_text

    def reject_external_neighbor(path: Path) -> str:
        if path == linked:
            raise AssertionError("external symlink neighbor was read")
        return original_read_text(path)

    monkeypatch.setattr(csc, "ROOT", tmp_path)
    monkeypatch.setattr(csc, "build_note_index", lambda: {})
    monkeypatch.setattr(csc, "formal_source_manifests", lambda: [manifest])
    monkeypatch.setattr(csc, "markdown_files", lambda: [manifest])
    monkeypatch.setattr(csc, "coverage_contract_issues", lambda *_args: [])
    monkeypatch.setattr(csc, "manifest_issues", lambda *_args: ([], 0))
    monkeypatch.setattr(csc, "read_text", reject_external_neighbor)
    monkeypatch.setattr(sys, "argv", ["check_source_coverage.py", "--json"])

    assert csc.main() == 0
    assert '"coverage_issues": 0' in capsys.readouterr().out


def test_nonempty_source_files_require_an_applicable_manifest(tmp_path: Path) -> None:
    note = tmp_path / "course" / "note.md"
    note.parent.mkdir()
    note.write_text(sourced_frontmatter("course_note", ["course/lecture.pdf"]), encoding="utf-8")

    assert coverage_contract_issues(tmp_path, markdown_files(tmp_path)) == [
        "course/note.md: non-empty source_files has no applicable formal source_manifest"
    ]


def test_nested_manifest_covers_nested_note_before_ancestor(tmp_path: Path) -> None:
    course = tmp_path / "course"
    topic = course / "topic"
    topic.mkdir(parents=True)
    (topic / "note.md").write_text(
        sourced_frontmatter("paper_topic_note", ["course/topic/paper.pdf"]), encoding="utf-8"
    )
    (course / "source_manifest.md").write_text(frontmatter("source_manifest"), encoding="utf-8")
    (topic / "source_manifest.md").write_text(
        frontmatter("source_manifest")
        + "\n| 源文件 | 类型 | 页/slide/记录数 | 抽取方式 | 对应笔记 | 覆盖状态 | 例题状态 | 限制说明 | 最后检查日期 |\n"
        + "|---|---|---:|---|---|---|---|---|---|\n"
        + "| `course/topic/paper.pdf` | `.pdf` | 3 | pdftotext-page | [[course/topic/note]] | "
        + "已映射：文本抽取与目标映射已记录；不构成逐页语义覆盖证明 | "
        + "已复核：源资料未提供独立例题 | 未见文本层空白页；图片未做视觉/OCR 核验 | 2026-08-07 |\n",
        encoding="utf-8",
    )

    assert coverage_contract_issues(tmp_path, markdown_files(tmp_path)) == []


def test_source_files_entry_must_be_mapped_back_to_declaring_note(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path)
    (tmp_path / "course" / "other.md").write_text(
        sourced_frontmatter("course_note", ["course/slides/shared.pdf"]), encoding="utf-8"
    )

    issues = coverage_contract_issues(tmp_path, markdown_files(tmp_path))

    assert issues == [
        "course/other.md: source_files entry is not mapped back to its declaring note: course/slides/shared.pdf"
    ]
    assert manifest.exists()


def test_manifest_cannot_pass_with_only_a_header(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path)
    lines = manifest.read_text(encoding="utf-8").splitlines()
    manifest.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

    issues, rows = manifest_issues(tmp_path, manifest, contract_index(tmp_path))

    assert rows == 0
    assert any("must contain at least one source row" in issue for issue in issues)


def test_manifest_requires_formal_note_type(tmp_path: Path) -> None:
    write_manifest(tmp_path, note_type="course_note")

    assert coverage_contract_issues(tmp_path, markdown_files(tmp_path)) == [
        "course/source_manifest.md: manifest must declare note_type source_manifest"
    ]


def test_legacy_99_page_is_forbidden_even_without_legacy_note_type(tmp_path: Path) -> None:
    course = tmp_path / "course"
    course.mkdir()
    page = course / "99_内容覆盖审查.md"
    page.write_text(frontmatter("course_note"), encoding="utf-8")

    assert coverage_contract_issues(tmp_path, markdown_files(tmp_path)) == [
        "course/99_内容覆盖审查.md: forbidden legacy audit artifact 99_内容覆盖审查.md"
    ]


def test_template_cannot_reintroduce_legacy_99_page(tmp_path: Path) -> None:
    page = tmp_path / "模板" / "99_内容覆盖审查.md"
    page.parent.mkdir()
    page.write_text(frontmatter("template"), encoding="utf-8")

    assert coverage_contract_issues(tmp_path, markdown_files(tmp_path)) == [
        "模板/99_内容覆盖审查.md: forbidden legacy audit artifact 99_内容覆盖审查.md"
    ]


@pytest.mark.parametrize(
    "note_type",
    ["coverage_audit", "global_coverage_audit", "vault_audit", "audit_record", "source_manifest_history"],
)
def test_learning_notes_cannot_use_legacy_audit_types(tmp_path: Path, note_type: str) -> None:
    note = tmp_path / "course" / "history.md"
    note.parent.mkdir()
    note.write_text(frontmatter(note_type), encoding="utf-8")

    assert coverage_contract_issues(tmp_path, markdown_files(tmp_path)) == [
        f"course/history.md: learner note cannot use note_type {note_type}"
    ]


def test_tooling_and_test_fixtures_are_exempt_from_learner_contract(tmp_path: Path) -> None:
    for relative in ("AGENT.md", "agent/rule.md", "scripts/README.md", "tests/fixture.md"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(frontmatter("audit_record"), encoding="utf-8")

    assert coverage_contract_issues(tmp_path, markdown_files(tmp_path)) == []


def test_manifest_validates_full_source_identity_type_and_count(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path, source="shared.pdf", kind="`.pptx`", count="0")

    issues, _ = manifest_issues(tmp_path, manifest, contract_index(tmp_path))

    assert any("full root-relative identity" in issue for issue in issues)
    assert any("count must be a positive integer" in issue for issue in issues)


def test_manifest_rejects_unbackticked_source_identity(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path)
    text = manifest.read_text(encoding="utf-8").replace(
        "| `course/slides/shared.pdf` |", "| course/slides/shared.pdf |"
    )
    manifest.write_text(text, encoding="utf-8")

    issues, rows = manifest_issues(tmp_path, manifest, contract_index(tmp_path))

    assert rows == 1
    assert any("full root-relative identity" in issue for issue in issues)


def test_manifest_type_must_match_source_suffix(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path, kind="`.pptx`")

    issues, _ = manifest_issues(tmp_path, manifest, contract_index(tmp_path))

    assert any("file type does not match source suffix" in issue for issue in issues)


def test_manifest_link_must_exist(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path, links="[[course/missing]]")

    issues, _ = manifest_issues(tmp_path, manifest, contract_index(tmp_path))

    assert any("broken corresponding note" in issue for issue in issues)


def test_manifest_date_status_example_and_limitations_are_fail_closed(tmp_path: Path) -> None:
    manifest = write_manifest(
        tmp_path,
        status="完成",
        example_status="已检查",
        limitations="",
        checked="2026-02-30",
    )

    issues, _ = manifest_issues(tmp_path, manifest, contract_index(tmp_path))

    assert any("coverage status must use an explicit evidence state" in issue for issue in issues)
    assert any("example status" in issue for issue in issues)
    assert any("empty limitations field" in issue for issue in issues)
    assert any("real, non-future" in issue for issue in issues)


def test_aggregate_mapping_cannot_claim_per_unit_semantic_completion(tmp_path: Path) -> None:
    manifest = write_manifest(
        tmp_path,
        source="course/slides/legacy.ppt",
        kind="`.ppt`",
        method="legacy-ppt-record-text",
        status="已映射：可抽取文本已覆盖",
        limitations="聚合文本记录；图片和视觉题未 OCR",
    )

    issues, _ = manifest_issues(tmp_path, manifest, contract_index(tmp_path))

    assert any("aggregate/range mapping does not prove per-unit semantic coverage" in issue for issue in issues)


def test_manifest_must_be_self_contained_without_audit_page_reference(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path, extra_text="\n语义状态见同目录覆盖审查表。\n")

    issues, _ = manifest_issues(tmp_path, manifest, contract_index(tmp_path))

    assert any("stale audit-page reference" in issue for issue in issues)


def test_extractable_sources_require_explicit_text_and_visual_boundaries(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path, limitations="有少量抽取限制")

    issues, _ = manifest_issues(tmp_path, manifest, contract_index(tmp_path))

    assert any("limitations must explicitly state text-unit and OCR/visual boundaries" in issue for issue in issues)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("x: forbidden legacy audit artifact 99", "FORBIDDEN_AUDIT_ARTIFACT"),
        ("x: stale audit-page reference", "STALE_AUDIT_REFERENCE"),
        ("x: aggregate/range mapping does not prove per-unit semantic coverage", "AGGREGATE_NOT_SEMANTIC_PROOF"),
    ],
)
def test_issue_codes_are_stable(message: str, expected: str) -> None:
    assert issue_code(message) == expected
