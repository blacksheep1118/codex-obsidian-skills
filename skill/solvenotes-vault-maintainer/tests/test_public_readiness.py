import sys

import check_public_readiness as cpr
import pytest


def test_public_readiness_classifies_paths_tokens_and_example_password(tmp_path, monkeypatch) -> None:
    note = tmp_path / "sample.md"
    note.write_text(
        "\n".join(
            [
                "path=" + "/" + "Users/alice/private/course.pdf",
                "token=" + "ghp_" + "A" * 24,
                "demo " + "password" + "='123456'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cpr, "ROOT", tmp_path)
    monkeypatch.setattr(cpr, "git_files", lambda: ["sample.md"])

    findings = cpr.collect_findings()
    categories = [item["category"] for item in findings]

    assert "absolute_path" in categories
    assert "github_token" in categories
    assert "example_password" in categories


def test_public_readiness_strict_ignores_example_password(tmp_path, monkeypatch) -> None:
    note = tmp_path / "sample.md"
    note.write_text("demo " + "password" + "='123456'\n", encoding="utf-8")
    monkeypatch.setattr(cpr, "ROOT", tmp_path)
    monkeypatch.setattr(cpr, "git_files", lambda: ["sample.md"])

    payload = cpr.build_payload(strict=True)

    assert payload["finding_count"] == 1
    assert payload["strict_failure_count"] == 0


@pytest.mark.parametrize(
    ("filename", "expected_suffix"),
    [
        ("lecture.pdf", ".pdf"),
        ("bundle.tar.gz", ".tar.gz"),
        ("SLIDES.PDF", ".pdf"),
        ("pytorch_model.bin", ".bin"),
    ],
)
def test_public_readiness_strict_rejects_forbidden_attachments(
    tmp_path,
    monkeypatch,
    filename: str,
    expected_suffix: str,
) -> None:
    attachment = tmp_path / filename
    attachment.write_bytes(b"small attachment\n")
    monkeypatch.setattr(cpr, "ROOT", tmp_path)
    monkeypatch.setattr(cpr, "git_files", lambda: [filename])

    payload = cpr.build_payload(strict=True)

    assert payload["finding_count"] == 1
    assert payload["findings"][0]["category"] == "forbidden_attachment"
    assert payload["findings"][0]["match"] == expected_suffix
    assert payload["strict_failure_count"] == 1


def test_public_readiness_keeps_note_images_as_warnings(tmp_path, monkeypatch) -> None:
    image = tmp_path / "figure.PNG"
    image.write_bytes(b"small image\n")
    monkeypatch.setattr(cpr, "ROOT", tmp_path)
    monkeypatch.setattr(cpr, "git_files", lambda: ["figure.PNG"])

    payload = cpr.build_payload(strict=True)

    assert payload["finding_count"] == 1
    assert payload["findings"][0]["category"] == "binary_attachment"
    assert payload["findings"][0]["match"] == ".png"
    assert payload["strict_failure_count"] == 0


def test_public_readiness_strict_cli_fails_for_forbidden_attachment(tmp_path, monkeypatch) -> None:
    pdf = tmp_path / "lecture.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(cpr, "ROOT", tmp_path)
    monkeypatch.setattr(cpr, "git_files", lambda: ["lecture.pdf"])
    monkeypatch.setattr(sys, "argv", ["check_public_readiness.py", "--strict"])

    assert cpr.main() == 1


def test_public_readiness_does_not_treat_url_path_as_local_home(tmp_path, monkeypatch) -> None:
    note = tmp_path / "sample.md"
    note.write_text(
        "论文：https://people.seas.harvard.edu/home/example/paper.pdf\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cpr, "ROOT", tmp_path)
    monkeypatch.setattr(cpr, "git_files", lambda: ["sample.md"])

    payload = cpr.build_payload(strict=True)

    assert payload["finding_count"] == 0
    assert payload["strict_failure_count"] == 0


@pytest.mark.parametrize("filename", ["linked.md", "linked.pdf", "linked.PNG"])
def test_public_readiness_does_not_read_external_symlink_target(
    tmp_path,
    monkeypatch,
    filename: str,
) -> None:
    outside = tmp_path.parent / "outside-public-readiness.md"
    outside.write_text("token=" + "ghp_" + "A" * 24 + "\n", encoding="utf-8")
    (tmp_path / filename).symlink_to(outside)
    monkeypatch.setattr(cpr, "ROOT", tmp_path)
    monkeypatch.setattr(cpr, "git_files", lambda: [filename])

    assert cpr.collect_findings() == []
