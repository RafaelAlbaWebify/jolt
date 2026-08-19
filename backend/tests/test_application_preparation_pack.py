from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

import jolt.main as main_module
from jolt.main import create_app


def test_application_preparation_pack_contains_evidence_and_boundaries(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'preparation.db').as_posix()}"
    client = TestClient(create_app(database_url))

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/application-support",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Support SQL, APIs, integrations, logs, incidents, DNS, and production systems."
            ),
        },
    )
    posting_id = intake.json()["posting_id"]

    response = client.get(f"/api/opportunities/{posting_id}/preparation-pack")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == (
        f"attachment; filename=JOLT_PREPARATION_{posting_id}.zip"
    )

    with ZipFile(BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert names == {
            "README.txt",
            "application-preparation.json",
            "application-preparation.md",
        }
        markdown = archive.read("application-preparation.md").decode("utf-8")
        assert "Application Support Engineer" in markdown
        assert "Evidence preparation" in markdown
        assert "Priority:" not in markdown
        assert "Score:" not in markdown
        assert "CV tailoring points" in markdown
        assert "Likely interview questions" in markdown
        assert "No application, CV edit, or recruiter contact was performed" in archive.read(
            "README.txt"
        ).decode("utf-8")


def test_application_preparation_pack_returns_404_for_unknown_posting(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'missing.db').as_posix()}"
    client = TestClient(create_app(database_url))
    response = client.get("/api/opportunities/missing/preparation-pack")
    assert response.status_code == 404


def test_application_preparation_pack_does_not_mask_internal_keyerror_as_404(
    tmp_path, monkeypatch
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'internal-error.db').as_posix()}"
    client = TestClient(create_app(database_url), raise_server_exceptions=True)

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/internal-error",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Support production applications and troubleshoot incidents."
            ),
        },
    )
    assert intake.status_code == 200
    posting_id = intake.json()["posting_id"]

    def broken_pack(*args, **kwargs):
        raise KeyError("simulated internal defect")

    monkeypatch.setattr(
        main_module,
        "build_application_preparation_pack",
        broken_pack,
    )

    with pytest.raises(KeyError, match="simulated internal defect"):
        client.get(f"/api/opportunities/{posting_id}/preparation-pack")
