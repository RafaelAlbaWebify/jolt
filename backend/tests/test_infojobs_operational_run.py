"""InfoJobs one-command import regression tests."""

import hashlib

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from jolt.database import Base, CaptureItem, Posting
from jolt.infojobs_operational_run import import_report


def _report() -> dict:
    title = "IT Support Engineer"
    body = (
        "Buscar empleo\n" + title + "\nGuardar\nExample Employer\n"
        "Madrid (Madrid)\nRemoto\nRequisitos\nDescripción\n"
        + ("Support Windows, Microsoft 365 and endpoints. " * 8)
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


def test_operational_import_is_idempotent_and_visible_in_review_inbox(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = import_report(session, _report())
        assert result["staged_unverified"] == 1
        assert result["newly_imported"] == 1
        assert result["review_inbox_verified"] == 1
        assert result["postings"][0]["ai_review_status"] == "awaiting_ai_review"
        assert result["ai_review_performed"] is False
        session.commit()
    with Session(engine) as session:
        repeated = import_report(session, _report())
        assert repeated["staged_unverified"] == 0
        assert repeated["newly_imported"] == 0
        assert repeated["already_imported"] == 1
        assert repeated["review_inbox_verified"] == 1
        assert len(session.scalars(select(Posting)).all()) == 1
        assert len(session.scalars(select(CaptureItem)).all()) == 1
        session.rollback()


def test_operational_import_rollback_on_tampered_evidence(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    report = _report()
    report["offers"][0]["body_sha256"] = "0" * 64
    with Session(engine) as session:
        try:
            import_report(session, report)
        except ValueError as exc:
            assert "body hash mismatch" in str(exc)
            session.rollback()
        else:
            raise AssertionError("Tampered evidence must be rejected")
    with Session(engine) as session:
        assert session.scalars(select(Posting)).all() == []
        assert session.scalars(select(CaptureItem)).all() == []
