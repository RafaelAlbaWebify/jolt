"""Phase 1.4 historical evidence and retention tests use disposable SQLite only."""

from sqlalchemy import delete, func, select

from jolt.capture_artifacts import CaptureArtifact
from jolt.database import CaptureItem, PortalSourceObservation, create_session_factory
from jolt.live_capture_workflow import run_linkedin_live_capture
from jolt.schemas import LinkedInLiveCaptureItemRequest, LinkedInLiveCaptureRequest
from jolt.sources.portal_observation_backfill import backfill_portal_observation_receipts
from jolt.sources.posting_source_history import get_posting_source_history


def _capture(session, identifier: str) -> tuple[str, str]:
    result = run_linkedin_live_capture(
        session,
        LinkedInLiveCaptureRequest(
            search_url="https://www.linkedin.com/jobs/search/",
            items=[
                LinkedInLiveCaptureItemRequest(
                    source_job_id=identifier,
                    source_url=f"https://www.linkedin.com/jobs/view/{identifier}",
                    title="Support engineer",
                    company="Example",
                    location="Madrid",
                    description="Investigate incidents, support critical IT applications and infrastructure.",
                    identity_verified=True,
                )
            ],
        ),
    )
    item = result.items[0]
    assert item.posting_id is not None
    return item.posting_id, item.capture_item_id


def test_history_backfill_dry_run_commit_repeat_and_restart(tmp_path) -> None:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'history.db').as_posix()}")
    with factory() as session:
        posting, item_id = _capture(session, "historic-123")
        session.execute(delete(PortalSourceObservation))
        session.commit()
        dry = backfill_portal_observation_receipts(session)
        assert dry.created == 1
        assert session.scalar(select(func.count()).select_from(PortalSourceObservation)) == 0
        written = backfill_portal_observation_receipts(session, commit=True)
        assert written.created == 1
        receipt = session.scalar(select(PortalSourceObservation))
        assert receipt is not None
        assert receipt.capture_item_id == item_id
        assert receipt.source_url.endswith("historic-123")
        assert backfill_portal_observation_receipts(session, commit=True).created == 0
    with factory() as session:
        history = get_posting_source_history(session, posting)
        assert history.total_observations == 1
        assert history.observations[0].capture_item_id == item_id


def test_backfill_rejects_modified_artifact_and_does_not_infer_missing_history(tmp_path) -> None:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'bad.db').as_posix()}")
    with factory() as session:
        posting, item_id = _capture(session, "historic-456")
        session.execute(delete(PortalSourceObservation))
        artifact = session.scalar(
            select(CaptureArtifact).where(CaptureArtifact.capture_item_id == item_id)
        )
        assert artifact is not None
        artifact.raw_payload = "modified without matching stored digest"
        session.commit()
        result = backfill_portal_observation_receipts(session, commit=True)
        assert result.created == 0
        assert result.rejected == 1
        assert result.rejected_item_ids == [item_id]
        assert session.scalar(select(func.count()).select_from(PortalSourceObservation)) == 0
        assert get_posting_source_history(session, posting).total_observations == 0


def test_receipt_remains_after_transient_artifact_and_item_removal(tmp_path) -> None:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'retention.db').as_posix()}")
    with factory() as session:
        posting, item_id = _capture(session, "historic-789")
        receipt = session.scalar(select(PortalSourceObservation))
        assert receipt is not None
        session.execute(delete(CaptureArtifact).where(CaptureArtifact.capture_item_id == item_id))
        session.execute(delete(CaptureItem).where(CaptureItem.id == item_id))
        session.commit()
    with factory() as session:
        history = get_posting_source_history(session, posting)
        assert history.total_observations == 1
        assert history.observations[0].artifact_sha256 == receipt.artifact_sha256
        assert session.get(CaptureItem, item_id) is None
