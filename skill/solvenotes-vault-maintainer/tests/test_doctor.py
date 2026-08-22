import subprocess
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
        (
            "vault-runtime",
            {
                "PyYAML",
                "numpy",
                "torch",
                "onnx",
                "onnxruntime",
                "onnxscript",
                "pyspark",
            },
        ),
        ("github-ready", {"PyYAML"}),
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


def test_runtime_profile_uses_optional_runtime_requirements_file(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    (source_root / "skill").mkdir(parents=True)
    installed_root = tmp_path / "installed"
    installed_root.mkdir()

    source_path = doctor.requirements_path_for_profile(
        "vault-runtime", source_root
    )
    installed_path = doctor.requirements_path_for_profile(
        "vault-runtime", installed_root
    )

    relative = Path("algorithm-job-notes-for-obsidian/requirements-runtime.txt")
    assert source_path == source_root / "skill" / relative
    assert installed_path == installed_root / relative


def test_command_version_rejects_macos_java_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda _command: "/usr/bin/java")
    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["java", "--version"],
            returncode=1,
            stdout="",
            stderr="Unable to locate a Java Runtime.",
        ),
    )

    assert doctor.command_version("java") is None


@pytest.mark.parametrize(
    ("detail", "expected"),
    [
        ("/jdk/bin/java (openjdk 17.0.20.1 2026-08-18)", 17),
        ('/jdk/bin/java (java version "1.8.0_442")', 8),
        ("/jdk/bin/java", None),
    ],
)
def test_java_major_parses_supported_version_forms(
    detail: str, expected: int | None
) -> None:
    assert doctor.java_major(detail) == expected


def test_runtime_profile_enforces_exact_requirements_file_versions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    notes_root = tmp_path / "notes"
    notes_root.mkdir()
    (notes_root / "AGENT.md").write_text("# test\n", encoding="utf-8")
    skills_root = tmp_path / "skills"
    requirements = (
        skills_root
        / "skill"
        / "algorithm-job-notes-for-obsidian"
        / "requirements-runtime.txt"
    )
    requirements.parent.mkdir(parents=True)
    requirements.write_text(
        "PyYAML==6.0.3\n"
        "numpy==1.26.4\n"
        "torch==2.11.0\n"
        "onnx==1.22.0\n"
        "onnxruntime==1.28.0\n"
        "onnxscript==0.7.1\n"
        "pyspark==4.2.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        doctor,
        "python_probe",
        lambda _python: ({"executable": "/tmp/python", "version": "3.11.0"}, None),
    )
    monkeypatch.setattr(
        doctor,
        "module_versions",
        lambda _python, _contract: (
            {
                "PyYAML": "6.0.3",
                "numpy": "1.26.5",
                "torch": "2.11.0+cpu",
                "onnx": "1.22.0",
                "onnxruntime": "1.28.0",
                "onnxscript": "0.7.1",
                "pyspark": "4.2.0",
            },
            None,
        ),
    )
    monkeypatch.setattr(
        doctor,
        "command_version",
        lambda command: (
            "/jdk/bin/java (openjdk 17.0.20.1)"
            if command == "java"
            else f"/usr/bin/{command}"
        ),
    )

    values, issues = doctor.report(
        python_bin="/tmp/python",
        notes_root=notes_root,
        skills_root=skills_root,
        profile="vault-runtime",
    )

    assert values["status_numpy"] == "VERSION_MISMATCH"
    assert values["status_torch"] == "SUPPORTED"
    assert "numpy==1.26.4 required (found 1.26.5)" in issues


def test_runtime_profile_requires_python_3_10(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = doctor.load_contract()
    runtime_profile = contract["profiles"]["vault-runtime"]
    runtime_profile["required_modules"] = []
    runtime_profile.pop("requirements_file")
    monkeypatch.setattr(doctor, "load_contract", lambda: contract)
    monkeypatch.setattr(
        doctor,
        "python_probe",
        lambda _python: ({"executable": "/tmp/python", "version": "3.9.20"}, None),
    )
    monkeypatch.setattr(doctor, "module_versions", lambda *_args: ({}, None))
    monkeypatch.setattr(doctor, "command_version", lambda command: f"/usr/bin/{command}")

    values, issues = doctor.report(
        python_bin="/tmp/python",
        notes_root=None,
        skills_root=tmp_path,
        profile="vault-runtime",
    )

    assert values["status_python"] == "UNSUPPORTED"
    assert "Python >= 3.10 required (found 3.9.20)" in issues
