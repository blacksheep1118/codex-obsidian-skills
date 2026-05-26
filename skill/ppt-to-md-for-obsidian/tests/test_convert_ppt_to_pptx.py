from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts.convert_ppt_to_pptx import find_soffice, soffice_candidates


def test_soffice_candidates_include_cross_platform_names():
    candidates = soffice_candidates("/custom/soffice")

    assert candidates[0] == "/custom/soffice"
    assert "soffice" in candidates
    assert "soffice.exe" in candidates
    assert "libreoffice" in candidates
    assert "libreoffice.exe" in candidates
    assert "/Applications/LibreOffice.app/Contents/MacOS/soffice" in candidates
    assert r"C:\Program Files\LibreOffice\program\soffice.exe" in candidates
    assert r"C:\Program Files (x86)\LibreOffice\program\soffice.exe" in candidates


def test_find_soffice_prefers_explicit_existing_path(tmp_path: Path):
    executable = tmp_path / "soffice"
    executable.write_text("# fake soffice\n", encoding="utf-8")

    assert find_soffice(str(executable)) == str(executable)


def test_find_soffice_uses_path_lookup(monkeypatch: pytest.MonkeyPatch):
    def fake_which(candidate: str) -> str | None:
        if candidate == "soffice.exe":
            return r"C:\LibreOffice\program\soffice.exe"
        return None

    monkeypatch.setattr(shutil, "which", fake_which)

    assert find_soffice() == r"C:\LibreOffice\program\soffice.exe"
