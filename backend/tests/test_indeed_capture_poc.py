from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from jolt.indeed_capture import (
    _is_action_link_text,
    _parse_panel_text,
    _visible_listing_candidates,
    canonical_indeed_job_url,
    extract_indeed_job_key,
)
from jolt.indeed_chrome_attach import _page_search_url
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


def test_parse_panel_text_keeps_selected_title_authoritative() -> None:
    panel_text = """
    Técnico/a de Soporte Informático Junior
    Indra
    España · Teletrabajo
    Contrato indefinido
    Detalles del empleo
    Tipo de empleo
    Contrato indefinido
    Beneficios
    Formación continua
    Descripción completa del empleo
    Soporte a usuarios y resolución de incidencias.
    """

    title, company, location, description = _parse_panel_text(
        panel_text,
        "Técnico/a de Soporte Informático Junior",
    )

    assert title == "Técnico/a de Soporte Informático Junior"
    assert company == "Indra"
    assert location == "España · Teletrabajo"
    assert description == "Soporte a usuarios y resolución de incidencias."


def test_panel_text_parser_handles_description_below_job_details() -> None:
    panel_text = """
    Técnico/a de Soporte Informático Junior
    Indra
    España · Teletrabajo
    Contrato indefinido
    Detalles del empleo
    Tipo de empleo
    Contrato indefinido
    Beneficios
    Formación continua
    Seguro de vida
    Descripción completa del empleo
    Atención a usuarios, soporte remoto y resolución de incidencias.
    """

    title, company, location, description = _parse_panel_text(
        panel_text,
        "Técnico/a de Soporte Informático Junior",
    )

    assert title == "Técnico/a de Soporte Informático Junior"
    assert company == "Indra"
    assert location == "España · Teletrabajo"
    assert "soporte remoto" in description


def test_parse_panel_text_requires_preserved_line_structure() -> None:
    panel_text = (
        "Técnico/a de Soporte Informático Junior\n"
        "Indra\n"
        "España · Teletrabajo\n"
        "Contrato indefinido\n"
        "Detalles del empleo\n"
        "Descripción completa del empleo\n"
        "Soporte remoto a usuarios y resolución de incidencias."
    )

    title, company, location, description = _parse_panel_text(
        panel_text,
        "Técnico/a de Soporte Informático Junior",
    )

    assert title == "Técnico/a de Soporte Informático Junior"
    assert company == "Indra"
    assert location == "España · Teletrabajo"
    assert description == "Soporte remoto a usuarios y resolución de incidencias."


def test_indeed_page_url_preserves_filters_and_replaces_ephemeral_job_key() -> None:
    source = (
        "https://es.indeed.com/jobs?q=IT+Support&l=&sort=date&"
        "sc=0kf%3Aattr%28DSQF7%7CPAXZC%252COR%29%3B&"
        "from=searchOnDesktopSerp&vjk=6c9392526a94bcfa"
    )

    page_1 = _page_search_url(source, 1)
    page_3 = _page_search_url(source, 3)

    assert "q=IT+Support" in page_1
    assert "sort=date" in page_1
    assert "sc=" in page_1
    assert "vjk=" not in page_1
    assert "start=" not in page_1

    assert "q=IT+Support" in page_3
    assert "sort=date" in page_3
    assert "sc=" in page_3
    assert "vjk=" not in page_3
    assert "start=20" in page_3


def test_indeed_capture_contract_accepts_contiguous_multi_page_evidence() -> None:
    payload = {
        "search_url": "https://es.indeed.com/jobs?q=IT+Support&sort=date",
        "requested_item_limit": 3,
        "pages": [
            {
                "page_number": 1,
                "visible_job_ids": ["job-a", "job-b"],
            },
            {
                "page_number": 2,
                "visible_job_ids": ["job-b", "job-c"],
            },
        ],
        "items": [
            {
                "source_job_id": "job-a",
                "source_url": "https://es.indeed.com/viewjob?jk=job-a",
                "title": "IT Support A",
                "company": "Example A",
                "location": "Spain",
                "description": "Support users.",
                "identity_verified": True,
                "verification_reason": "",
            },
            {
                "source_job_id": "job-b",
                "source_url": "https://es.indeed.com/viewjob?jk=job-b",
                "title": "IT Support B",
                "company": "Example B",
                "location": "Spain",
                "description": "Support users.",
                "identity_verified": True,
                "verification_reason": "",
            },
            {
                "source_job_id": "job-c",
                "source_url": "https://es.indeed.com/viewjob?jk=job-c",
                "title": "IT Support C",
                "company": "Example C",
                "location": "Spain",
                "description": "Support users.",
                "identity_verified": True,
                "verification_reason": "",
            },
        ],
    }

    request = IndeedLiveCaptureRequest.model_validate(payload)

    assert len(request.pages) == 2
    assert request.pages[1].page_number == 2
    assert request.requested_item_limit == 3


def test_indeed_live_capture_persists_multi_page_evidence(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'indeed-pages.db').as_posix()}"))
    response = client.post(
        "/api/captures/indeed/live",
        json={
            "search_url": "https://es.indeed.com/jobs?q=IT+Support&sort=date",
            "requested_item_limit": 2,
            "stop_reason": "page_limit_reached",
            "pages": [
                {"page_number": 1, "visible_job_ids": ["page1-job"]},
                {"page_number": 2, "visible_job_ids": ["page2-job"]},
            ],
            "items": [
                {
                    "source_job_id": "page1-job",
                    "source_url": "https://es.indeed.com/viewjob?jk=page1-job",
                    "title": "Support One",
                    "company": "Example One",
                    "location": "Spain",
                    "description": "Support users and endpoints.",
                    "identity_verified": True,
                    "verification_reason": "",
                },
                {
                    "source_job_id": "page2-job",
                    "source_url": "https://es.indeed.com/viewjob?jk=page2-job",
                    "title": "Support Two",
                    "company": "Example Two",
                    "location": "Spain",
                    "description": "Support users and systems.",
                    "identity_verified": True,
                    "verification_reason": "",
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [page["page_number"] for page in body["pages"]] == [1, 2]
    assert body["pages"][0]["visible_job_ids"] == ["page1-job"]
    assert body["pages"][1]["visible_job_ids"] == ["page2-job"]
    assert body["total_items"] == 2


def test_indeed_action_links_are_not_treated_as_job_titles() -> None:
    assert _is_action_link_text("Ver empleos similares de esta empresa")
    assert _is_action_link_text("Solicitar en la página de la empresa")
    assert _is_action_link_text("Apply on company site")
    assert not _is_action_link_text("Technical Support Specialist")
    assert not _is_action_link_text("IT System Administrator")


def test_visible_candidates_include_mixed_current_indeed_link_structures() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(
            """
            <html>
              <body>
                <h2 class="jobTitle">
                  <a href="https://es.indeed.com/viewjob?jk=job-a">Support A</a>
                </h2>
                <div>
                  <a href="https://es.indeed.com/rc/clk?jk=job-b">Support B</a>
                </div>
                <div>
                  <a href="https://es.indeed.com/pagead/clk?jk=job-c">Support C</a>
                </div>
              </body>
            </html>
            """
        )
        candidates = _visible_listing_candidates(page, 10)
        browser.close()

    assert [candidate["source_job_id"] for candidate in candidates] == [
        "job-a",
        "job-b",
        "job-c",
    ]



def test_visible_candidates_accept_data_jk_card_without_jk_in_href() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(
            """
            <html>
              <body>
                <div class="job_seen_beacon" data-jk="job-data-jk">
                  <h2 class="jobTitle">
                    <a href="https://es.indeed.com/viewjob">Data JK Support Engineer</a>
                  </h2>
                  <span>Example Company</span>
                </div>
              </body>
            </html>
            """
        )
        candidates = _visible_listing_candidates(page, 10)
        browser.close()

    assert candidates == [
        {
            "source_job_id": "job-data-jk",
            "source_url": "https://es.indeed.com/viewjob?jk=job-data-jk",
            "title": "Data JK Support Engineer",
        }
    ]
