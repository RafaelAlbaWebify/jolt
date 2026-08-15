from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from jolt.database import (
    Evaluation,
    Posting,
    SourceDocument,
    create_session_factory,
    utc_now,
)
from jolt.evaluation_strategy import CapabilityEvidence, RoleFamily, StrategyProfile
from jolt.strategy_runtime import ENGINE_VERSION, ensure_strategy_review


def _profile() -> StrategyProfile:
    return StrategyProfile(
        profile_id="persistence-test",
        version=1,
        role_families=[
            RoleFamily(
                id="application_support",
                label="Application Support",
                priority="primary",
                terms=["application support"],
                strategic_value=95,
            )
        ],
        capabilities=[
            CapabilityEvidence(
                id="incident_support",
                label="Incident support",
                terms=["incident", "troubleshooting"],
                evidence_level=5,
            )
        ],
    )


def test_newer_legacy_capture_is_followed_by_current_strategy_snapshot(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'persistence.db').as_posix()}"
    factory = create_session_factory(database_url)

    with factory() as session:
        source = SourceDocument(
            id=str(uuid4()),
            source_type="linkedin_live",
            source_url="https://www.linkedin.com/jobs/view/123",
            raw_text="Application Support Engineer",
            content_hash="a" * 64,
            captured_at=utc_now(),
        )
        posting = Posting(
            id=str(uuid4()),
            source_document_id=source.id,
            canonical_url="https://www.linkedin.com/jobs/view/123",
            identity_key="linkedin:123",
            title="Application Support Engineer",
            company="Example Systems",
            location="Spain",
            description="Own application support incidents and troubleshooting.",
            identity_status="new",
            created_at=utc_now(),
        )
        session.add_all([source, posting])
        session.flush()

        profile = _profile()

        ensure_strategy_review(session, profile, posting, commit=False)
        session.flush()

        first_current = session.scalar(
            select(Evaluation)
            .where(
                Evaluation.posting_id == posting.id,
                Evaluation.engine_version == ENGINE_VERSION,
            )
            .order_by(Evaluation.created_at.desc(), Evaluation.id.desc())
        )
        assert first_current is not None

        legacy = Evaluation(
            id=str(uuid4()),
            posting_id=posting.id,
            profile_version_id=first_current.profile_version_id,
            engine_version="rules-v1",
            recommendation="consider",
            confidence="medium",
            ranking_score=59,
            reasons_json=json.dumps(["Legacy capture evaluation."]),
            created_at=first_current.created_at + timedelta(seconds=1),
        )
        session.add(legacy)
        session.flush()

        latest_before = session.scalar(
            select(Evaluation)
            .where(Evaluation.posting_id == posting.id)
            .order_by(Evaluation.created_at.desc(), Evaluation.id.desc())
        )
        assert latest_before is not None
        assert latest_before.engine_version == "rules-v1"

        ensure_strategy_review(session, profile, posting, commit=False)
        session.flush()

        evaluations = list(
            session.scalars(
                select(Evaluation)
                .where(Evaluation.posting_id == posting.id)
                .order_by(Evaluation.created_at.desc(), Evaluation.id.desc())
            ).all()
        )

        latest_after = evaluations[0]
        assert latest_after.engine_version == ENGINE_VERSION
        assert latest_after.recommendation == first_current.recommendation
        assert latest_after.ranking_score == first_current.ranking_score

        current_count = sum(
            evaluation.engine_version == ENGINE_VERSION for evaluation in evaluations
        )
        assert current_count == 2

        ensure_strategy_review(session, profile, posting, commit=False)
        session.flush()

        current_after_repeat = list(
            session.scalars(
                select(Evaluation).where(
                    Evaluation.posting_id == posting.id,
                    Evaluation.engine_version == ENGINE_VERSION,
                )
            ).all()
        )

        assert len(current_after_repeat) == 2
