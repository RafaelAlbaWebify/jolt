from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_identity_evidence_preserves_duplicate_source_documents(tmp_path: Path) -> None:
    app = create_app(f"sqlite:///{(tmp_path / 'identity.db').as_posix()}")
    client = TestClient(app)
    payload = {
        "source_url": "https://www.linkedin.com/jobs/view/123?utm_source=test",
        "raw_text": (
            "Application Support Engineer\n"
            "Example Systems\n"
            "Location: Remote Spain\n"
            "Application support, SQL, API, incident ownership."
        ),
    }

    first = client.post("/api/intake/manual", json=payload)
    second = client.post(
        "/api/intake/manual",
        json={**payload, "source_url": "https://www.linkedin.com/jobs/view/123?trk=duplicate"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["identity_status"] == "confirmed_duplicate"
    posting_id = first.json()["posting_id"]

    response = client.get(f"/api/opportunities/{posting_id}/identity-evidence")

    assert response.status_code == 200
    evidence = response.json()
    assert evidence["evidence_count"] == 2
    assert evidence["duplicate_evidence_count"] == 1
    assert [item["identity_status"] for item in evidence["evidence"]] == [
        "original",
        "confirmed_duplicate",
    ]
    assert {item["match_basis"] for item in evidence["evidence"]} == {"canonical_url"}
    assert all("raw_text" not in item for item in evidence["evidence"])


def test_bulk_identity_evidence_returns_opportunities_and_sources_once(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'bulk-identity.db').as_posix()}"))
    payloads = [
        {
            "source_url": "https://www.linkedin.com/jobs/view/123",
            "raw_text": (
                "Application Support Engineer\n"
                "Example Systems\n"
                "Location: Remote Spain\n"
                "Application support, SQL, API, incident ownership."
            ),
        },
        {
            "source_url": "https://www.linkedin.com/jobs/view/456",
            "raw_text": (
                "Cloud Support Engineer\n"
                "Beta Cloud\n"
                "Location: Madrid\n"
                "Cloud support, monitoring, incident response, and Azure."
            ),
        },
    ]
    for payload in payloads:
        assert client.post("/api/intake/manual", json=payload).status_code == 200
    assert (
        client.post(
            "/api/intake/manual",
            json={
                **payloads[0],
                "source_url": "https://www.linkedin.com/jobs/view/123?trk=duplicate",
            },
        ).status_code
        == 200
    )

    response = client.get("/api/identity-evidence")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 2
    assert {row["opportunity"]["title"] for row in rows} == {
        "Application Support Engineer",
        "Cloud Support Engineer",
    }
    duplicate_row = next(
        row for row in rows if row["opportunity"]["title"] == "Application Support Engineer"
    )
    assert duplicate_row["evidence"]["evidence_count"] == 2
    assert duplicate_row["evidence"]["duplicate_evidence_count"] == 1
    assert all("raw_text" not in item for row in rows for item in row["evidence"]["evidence"])


def test_identity_evidence_returns_404_for_unknown_posting(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'missing.db').as_posix()}"))
    response = client.get("/api/opportunities/missing/identity-evidence")
    assert response.status_code == 404
