from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import CaptureArtifact
from jolt.database import Base, CaptureItem, CaptureRun, Posting
from jolt.jobgether_supervised_stage import stage_supervised_batch

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
                "company": "Example",
                "mismatches": [],
                "applicant_countries": ["US"],
                "spain_declared": False,
                "source_evidence_verified": False,
                "work_from_spain_verified": False,
            }
        ],
    }


def test_staging_is_idempotent_and_does_not_promote(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = stage_supervised_batch(session, _report())
        assert first["staged_unverified"] == 1
        session.commit()
    with Session(engine) as session:
        second = stage_supervised_batch(session, _report())
        assert second["staged_unverified"] == 0
        assert second["already_known"] == 1
        session.rollback()
        assert session.scalar(select(func.count(Posting.id))) == 0
        assert session.scalar(select(func.count(CaptureItem.id))) == 1
        assert session.scalar(select(func.count(CaptureArtifact.id))) == 1
        item = session.scalar(select(CaptureItem))
        assert item is not None
        assert item.posting_id is None
        assert item.source_document_id is None
        assert item.detail_status == "observed_unverified"
        assert session.scalar(select(CaptureRun.mode)) == "supervised_browser_observation"


def test_staging_rollback_preserves_empty_database(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        stage_supervised_batch(session, _report())
        session.rollback()
        assert session.scalar(select(func.count(CaptureRun.id))) == 0
        assert session.scalar(select(func.count(CaptureItem.id))) == 0


def test_identity_mismatch_never_staged(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    report = _report()
    report["offers"][0]["source_job_id"] = "bbbbbbbbbbbbbbbbbbbbbbbb"
    with Session(engine) as session:
        result = stage_supervised_batch(session, report)
        assert result["staged_unverified"] == 0
        assert session.scalar(select(func.count(CaptureRun.id))) == 0


def test_new_description_refreshes_known_source_without_erasing_old_evidence(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        stage_supervised_batch(session, _report())
        session.commit()
    richer = _report()
    richer["offers"][0]["description"] = (
        "Support the Microsoft 365 workplace stack and resolve technical incidents. " * 5
    )
    with Session(engine) as session:
        result = stage_supervised_batch(session, richer)
        assert result["refreshed_evidence"] == 1
        assert result["new_source_id_count"] == 0
        session.commit()
    with Session(engine) as session:
        assert session.scalar(select(func.count(CaptureItem.id))) == 2
        assert session.scalar(select(func.count(CaptureArtifact.id))) == 2
        again = stage_supervised_batch(session, richer)
        assert again["staged_unverified"] == 0
        assert again["already_known"] == 1
        session.rollback()
