from __future__ import annotations

import io
import json
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from jolt.main import create_app

LISTING_HTML = """
<html><body><ul>
  <li class="jobs-search-results__list-item" data-job-id="4434979232">
    <a class="job-card-list__title" href="https://www.linkedin.com/jobs/view/4434979232">Application Support Engineer</a>
    <span class="job-card-container__primary-description">Example Systems</span>
    <span class="job-card-container__metadata-item">Remote Spain</span>
  </li>
  <li class="jobs-search-results__list-item" data-job-id="4435000001">
    <a class="job-card-list__title" href="https://www.linkedin.com/jobs/view/4435000001">Production Support Engineer</a>
    <span class="job-card-container__primary-description">Factory Cloud</span>
    <span class="job-card-container__metadata-item">European Union</span>
  </li>
</ul><button class="artdeco-pagination__button--next">Next</button></body></html>
"""


def detail_html(job_id: str, title: str, company: str) -> str:
    return f"""
    <html><body><section class="jobs-search__job-details--container" data-job-id="{job_id}">
      <a class="jobs-unified-top-card__job-title-link" href="https://www.linkedin.com/jobs/view/{job_id}"></a>
      <h1 class="jobs-unified-top-card__job-title">{title}</h1>
      <span class="jobs-unified-top-card__company-name">{company}</span>
      <span class="jobs-unified-top-card__bullet">Remote Spain</span>
      <div class="jobs-description-content__text">SQL application support and incident ownership.</div>
    </section></body></html>
    """


def test_capture_history_detail_and_analysis_pack(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'history.db').as_posix()}"))
    verified = detail_html("4434979232", "Application Support Engineer", "Example Systems")

    captured = client.post(
        "/api/captures/linkedin/fixture",
        json={
            "listing_html": LISTING_HTML,
            "detail_html_by_job_id": {
                "4434979232": verified,
                "4435000001": verified,
            },
            "search_url": "https://www.linkedin.com/jobs/search/?keywords=IT%20Support",
        },
    )
    assert captured.status_code == 200
    run_id = captured.json()["capture_run_id"]

    history = client.get("/api/captures")
    assert history.status_code == 200
    assert history.json()[0]["capture_run_id"] == run_id
    assert history.json()[0]["verified_items"] == 1
    assert history.json()[0]["rejected_items"] == 1

    detail = client.get(f"/api/captures/{run_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["pages"][0]["visible_job_ids"] == ["4434979232", "4435000001"]
    rejected = next(item for item in payload["items"] if item["source_job_id"] == "4435000001")
    assert rejected["detail_status"] == "rejected_unverified"
    assert rejected["title"] == "Production Support Engineer"
    assert rejected["posting_id"] is None
    assert rejected["verification_reasons"]

    exported = client.get("/api/exports/analysis-pack")
    assert exported.status_code == 200
    with ZipFile(io.BytesIO(exported.content)) as archive:
        names = set(archive.namelist())
        assert "data/capture_runs.csv" in names
        assert "data/capture_items.csv" in names
        dataset = json.loads(archive.read("data/full_dataset.json"))
        assert len(dataset["data"]["capture_runs"]) == 1
        assert len(dataset["data"]["capture_items"]) == 2
        assert dataset["data"]["capture_items"][1]["detail_status"] in {
            "verified",
            "rejected_unverified",
        }
