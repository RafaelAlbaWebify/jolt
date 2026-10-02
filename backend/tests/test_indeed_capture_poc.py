from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jolt.indeed_capture import _parse_panel_text, canonical_indeed_job_url, extract_indeed_job_key
from jolt.main import create_app
from jolt.schemas import IndeedLiveCaptureRequest
from jolt.url_identity import canonicalize_source_url, indeed_job_key


def test_extracts_indeed_job_key_from_viewjob_url() -> None:
    url = "https://es.indeed.com/viewjob?jk=6679e1407fc705be&utm_source=test"
    assert extract_indeed_job_key(url) == "6679e1407fc705be"
    assert indeed_job_key(url) == "6679e1407fc705be"


def test_canonicalizes_indeed_job_url_by_job_key() -> None:
    url = "https://es.indeed.com/viewjob?jk=6679e1407fc705be&from=serp&vjk=ignored"
    assert canonical_indeed_job_url(url) == "https://es.indeed.com/viewjob?jk=6679e1407fc705be"
    assert canonicalize_source_url(url) == "https://www.indeed.com/viewjob?jk=6679e1407fc705be"


def test_indeed_capture_contract_is_bounded_to_ten_jobs() -> None:
    payload = {
        "search_url": "https://es.indeed.com/jobs?q=it+support",
        "requested_item_limit": 1,
        "items": [
            {
                "source_job_id": "abc123",
                "source_url": "https://es.indeed.com/viewjob?jk=abc123",
                "title": "IT Support",
                "company": "Example",
                "location": "Vigo",
                "description": "Support users and Windows systems.",
                "identity_verified": True,
                "verification_reason": "",
            }
        ],
    }

    request = IndeedLiveCaptureRequest.model_validate(payload)
    assert request.items[0].source_job_id == "abc123"
    assert request.requested_item_limit == 1


def test_indeed_live_capture_ingests_verified_posting(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'indeed.db').as_posix()}"))
    response = client.post(
        "/api/captures/indeed/live",
        json={
            "search_url": "https://es.indeed.com/jobs?q=it+support",
            "requested_item_limit": 1,
            "stop_reason": "requested_limit_reached",
            "items": [
                {
                    "source_job_id": "6679e1407fc705be",
                    "source_url": "https://es.indeed.com/viewjob?jk=6679e1407fc705be",
                    "title": "Técnico/a IT Junior Soporte con inglés",
                    "company": "knowmad mood",
                    "location": "Las Rozas de Madrid",
                    "description": (
                        "Resolución de incidencias técnicas de primer nivel. "
                        "Administración básica de sistemas y atención a usuarios."
                    ),
                    "identity_verified": True,
                    "verification_reason": "",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "indeed"
    assert payload["verified_items"] == 1
    assert payload["items"][0]["detail_status"] == "verified"
    assert payload["items"][0]["posting_id"]
    assert payload["items"][0]["source_document_id"]


def test_parse_panel_text_extracts_visible_indeed_detail() -> None:
    panel_text = """
    Técnico auxiliar informático
    domestiko.com
    Ogíjares, Granada provincia
    2.645 € al mes - Contrato temporal, Jornada completa
    Detalles del empleo
    Salario
    2.645 € al mes
    Tipo de empleo
    Contrato temporal
    Jornada completa
    Descripción completa del empleo
    En Ogíjares (Granada) se busca una persona para dar soporte informático.
    Atención a usuarios y resolución de incidencias.
    """

    title, company, location, description = _parse_panel_text(
        panel_text,
        "Técnico auxiliar informático",
    )

    assert title == "Técnico auxiliar informático"
    assert company == "domestiko.com"
    assert location == "Ogíjares, Granada provincia"
    assert "soporte informático" in description
    assert "resolución de incidencias" in description
