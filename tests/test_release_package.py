from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )


def write_file(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_release_zip_excludes_repository_cache_build_and_macos_artifacts(tmp_path: Path):
    source = tmp_path / "source"
    output = tmp_path / "skills.zip"

    write_file(source / "README.md", "# Example\n")
    write_file(source / "skill" / "example" / "SKILL.md", "---\nname: example\n---\n")
    write_file(source / ".git" / "config")
    write_file(source / "__MACOSX" / "._README.md")
    write_file(source / "._README.md")
    write_file(source / ".DS_Store")
    write_file(source / ".pytest_cache" / "v" / "cache" / "nodeids")
    write_file(source / "pkg" / "__pycache__" / "module.cpython-311.pyc")
    write_file(source / "pkg" / "module.pyc")
    write_file(source / ".ruff_cache" / "content")
    write_file(source / "build" / "artifact.txt")
    write_file(source / "converted_pptx" / "deck.pptx")
    write_file(source / "nested" / ".DS_Store")
    write_file(source / "nested" / "._notes.md")
    write_file(source / "nested" / "build" / "artifact.txt")
    write_file(source / "nested" / "converted_pptx" / "deck.pptx")

    result = run_script("scripts/package_release.py", "--source", str(source), "--out", str(output))

    assert "wrote" in result.stdout
    with ZipFile(output) as archive:
        names = archive.namelist()

    assert "README.md" in names
    assert "skill/example/SKILL.md" in names
    assert not any(".git/" in name for name in names)
    assert not any("__MACOSX/" in name for name in names)
    assert not any("/__pycache__/" in name or name.startswith("__pycache__/") for name in names)
    assert not any(".pytest_cache/" in name for name in names)
    assert not any(".ruff_cache/" in name for name in names)
    assert not any("/build/" in name or name.startswith("build/") for name in names)
    assert not any("/converted_pptx/" in name or name.startswith("converted_pptx/") for name in names)
    assert not any(Path(name).name == ".DS_Store" for name in names)
    assert not any(Path(name).name.startswith("._") for name in names)
    assert not any(name.endswith(".pyc") for name in names)


def test_root_pytest_collects_only_root_tests():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=True,
    )

    collected = result.stdout.replace("\\", "/")
    assert "tests/test_release_package.py::test_root_pytest_collects_only_root_tests" in collected
    assert "skill/" not in collected
