from pathlib import Path

import doctor
import pytest


def test_doctor_reads_central_python_support_contract(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.solvenotes]\npython-min = "3.9"\npython-primary = "3.11"\npython-newest-validated = "3.12"\n',
        encoding="utf-8",
    )

    assert doctor.python_support(tmp_path) == {
        "python-min": "3.9",
        "python-primary": "3.11",
        "python-newest-validated": "3.12",
    }


@pytest.mark.parametrize(
    ("mode", "required"),
    [
        ("vault-quick", {"PyYAML"}),
        ("vault-full", {"PyYAML"}),
        ("tool-quick", {"PyYAML"}),
        ("tool-full", {"PyYAML", "pytest", "ruff"}),
    ],
)
def test_doctor_modes_only_require_their_own_python_tools(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str,
    required: set[str],
) -> None:
    monkeypatch.setattr(
        doctor,
        "python_probe",
        lambda _python: ({"executable": "/tmp/python", "version": "3.11.0"}, None),
    )
    monkeypatch.setattr(
        doctor,
        "module_versions",
        lambda _python: ({"pytest": "MISSING", "PyYAML": "MISSING", "ruff": "MISSING"}, None),
    )
    monkeypatch.setattr(doctor, "python_support", lambda _root: {})
    monkeypatch.setattr(doctor, "command_version", lambda command: f"/usr/bin/{command}")
    monkeypatch.setattr(doctor.shutil, "which", lambda command: f"/usr/bin/{command}")

    values, missing = doctor.report(
        python_bin="/tmp/python",
        notes_root=None,
        skills_root=tmp_path,
        mode=mode,
    )

    assert set(missing) == required
    for distribution in {"pytest", "PyYAML", "ruff"}:
        expected = "MISSING" if distribution in required else "OPTIONAL_MISSING"
        assert values[f"status_{distribution}"] == expected
