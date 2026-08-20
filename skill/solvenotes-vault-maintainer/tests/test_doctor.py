from pathlib import Path

import doctor


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
