"""Jobgether review import must preserve source fidelity and idempotency."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from jolt.database import Base, CaptureItem, Posting
from jolt.jobgether_operational_run import import_report, validated_offers

KEY = "6ac5af098a27695aea352fce"


def _report() -> dict:
    return {
        "source": "jobgether",
        "mode": "supervised_search_tab_read_only",
        "search_url": "https://jobgether.com/talent/matches",
        "offers": [
            {
                "status": "extracted_unverified",
                "source_job_id": KEY,
                "url": f"https://jobgether.com/offer/{KEY}-technical-engineer",
                "title": "Technical Engineer",
                "company": "Example Employer",
                "description": "Support Microsoft 365 and Windows endpoints. " * 8,
                "mismatches": [],
                "source_evidence_verified": False,
                "work_from_spain_verified": False,
            }
        ],
    }


def test_complete_jobgether_evidence_is_importable_and_idempotent(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = import_report(session, _report())
        assert first["newly_imported"] == 1
        assert first["review_inbox_verified"] == 1
        assert first["work_from_spain_verified"] is False
        session.commit()
    with Session(engine) as session:
        again = import_report(session, _report())
        assert again["newly_imported"] == 0
        assert again["review_inbox_verified"] == 1
        assert len(session.scalars(select(Posting)).all()) == 1
        assert len(session.scalars(select(CaptureItem)).all()) == 1
        session.rollback()


def test_unverified_or_short_jobgether_detail_is_not_imported(tmp_path) -> None:
    report = _report()
    report["offers"][0]["description"] = "short"
    assert validated_offers(report) == []
    engine = create_engine(f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        try:
            import_report(session, report)
        except ValueError as exc:
            assert "complete" in str(exc)
            session.rollback()
        else:
            raise AssertionError("Unreliable Jobgether evidence must be rejected")
        assert session.scalars(select(Posting)).all() == []
        assert session.scalars(select(CaptureItem)).all() == []
