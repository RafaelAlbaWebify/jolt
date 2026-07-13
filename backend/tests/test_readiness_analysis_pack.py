from io import BytesIO
from zipfile import ZipFile
import json

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_analysis_pack_includes_application_readiness(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'analysis.db').as_posix()}"
    client = TestClient(create_app(database_url))

    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.test/jobs/application-support",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Own production incidents, inspect logs, and troubleshoot SQL and API integrations."
            ),
        },
    )
    assert intake.status_code == 200

    response = client.get("/api/exports/analysis-pack")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    with ZipFile(BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert "data/application_readiness_reports.csv" in names
        dataset = json.loads(archive.read("data/full_dataset.json"))
        reports = dataset["data"]["application_readiness_reports"]
        assert len(reports) == 1
        report = reports[0]
        assert report["posting_id"] == intake.json()["posting_id"]
        assert report["profile_version_id"] == "rafael-job-search:v2"
        assert report["engine_version"] == "application-readiness-v1"
        assert report["readiness_score"] > 0
        assert report["evidence_matches"]
        assert report["checklist"]
        readme = archive.read("README.md").decode("utf-8")
        assert "Application readiness reports: 1" in readme
