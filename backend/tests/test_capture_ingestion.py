# ruff: noqa: I001
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


LISTING_HTML = """
<html><body>
  <ul>
    <li class="jobs-search-results__list-item" data-job-id="4434979232">
      <a class="job-card-list__title" href="https://www.linkedin.com/jobs/view/4434979232">Application Support Engineer</a>
      <span class="job-card-container__primary-description">Example Systems</span>
      <span class="job-card-container__metadata-item">Remote Spain</span>
      <span class="job-card-container__footer-item">SQL and incident support</span>
    </li>
    <li class="jobs-search-results__list-item" data-job-id="4435000001">
      <a class="job-card-list__title" href="https://www.linkedin.com/jobs/view/4435000001">Production Support Engineer</a>
      <span class="job-card-container__primary-description">Factory Cloud</span>
      <span class="job-card-container__metadata-item">European Union</span>
    </li>
  </ul>
  <button class="artdeco-pagination__button--next">Next</button>
</body></html>
"""


def detail_html(job_id: str, title: str, company: str, location: str, description: str) -> str:
    return f"""
    <html><body>
      <section class="jobs-search__job-details--container" data-job-id="{job_id}">
        <a class="jobs-unified-top-card__job-title-link" href="https://www.linkedin.com/jobs/view/{job_id}"></a>
        <h1 class="jobs-unified-top-card__job-title">{title}</h1>
        <span class="jobs-unified-top-card__company-name">{company}</span>
        <span class="jobs-unified-top-card__bullet">{location}</span>
        <div class="jobs-description-content__text">{description}</div>
      </section>
    </body></html>
    """


def _client(database_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))


def test_fixture_capture_persists_evidence_and_ingests_only_verified_details(tmp_path: Path) -> None:
    database_path = tmp_path / "capture.db"
    client = _client(database_path)
    verified = detail_html(
        "4434979232",
        "Application Support Engineer",
        "Example Systems",
        "Remote Spain",
        "Own SQL-backed application incidents and API troubleshooting.",
    )
    stale = verified

    response = client.post(
        "/api/captures/linkedin/fixture",
        json={
            "listing_html": LISTING_HTML,
            "detail_html_by_job_id": {
                "4434979232": verified,
                "4435000001": stale,
            },
            "search_url": "https://www.linkedin.com/jobs/search/?keywords=IT%20Support",
        },
    )

    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed_with_warnings"
    assert len(run["items"]) == 2
    verified_item = next(item for item in run["items"] if item["source_job_id"] == "4434979232")
    rejected_item = next(item for item in run["items"] if item["source_job_id"] == "4435000001")
    assert verified_item["detail_status"] == "verified"
    assert verified_item["posting_id"]
    assert verified_item["identity_status"] == "new"
    assert rejected_item["detail_status"] == "rejected_unverified"
    assert rejected_item["posting_id"] is None
    assert any(
        "does not match expected 4435000001" in reason
        for reason in rejected_item["verification_reasons"]
    )

    opportunities = client.get("/api/opportunities").json()
    assert len(opportunities) == 1
    assert opportunities[0]["title"] == "Application Support Engineer"

    restarted = _client(database_path)
    persisted = restarted.get(f"/api/captures/{run['capture_run_id']}")
    assert persisted.status_code == 200
    assert persisted.json()["status"] == "completed_with_warnings"
    assert len(persisted.json()["items"]) == 2

    duplicate = restarted.post(
        "/api/captures/linkedin/fixture",
        json={
            "listing_html": LISTING_HTML,
            "detail_html_by_job_id": {"4434979232": verified},
        },
    )
    assert duplicate.status_code == 200
    duplicate_item = next(
        item for item in duplicate.json()["items"] if item["source_job_id"] == "4434979232"
    )
    assert duplicate_item["identity_status"] == "confirmed_duplicate"
    assert duplicate_item["posting_id"] == verified_item["posting_id"]
    assert duplicate_item["source_document_id"] != verified_item["source_document_id"]
    assert len(restarted.get("/api/opportunities").json()) == 1
