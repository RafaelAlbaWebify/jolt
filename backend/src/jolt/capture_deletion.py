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

    protected_posting_ids: set[str] = set()
    posting_ids_to_delete: set[str] = set()
    source_document_ids_to_consider: set[str] = set()
    evaluations_to_delete: list[Evaluation] = []

    # Collect all downstream opportunity targets before deleting anything. This avoids
    # query-triggered autoflush while CaptureItem rows still reference Posting rows.
    for item in items:
        posting = session.get(Posting, item.posting_id) if item.posting_id else None
        source_document = (
            session.get(SourceDocument, item.source_document_id)
            if item.source_document_id
            else None
        )

        if posting is None:
            if source_document is not None:
                source_document_ids_to_consider.add(source_document.id)
            continue

        # Only delete opportunities that this capture actually created. Duplicate captures may point
        # at an older posting while creating a transient source document; those older postings must
        # not be removed when deleting the duplicate batch.
        capture_created_posting = posting.source_document_id == item.source_document_id
        if capture_created_posting and not _posting_is_user_managed(session, posting.id):
            posting_ids_to_delete.add(posting.id)
            if source_document is not None:
                source_document_ids_to_consider.add(source_document.id)
            evaluations_to_delete.extend(
                session.scalars(select(Evaluation).where(Evaluation.posting_id == posting.id)).all()
            )
        else:
            protected_posting_ids.add(posting.id)
            if source_document is not None and not capture_created_posting:
                source_document_ids_to_consider.add(source_document.id)

    # Delete capture-owned rows first, because capture_items hold foreign keys to postings
    # and source_documents. Then delete unclassified opportunity records.
    for artifact in artifacts:
        session.delete(artifact)
    for item in items:
        session.delete(item)
    for page in pages:
        session.delete(page)
    session.delete(run)
    for evaluation in evaluations_to_delete:
        session.delete(evaluation)

    postings_to_delete = [
        session.get(Posting, posting_id)
        for posting_id in posting_ids_to_delete
    ]
    for posting in postings_to_delete:
        if posting is not None:
            session.delete(posting)

    session.flush()

    deleted_source_document_ids: set[str] = set()
    for source_document_id in source_document_ids_to_consider:
        still_used = session.scalar(
            select(Posting).where(Posting.source_document_id == source_document_id)
        )
        if still_used is not None:
            continue
        source_document = session.get(SourceDocument, source_document_id)
        if source_document is not None:
            session.delete(source_document)
            deleted_source_document_ids.add(source_document.id)

    session.commit()

    return CaptureRunDeletionResult(
        capture_run_id=capture_run_id,
        deleted_page_count=len(pages),
        deleted_item_count=len(items),
        deleted_artifact_count=len(artifacts),
        deleted_source_document_count=len(deleted_source_document_ids),
        deleted_posting_count=len(posting_ids_to_delete),
        deleted_evaluation_count=len(evaluations_to_delete),
        protected_posting_count=len(protected_posting_ids),
    )
