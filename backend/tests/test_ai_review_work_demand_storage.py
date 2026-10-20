import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from jolt.database import Base, AIReview


def test_work_demand_columns_roundtrip(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'work-demand.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(AIReview(
            id="review-1", capture_run_id="run-1", posting_id="posting-1",
            source_job_id="job-1", review_source="chatgpt_source_first",
            review_version="test", contract_version="1.2", decision="conditional",
            priority_score=50, geography_status="eligible", clearance_status="unknown",
            language_status="clear",
            employment_track="bridge", physical_demand_status="incompatible",
            physical_demand_evidence_json=json.dumps(["Regularly lift 25 kg boxes"]),
            commercial_pressure_status="low", commercial_pressure_evidence_json="[]",
            reviewed_at=datetime.now(timezone.utc), imported_at=datetime.now(timezone.utc),
        ))
        # ORM schema accepts the structured evidence. No human review state is edited.
        session.flush()
        review = session.scalar(select(AIReview).where(AIReview.id == "review-1"))
        assert review is not None
        assert review.physical_demand_status == "incompatible"
        assert json.loads(review.physical_demand_evidence_json) == ["Regularly lift 25 kg boxes"]
        session.rollback()
