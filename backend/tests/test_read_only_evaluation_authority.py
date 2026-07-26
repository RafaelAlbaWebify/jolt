from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from jolt.application_readiness import ApplicationReadiness
from jolt.database import Evaluation, ProfileVersion, create_session_factory
from jolt.main import create_app


def _client(database_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))


def _derived_counts(database_path: Path) -> tuple[int, int, int]:
    factory = create_session_factory(f"sqlite:///{database_path.as_posix()}")
    with factory() as session:
        return (
            int(session.scalar(select(func.count(Evaluation.id))) or 0),
            int(session.scalar(select(func.count(ProfileVersion.id))) or 0),
            int(session.scalar(select(func.count(ApplicationReadiness.id))) or 0),
        )


def test_get_workspaces_do_not_create_derived_records(tmp_path: Path) -> None:
    database_path = tmp_path / "readonly.db"
    client = _client(database_path)
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.com/jobs/readonly",
            "raw_text": (
                "Application Support Engineer\nExample Systems\nLocation: Remote Spain\n"
                "Application support, SQL troubleshooting, incident ownership, APIs, and monitoring."
            ),
        },
    )
    assert intake.status_code == 200
    posting_id = intake.json()["posting_id"]
    before = _derived_counts(database_path)

    for url in (
        "/api/opportunity-index",
        "/api/application-index",
        "/api/opportunities",
        f"/api/opportunity-detail/{posting_id}",
        "/api/market-intelligence",
    ):
        response = client.get(url)
        assert response.status_code == 200

    assert _derived_counts(database_path) == before


def test_explicit_refresh_creates_v4_and_all_reads_use_it(tmp_path: Path) -> None:
    database_path = tmp_path / "authority.db"
    client = _client(database_path)
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.com/jobs/authority",
            "raw_text": (
                "Production Support Engineer\nExample Systems\nLocation: Remote Spain\n"
                "Production support, incident ownership, SQL, API integration, logs, and monitoring."
            ),
        },
    )
    assert intake.status_code == 200
    posting_id = intake.json()["posting_id"]

    refresh = client.post("/api/evaluations/refresh")
    assert refresh.status_code == 200
    assert refresh.json()["authoritative_engine"] == "profile-rules-v4"

    queue_item = client.get("/api/opportunity-index").json()[0]
    detail = client.get(f"/api/opportunity-detail/{posting_id}").json()
    list_item = client.get("/api/opportunities").json()[0]

    assert detail["engine_version"] == "profile-rules-v4"
    assert queue_item["evaluation_id"] == detail["evaluation_id"] == list_item["evaluation_id"]
    assert queue_item["ranking_score"] == detail["ranking_score"] == list_item["ranking_score"]

    before = _derived_counts(database_path)
    client.get("/api/opportunity-index")
    client.get(f"/api/opportunity-detail/{posting_id}")
    client.get("/api/opportunities")
    assert _derived_counts(database_path) == before
