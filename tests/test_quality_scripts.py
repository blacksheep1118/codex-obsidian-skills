from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts.shared.markdown_links import MARKDOWN_IMAGE_RE, MARKDOWN_LINK_RE


ROOT = Path(__file__).resolve().parents[1]


def run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


ROOT_SHAPE_CONSUMERS = (
    "skill/obsidian-vault-organizer/scripts/check_vault_quality.py",
    "skill/obsidian-vault-organizer/scripts/link_inventory.py",
    "skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py",
)
ROOT_SHAPE_REASON = "root must be an existing directory without symlink components"


def write_clean_course(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "00_课程总览.md").write_text(
        "# 总览\n\n[[知识点详细版_含公式]]\n[[知识点精简复习版_含公式]]\n",
        encoding="utf-8",
    )
    (root / "知识点详细版_含公式.md").write_text("# 详细\n\n稳定内容。\n", encoding="utf-8")
    (root / "知识点精简复习版_含公式.md").write_text("# 精简\n\n稳定内容。\n", encoding="utf-8")


def make_quality_root_shape(tmp_path: Path, kind: str) -> tuple[Path, Path]:
    regular = tmp_path / "regular-root"
    write_clean_course(regular)
    if kind == "regular-dir":
        return regular, regular
    if kind == "missing":
        return tmp_path / "missing-root", regular

    regular_file = tmp_path / "root.md"
    regular_file.write_text("# File\n", encoding="utf-8")
    if kind == "file":
        return regular_file, regular
    alias = tmp_path / kind
    if kind == "symlink-file":
        alias.symlink_to(regular_file)
    elif kind == "leaf-same-inode":
        alias.symlink_to(regular, target_is_directory=True)
    elif kind == "ancestor-same-inode":
        real_parent = tmp_path / "real-parent"
        nested = real_parent / "nested"
        write_clean_course(nested)
        alias.symlink_to(real_parent, target_is_directory=True)
        return alias / "nested", nested
    elif kind == "external-leaf":
        boundary = tmp_path / "empty-boundary"
        boundary.mkdir()
        alias = boundary / "external-alias"
        alias.symlink_to(regular, target_is_directory=True)
    elif kind == "broken-leaf":
        alias.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    elif kind == "broken-ancestor":
        alias.symlink_to(tmp_path / "missing-parent", target_is_directory=True)
        return alias / "nested", regular
    else:
        raise AssertionError(kind)
    return alias, regular


def regular_tree_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


@pytest.mark.parametrize(
    "entrypoint",
    ROOT_SHAPE_CONSUMERS,
    ids=("vault-quality", "link-inventory", "course-notes"),
)
@pytest.mark.parametrize(
    "kind",
    (
        "regular-dir",
        "missing",
        "file",
        "symlink-file",
        "leaf-same-inode",
        "ancestor-same-inode",
        "external-leaf",
        "broken-leaf",
        "broken-ancestor",
    ),
)
def test_quality_cli_consumers_share_lexical_root_shape_gate(
    tmp_path: Path,
    entrypoint: str,
    kind: str,
) -> None:
    root, _target = make_quality_root_shape(tmp_path, kind)
    before = regular_tree_snapshot(tmp_path)

    result = run_command(entrypoint, str(root))

    if kind == "regular-dir":
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stderr == ""
    else:
        assert result.returncode == 2
        assert result.stdout == ""
        assert result.stderr == f"ERROR: {root}: {ROOT_SHAPE_REASON}\n"
        assert "Traceback" not in result.stderr
    assert regular_tree_snapshot(tmp_path) == before


def test_vault_quality_accepts_clean_fixture():
    result = run_command("skill/obsidian-vault-organizer/scripts/check_vault_quality.py", "fixtures/vault-clean")

    assert result.returncode == 0
    assert "vault_quality_issues 0" in result.stdout


def test_vault_quality_reports_common_issues(tmp_path: Path):
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "fixtures" / "vault-quality-issues", vault)
    (vault / "conflict.md").write_text("# Conflict\n\n<<<<<<< HEAD\nold\n=======\nnew\n>>>>>>> branch\n", encoding="utf-8")

    result = run_command("skill/obsidian-vault-organizer/scripts/check_vault_quality.py", str(vault))

    assert result.returncode == 1
    assert "CONFLICT_MARKER" in result.stdout
    assert "EMPTY_FILE" in result.stdout
    assert "UNBALANCED_MATH" in result.stdout
    assert "TEMPLATE_RESIDUE" in result.stdout


def test_course_note_checker_accepts_sample_notes():
    result = run_command("skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py", "skill/ppt-to-md-for-obsidian/examples/sample-course/notes")

    assert result.returncode == 0
    assert "course_note_issues 0" in result.stdout


def test_root_link_checker_cli_accepts_commonmark_nested_and_encoded_destinations(
    tmp_path: Path,
):
    vault = tmp_path / "vault"
    (vault / "folder").mkdir(parents=True)
    for target in ("foo(and(bar)).md", "encoded(1).md", "folder/My Note.md"):
        (vault / target).write_text("# Target\n", encoding="utf-8")
    (vault / "index.md").write_text(
        '[Nested](foo(and(bar)).md "title")\n'
        "[Encoded](encoded%281%29.md#part)\n"
        "[Spaced](<folder/My Note.md>)\n"
        "![Image](missing(and(bar)).png)\n",
        encoding="utf-8",
    )

    result = run_command("scripts/check_obsidian_links.py", str(vault))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "checked_links 3" in result.stdout
    assert "broken_links 0" in result.stdout


def test_shared_markdown_link_parser_depth_images_and_windows_space_boundaries():
    depth_32 = "target.md"
    for index in range(32):
        depth_32 = f"level{index}({depth_32})"
    depth_33 = f"overflow({depth_32})"
    text = (
        f'[Deep]({depth_32} "title")\n'
        r"[Windows](<C:\Course Notes\topic(1).md>)" "\n"
        "![Image](plot(and(detail)).png)\n"
        f"[Too deep]({depth_33})\n"
        "[Unclosed](target(and(child))\n"
    )

    assert MARKDOWN_LINK_RE.findall(text) == [
        depth_32,
        r"<C:\Course Notes\topic(1).md>",
    ]
    assert MARKDOWN_IMAGE_RE.findall(text) == ["plot(and(detail)).png"]


def test_shared_markdown_link_parser_rejects_backslash_space_like_commonmark() -> None:
    source = r"[Backslash space](foo\ bar.md)"
    markdown_it = pytest.importorskip("markdown_it")

    assert "<a " not in markdown_it.MarkdownIt("commonmark").render(source)
    assert MARKDOWN_LINK_RE.findall(source) == []


def test_shared_markdown_link_parser_keeps_commonmark_punctuation_escapes() -> None:
    source = r"[Escaped punctuation](foo\(bar\).md)"

    assert MARKDOWN_LINK_RE.findall(source) == [r"foo\(bar\).md"]


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("[soft\nlabel](foo.md)", ["foo.md"]),
        ("[soft\r\nlabel](foo.md)", ["foo.md"]),
        ("[soft\rlabel](foo.md)", ["foo.md"]),
        ("[blank\n\nlabel](foo.md)", []),
        ("[blank\r\n\r\nlabel](foo.md)", []),
        ("[blank\r\rlabel](foo.md)", []),
        ('[quoted]( "title")', ['"title"']),
        ('[empty angle](<> "title")', ["<>"]),
        (r'[escaped title](foo.md "a \" quote")', ["foo.md"]),
        ("[one newline](foo.md\n'title')", ["foo.md"]),
        ("[blank title](foo.md\n\n'title')", []),
        ('[blank CR in title](foo.md "a\r\rb")', []),
        ('[soft CRLF in title](foo.md "a\r\nb")', ["foo.md"]),
        ("[bad delimiter](foo.md title)", []),
    ),
)
def test_shared_markdown_link_parser_matches_commonmark_boundaries(
    source: str,
    expected: list[str],
) -> None:
    markdown_it = pytest.importorskip("markdown_it")
    oracle_links = [
        child.attrGet("href") or ""
        for token in markdown_it.MarkdownIt("commonmark").parse(source)
        for child in (token.children or [])
        if child.type == "link_open"
    ]

    assert bool(oracle_links) is bool(expected)
    assert MARKDOWN_LINK_RE.findall(source) == expected


def test_shared_markdown_link_parser_reports_exact_source_spans() -> None:
    source = "prefix [soft\nlabel](<folder/My Note.md> 'title') suffix"

    matches = list(MARKDOWN_LINK_RE.finditer(source))

    assert len(matches) == 1
    assert matches[0].group(0) == "[soft\nlabel](<folder/My Note.md> 'title')"
    assert source[matches[0].start() : matches[0].end()] == matches[0].group(0)
    assert matches[0].group(1) == "<folder/My Note.md>"


def test_course_note_checker_requires_review_pages(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "00_课程总览.md").write_text("# 课程总览\n\n- [[01_主题]]\n", encoding="utf-8")
    (notes / "01_主题.md").write_text("# 主题\n\n正文。\n", encoding="utf-8")

    result = run_command("skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py", str(notes))

    assert result.returncode == 1
    assert "MISSING_REVIEW_PAGE" in result.stdout
    assert "MISSING_REVIEW_LINK" in result.stdout


def test_course_note_checker_accepts_course_prefixed_review_pages(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "00_游戏数值策划学习总览.md").write_text(
        "# 游戏数值策划学习总览\n\n"
        "- [[游戏数值策划知识点详细版_含公式]]\n"
        "- [[游戏数值策划知识点精简复习版_含公式]]\n",
        encoding="utf-8",
    )
    (notes / "01_主题.md").write_text("# 主题\n\n正文。\n", encoding="utf-8")
    (notes / "游戏数值策划知识点详细版_含公式.md").write_text("# 详细\n\n核心机制。\n", encoding="utf-8")
    (notes / "游戏数值策划知识点精简复习版_含公式.md").write_text("# 精简\n\n核心公式。\n", encoding="utf-8")

    result = run_command("skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py", str(notes))

    assert result.returncode == 0
    assert "course_note_issues 0" in result.stdout


def test_course_note_checker_strict_depth_reports_thin_generic_notes(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "00_课程总览.md").write_text(
        "# 课程总览\n\n- [[知识点详细版_含公式]]\n- [[知识点精简复习版_含公式]]\n",
        encoding="utf-8",
    )
    (notes / "01_主题.md").write_text("# 主题\n\n正文太少。\n", encoding="utf-8")
    (notes / "知识点详细版_含公式.md").write_text("# 详细\n\n例题模板：先写定义再套公式。\n", encoding="utf-8")
    (notes / "知识点精简复习版_含公式.md").write_text("# 精简\n\n核心公式。\n", encoding="utf-8")

    result = run_command(
        "skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py",
        "--strict-depth",
        "--min-chapter-lines",
        "5",
        "--min-detailed-lines",
        "5",
        str(notes),
    )

    assert result.returncode == 1
    assert "THIN_CHAPTER_NOTE" in result.stdout
    assert "THIN_DETAILED_REVIEW" in result.stdout
    assert "GENERIC_TEMPLATE_RESIDUE" in result.stdout


def test_course_note_checker_allows_single_exam_review_with_audit(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    exam_body = "\n".join(f"- 知识点 {index}：定义、公式、例题和易错点。" for index in range(1, 6))
    (notes / "00_机器学习课程总览.md").write_text(
        "# 机器学习课程总览\n\n- [[机器学习考试复习笔记]]\n",
        encoding="utf-8",
    )
    (notes / "机器学习考试复习笔记.md").write_text(f"# 机器学习考试复习笔记\n\n{exam_body}\n", encoding="utf-8")
    (notes / "99_内容覆盖审查.md").write_text("# 内容覆盖审查\n\n- 已核对来源。\n", encoding="utf-8")
    (notes / "source_manifest.md").write_text("# Source Manifest\n\n- source.pdf\n", encoding="utf-8")

    result = run_command(
        "skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py",
        "--strict-depth",
        "--allow-exam-review",
        "--require-coverage-audit",
        "--min-exam-review-lines",
        "5",
        str(notes),
    )

    assert result.returncode == 0
    assert "course_note_issues 0" in result.stdout
