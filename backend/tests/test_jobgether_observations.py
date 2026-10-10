from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import CaptureArtifact
from jolt.database import Base, CaptureItem, Posting
from jolt.jobgether_observations import stage_jobgether_observations


def test_observation_staging_never_promotes_posting(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    key = "6ac85207480485773199660a"
    record = {
        "source_job_id": key,
        "url": f"https://jobgether.com/offer/{key}-it-support",
        "title": "IT Support",
        "company": "Example",
        "location": "Anywhere",
        "quality_flags": ["older_than_30_days"],
    }
    with Session(engine) as session:
        first = stage_jobgether_observations(
            session, search_url="https://jobgether.com/api/v1/jobs", jobs=[record]
        )
        assert first["staged_unverified"] == 1
        assert first["committed"] is False
        session.commit()
    with Session(engine) as session:
        second = stage_jobgether_observations(
            session, search_url="https://jobgether.com/api/v1/jobs", jobs=[record]
        )
        assert second["already_known"] == 1
        session.commit()
        assert session.scalar(select(func.count(Posting.id))) == 0
        assert session.scalar(select(func.count(CaptureItem.id))) == 1
        assert session.scalar(select(func.count(CaptureArtifact.id))) == 1
        item = session.scalar(select(CaptureItem))
        assert item is not None
        assert item.detail_status == "observed_unverified"
        assert item.source_document_id is None
        assert item.posting_id is None
