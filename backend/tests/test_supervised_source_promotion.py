import hashlib
import json

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import CaptureArtifact
from jolt.database import Base, CaptureItem, Posting
from jolt.infojobs_observations import stage_report
from jolt.jobgether_supervised_stage import stage_supervised_batch
from jolt.supervised_source_promotion import promote_supervised_item


def _infojobs() -> dict:
    title = "IT Support Engineer"
    body = (
        "Buscar empleo\n" + title + "\nGuardar\nExample Employer\n"
        "Madrid (Madrid)\nRemoto\nRequisitos\nDescripción\n"
        + ("Support Windows, Microsoft 365, user incidents and network endpoints. " * 5)
        + "\nCategoría\nInformática\nNosotros\n"
    )
    return {
        "source": "infojobs",
        "mode": "supervised_browser_evidence_read_only",
        "search_url": "https://www.infojobs.net/ofertas-trabajo/support-it",
        "offers": [
            {
                "url": "https://www.infojobs.net/madrid/support/of-i9a3c6c996942d0b2d0f19cacaf8f2e",
                "title_observed": title,
                "status": "extracted_unverified",
                "body_text": body,
                "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            }
        ],
    }


def _jobgether(has_description: bool = True) -> dict:
    return {
        "source": "jobgether",
        "mode": "supervised_search_tab_read_only",
        "search_url": "https://jobgether.com/talent/matches",
        "offers": [
            {
                "status": "extracted_unverified",
                "source_job_id": "a" * 24,
                "url": "https://jobgether.com/offer/" + "a" * 24 + "-technical-engineer",
                "title": "Technical Engineer",
                "company": "Example Employer",
                "description": "Support global customer IT operations and troubleshoot endpoints. "
                * 5
                if has_description
                else "",
                "mismatches": [],
            }
        ],
    }


def test_infojobs_explicit_import_is_idempotent(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        stage_report(session, _infojobs())
        item = session.scalar(select(CaptureItem))
        assert item is not None
        result = promote_supervised_item(session, item.id)
        assert result["status"] == "imported_for_review"
        assert item.company == "Example Employer"
        assert item.location == "Madrid (Madrid)"
        posting = session.get(Posting, item.posting_id)
        assert posting is not None
        assert posting.description.startswith("Support Windows, Microsoft 365")
        assert "IT Support Engineer" not in posting.description
        assert "eligibility is NOT verified" in item.verification_reasons_json
        repeated = promote_supervised_item(session, item.id)
        assert repeated["status"] == "already_imported"
        session.commit()
    with Session(engine) as session:
        assert session.scalar(select(func.count(Posting.id))) == 1
        assert session.scalar(select(func.count(CaptureArtifact.id))) == 1


def test_jobgether_old_capture_without_description_fails_closed(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        stage_supervised_batch(session, _jobgether(has_description=False))
        item = session.scalar(select(CaptureItem))
        assert item is not None
        with pytest.raises(ValueError, match="Insufficient"):
            promote_supervised_item(session, item.id)
        session.rollback()
    with Session(engine) as session:
        assert session.scalar(select(func.count(Posting.id))) == 0


def test_jobgether_full_structured_capture_imports_to_existing_posting(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        stage_supervised_batch(session, _jobgether())
        item = session.scalar(select(CaptureItem))
        assert item is not None
        result = promote_supervised_item(session, item.id)
        assert result["status"] == "imported_for_review"
        assert item.posting_id is not None
        session.commit()


def test_tampered_artifact_fails_without_new_posting(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        stage_report(session, _infojobs())
        item = session.scalar(select(CaptureItem))
        artifact = session.scalar(select(CaptureArtifact))
        assert item is not None and artifact is not None
        artifact.raw_payload = json.dumps({"offer": {}})
        with pytest.raises(ValueError, match="digest"):
            promote_supervised_item(session, item.id)
        session.rollback()
    with Session(engine) as session:
        assert session.scalar(select(func.count(Posting.id))) == 0
