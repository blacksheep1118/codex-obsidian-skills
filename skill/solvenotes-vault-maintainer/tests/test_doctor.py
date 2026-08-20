from pathlib import Path

import doctor
import pytest


def test_doctor_reads_central_python_support_contract(tmp_path: Path) -> None:
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
        ("tool-quick", {"PyYAML", "pytest", "ruff"}),
        ("tool-full", {"PyYAML", "pytest", "ruff"}),
        ("online", {"PyYAML"}),
        ("package-notes", set()),
        ("package-workspace", set()),
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
        lambda _python, _contract: (
            {"pytest": "MISSING", "PyYAML": "MISSING", "ruff": "MISSING"},
            None,
        ),
    )
    monkeypatch.setattr(doctor, "command_version", lambda command: f"/usr/bin/{command}")

    values, missing = doctor.report(
        python_bin="/tmp/python",
        notes_root=None,
        skills_root=tmp_path,
        profile=mode,
    )

    missing_modules = {item.split(">=", 1)[0] for item in missing}
    assert required <= missing_modules
    for distribution in {"pytest", "PyYAML", "ruff"}:
        expected = "MISSING" if distribution in required else "OPTIONAL_MISSING"
        assert values[f"status_{distribution}"] == expected


def test_doctor_reports_unvalidated_python_and_required_module_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        doctor,
        "python_probe",
        lambda _python: ({"executable": "/tmp/python", "version": "3.13.1"}, None),
    )
    monkeypatch.setattr(
        doctor,
        "module_versions",
        lambda _python, _contract: (
            {"pytest": "9.0.0", "PyYAML": "6.0.3", "ruff": "0.16.4"},
            None,
        ),
    )
    monkeypatch.setattr(doctor, "command_version", lambda command: f"/usr/bin/{command}")

    values, issues = doctor.report(
        python_bin="/tmp/python",
        notes_root=None,
        skills_root=tmp_path,
        profile="tool-quick",
    )

    assert values["status_python"] == "UNTESTED"
    assert values["status_pytest"] == "VERSION_MISMATCH"
    assert any("validated set" in issue for issue in issues)
    assert any("pytest>=8.0.0,<9.0.0" in issue for issue in issues)
