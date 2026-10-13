import hashlib

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import CaptureArtifact
from jolt.database import Base, CaptureItem, CaptureRun, Posting
from jolt.infojobs_observations import inspect_offer, stage_report

ID = "9a3c6c996942d0b2d0f19cacaf8f2e"
URL = f"https://www.infojobs.net/barcelona/customer-service/of-i{ID}"


def _report() -> dict:
    body = (
        "Buscar empleo\nCustomer Service Trainee\nGuardar\nExample Company\n"
        + "Requisitos\nDescripción\n"
        + "Example genuine job description about helping customers and "
        + "answering difficult queries across technical support platforms. " * 3
        + "\nCategoría\nInformática\nNosotros\n© Footer"
    )
    return {
        "source": "infojobs",
        "mode": "supervised_browser_evidence_read_only",
        "search_url": "https://www.infojobs.net/ofertas-trabajo/support-it",
        "offers": [
            {
                "url": URL,
                "title_observed": "Customer Service Trainee",
                "status": "extracted_unverified",
                "body_text": body,
                "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            }
        ],
    }


def test_extract_description_excludes_navigation_and_footer() -> None:
    job = inspect_offer(_report()["offers"][0])
    assert job["source_job_id"] == ID
    assert job["description"].startswith("Example genuine job description")
    assert "Buscar empleo" not in job["description"]
    assert "© Footer" not in job["description"]


def test_hash_mismatch_fails_closed() -> None:
    offer = _report()["offers"][0]
    offer["body_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash"):
        inspect_offer(offer)


def test_stage_deduplicates_and_never_creates_postings(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        one = stage_report(session, _report())
        assert one["staged_unverified"] == 1
        session.commit()
    with Session(engine) as session:
        two = stage_report(session, _report())
        assert two["already_known"] == 1
        assert two["staged_unverified"] == 0
        assert session.scalar(select(func.count(CaptureArtifact.id))) == 1
        assert session.scalar(select(func.count(Posting.id))) == 0
        item = session.scalar(select(CaptureItem))
        assert item is not None
        assert item.detail_status == "observed_unverified"
        assert item.posting_id is None
        assert session.scalar(select(CaptureRun.mode)) == "supervised_browser_observation"


def test_dry_run_rolls_back(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        stage_report(session, _report())
        session.rollback()
        assert session.scalar(select(func.count(CaptureItem.id))) == 0


def test_realistic_infojobs_header_extracts_company_and_location() -> None:
    offer = _report()["offers"][0]
    body = offer["body_text"].replace(
        "Customer Service Trainee\nGuardar\nExample Company\n",
        "Customer Service Trainee\nGuardar\nExperis IT\n4 (205)\nBarcelona (Barcelona)\nPresencial\n",
    )
    offer["body_text"] = body
    offer["body_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    parsed = inspect_offer(offer)
    assert parsed["company"] == "Experis IT"
    assert parsed["location"] == "Barcelona (Barcelona)"
