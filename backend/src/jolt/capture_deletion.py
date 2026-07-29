from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import CaptureArtifact
from jolt.database import (
    Application,
    CaptureItem,
    CapturePage,
    CaptureRun,
    Evaluation,
    Outcome,
    Posting,
    ReviewDecision,
    SourceDocument,
)


class CaptureRunDeletionResult(BaseModel):
    capture_run_id: str
    deleted_page_count: int
    deleted_item_count: int
    deleted_artifact_count: int
    deleted_source_document_count: int
    deleted_posting_count: int
    deleted_evaluation_count: int
    protected_posting_count: int


def _posting_is_user_managed(session: Session, posting_id: str) -> bool:
    review = session.scalar(select(ReviewDecision).where(ReviewDecision.posting_id == posting_id))
    if review is not None:
        return True
    application = session.scalar(select(Application).where(Application.posting_id == posting_id))
    if application is not None:
        return True
    outcome = session.scalar(select(Outcome).where(Outcome.posting_id == posting_id))
    return outcome is not None


def delete_capture_run_with_unclassified_opportunities(
    session: Session,
    capture_run_id: str,
) -> CaptureRunDeletionResult:
    run = session.get(CaptureRun, capture_run_id)
    if run is None:
        raise LookupError(f"Capture run {capture_run_id} was not found.")
    if run.status == "running":
        raise ValueError("A running capture run must be stopped before it can be deleted.")

    pages = session.scalars(
        select(CapturePage).where(CapturePage.capture_run_id == capture_run_id)
    ).all()
    items = session.scalars(
        select(CaptureItem).where(CaptureItem.capture_run_id == capture_run_id)
    ).all()
    item_ids = [item.id for item in items]
    artifacts = (
        session.scalars(select(CaptureArtifact).where(CaptureArtifact.capture_item_id.in_(item_ids))).all()
        if item_ids
        else []
    )

    deleted_source_document_ids: set[str] = set()
    deleted_posting_ids: set[str] = set()
    deleted_evaluation_count = 0
    protected_posting_ids: set[str] = set()

    for item in items:
        posting = session.get(Posting, item.posting_id) if item.posting_id else None
        source_document = (
            session.get(SourceDocument, item.source_document_id)
            if item.source_document_id
            else None
        )

        if posting is not None:
            # Only delete opportunities that this capture actually created. Duplicate captures may point
            # at an older posting while creating a transient source document; those older postings must
            # not be removed when deleting the duplicate batch.
            capture_created_posting = posting.source_document_id == item.source_document_id
            if capture_created_posting and not _posting_is_user_managed(session, posting.id):
                evaluations = session.scalars(
                    select(Evaluation).where(Evaluation.posting_id == posting.id)
                ).all()
                for evaluation in evaluations:
                    session.delete(evaluation)
                deleted_evaluation_count += len(evaluations)
                session.delete(posting)
                deleted_posting_ids.add(posting.id)
            else:
                protected_posting_ids.add(posting.id)
                source_document = None

        if source_document is not None:
            still_used = session.scalar(
                select(Posting).where(Posting.source_document_id == source_document.id)
            )
            if still_used is None:
                session.delete(source_document)
                deleted_source_document_ids.add(source_document.id)

    for artifact in artifacts:
        session.delete(artifact)
    for item in items:
        session.delete(item)
    for page in pages:
        session.delete(page)
    session.delete(run)
    session.commit()

    return CaptureRunDeletionResult(
        capture_run_id=capture_run_id,
        deleted_page_count=len(pages),
        deleted_item_count=len(items),
        deleted_artifact_count=len(artifacts),
        deleted_source_document_count=len(deleted_source_document_ids),
        deleted_posting_count=len(deleted_posting_ids),
        deleted_evaluation_count=deleted_evaluation_count,
        protected_posting_count=len(protected_posting_ids),
    )
