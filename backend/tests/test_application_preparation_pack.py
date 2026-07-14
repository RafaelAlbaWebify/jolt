from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

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
