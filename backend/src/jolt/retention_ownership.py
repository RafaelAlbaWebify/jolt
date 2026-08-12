from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jolt.capture_archival import ARCHIVED_CAPTURE_STATUS
from jolt.database import (
    CaptureItem,
    CapturePage,
    CaptureRun,
    MarketIntelligenceObservation,
)


class CaptureRetentionPreviewItem(BaseModel):
    capture_run_id: str
    status: str
    started_at: str
    is_current_capture: bool
    capture_page_count: int
    capture_item_count: int
    verified_item_count: int
    market_observation_count: int
    market_extraction_complete: bool
    retention_action: str


class RetentionOwnershipPreview(BaseModel):
    current_capture_run_id: str | None
    capture_run_count: int
    superseded_capture_run_count: int
    market_observation_count: int
    captures: list[CaptureRetentionPreviewItem]


def build_retention_ownership_preview(
    session: Session,
) -> RetentionOwnershipPreview:
    runs = list(
        session.scalars(
            select(CaptureRun).order_by(
                CaptureRun.started_at.desc(),
                CaptureRun.id.desc(),
            )
        ).all()
    )

    current_run = next(
        (
            run
            for run in runs
            if run.status != ARCHIVED_CAPTURE_STATUS
        ),
        None,
    )
    current_id = current_run.id if current_run else None

    items: list[CaptureRetentionPreviewItem] = []

    for run in runs:
        page_count = int(
            session.scalar(
                select(func.count(CapturePage.id)).where(
                    CapturePage.capture_run_id == run.id
                )
            )
            or 0
        )
        item_count = int(
            session.scalar(
                select(func.count(CaptureItem.id)).where(
                    CaptureItem.capture_run_id == run.id
                )
            )
            or 0
        )
        verified_count = int(
            session.scalar(
                select(func.count(CaptureItem.id))
                .where(CaptureItem.capture_run_id == run.id)
                .where(CaptureItem.detail_status == "verified")
                .where(CaptureItem.posting_id.is_not(None))
            )
            or 0
        )
        expected_job_ids = set(
            session.scalars(
                select(CaptureItem.source_job_id)
                .where(CaptureItem.capture_run_id == run.id)
                .where(CaptureItem.detail_status == "verified")
                .where(CaptureItem.posting_id.is_not(None))
            ).all()
        )
        observed_job_ids = set(
            session.scalars(
                select(MarketIntelligenceObservation.source_job_id).where(
                    MarketIntelligenceObservation.source_capture_run_id
                    == run.id
                )
            ).all()
        )
        observation_count = len(observed_job_ids)

        complete = expected_job_ids.issubset(observed_job_ids)
        is_current = run.id == current_id

        if is_current:
            action = "keep_current_capture"
        elif complete and run.status != "running":
            action = "purge_when_guarded_cleanup_is_enabled"
        else:
            action = "keep_until_market_extraction_is_complete"

        items.append(
            CaptureRetentionPreviewItem(
                capture_run_id=run.id,
                status=run.status,
                started_at=run.started_at.isoformat(),
                is_current_capture=is_current,
                capture_page_count=page_count,
                capture_item_count=item_count,
                verified_item_count=verified_count,
                market_observation_count=observation_count,
                market_extraction_complete=complete,
                retention_action=action,
            )
        )

    total_observations = int(
        session.scalar(
            select(func.count(MarketIntelligenceObservation.id))
        )
        or 0
    )

    return RetentionOwnershipPreview(
        current_capture_run_id=current_id,
        capture_run_count=len(runs),
        superseded_capture_run_count=sum(
            1
            for item in items
            if not item.is_current_capture
        ),
        market_observation_count=total_observations,
        captures=items,
    )



def _guarded_retention_cleanup_state(
    session,
) -> dict[str, object]:
    from sqlalchemy import bindparam, text

    def values(
        sql: str,
        params: dict[str, object] | None = None,
    ) -> set[str]:
        rows = session.execute(
            text(sql),
            params or {},
        ).all()
        return {
            str(row[0])
            for row in rows
            if row[0] is not None
        }

    def rows_for_ids(
        sql: str,
        ids: set[str],
    ):
        if not ids:
            return []

        statement = text(sql).bindparams(
            bindparam("ids", expanding=True)
        )
        return session.execute(
            statement,
            {"ids": sorted(ids)},
        ).all()

    current_row = session.execute(
        text(
            """
            SELECT id
            FROM capture_runs
            WHERE status != 'archived'
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """
        )
    ).first()

    current_run_id = (
        str(current_row[0])
        if current_row is not None
        else None
    )

    all_run_rows = session.execute(
        text(
            """
            SELECT id, status
            FROM capture_runs
            """
        )
    ).all()

    superseded_run_ids = {
        str(row[0])
        for row in all_run_rows
        if str(row[0]) != current_run_id
    }

    superseded_running_run_ids = {
        str(row[0])
        for row in all_run_rows
        if (
            str(row[0]) != current_run_id
            and str(row[1]) == "running"
        )
    }

    expected_observation_pairs = {
        (str(row[0]), str(row[1]))
        for row in rows_for_ids(
            """
            SELECT capture_run_id, source_job_id
            FROM capture_items
            WHERE capture_run_id IN :ids
              AND detail_status = 'verified'
            """,
            superseded_run_ids,
        )
    }

    observed_pairs = {
        (str(row[0]), str(row[1]))
        for row in rows_for_ids(
            """
            SELECT source_capture_run_id, source_job_id
            FROM market_intelligence_observations
            WHERE source_capture_run_id IN :ids
            """,
            superseded_run_ids,
        )
    }

    missing_observation_pairs = (
        expected_observation_pairs - observed_pairs
    )

    superseded_posting_ids = {
        str(row[0])
        for row in rows_for_ids(
            """
            SELECT DISTINCT posting_id
            FROM capture_items
            WHERE capture_run_id IN :ids
              AND posting_id IS NOT NULL
            """,
            superseded_run_ids,
        )
    }

    current_posting_ids: set[str] = set()

    if current_run_id is not None:
        current_posting_ids = values(
            """
            SELECT DISTINCT posting_id
            FROM capture_items
            WHERE capture_run_id = :run_id
              AND posting_id IS NOT NULL
            """,
            {"run_id": current_run_id},
        )

    manual_posting_ids = values(
        """
        SELECT p.id
        FROM postings p
        JOIN source_documents sd
          ON sd.id = p.source_document_id
        WHERE sd.source_type = 'manual'
        """
    )

    application_posting_ids = values(
        """
        SELECT DISTINCT posting_id
        FROM applications
        """
    )

    review_posting_ids = values(
        """
        SELECT DISTINCT posting_id
        FROM review_decisions
        """
    )

    outcome_posting_ids = values(
        """
        SELECT DISTINCT posting_id
        FROM outcomes
        """
    )

    durable_posting_ids = (
        current_posting_ids
        | manual_posting_ids
        | application_posting_ids
        | review_posting_ids
        | outcome_posting_ids
    )

    retained_posting_ids = (
        superseded_posting_ids
        & durable_posting_ids
    )

    candidate_posting_ids = (
        superseded_posting_ids
        - durable_posting_ids
    )

    dependency_tables = (
        "application_readiness_reports",
        "applications",
        "capture_items",
        "evaluations",
        "outcomes",
        "review_decisions",
    )

    dependency_counts: dict[str, int] = {}

    for table_name in dependency_tables:
        if not candidate_posting_ids:
            dependency_counts[table_name] = 0
            continue

        statement = text(
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE posting_id IN :ids
            """
        ).bindparams(
            bindparam("ids", expanding=True)
        )

        dependency_counts[table_name] = int(
            session.execute(
                statement,
                {"ids": sorted(candidate_posting_ids)},
            ).scalar_one()
        )

    superseded_source_ids = {
        str(row[0])
        for row in rows_for_ids(
            """
            SELECT DISTINCT source_document_id
            FROM capture_items
            WHERE capture_run_id IN :ids
              AND source_document_id IS NOT NULL
            """,
            superseded_run_ids,
        )
    }

    candidate_posting_source_ids = {
        str(row[0])
        for row in rows_for_ids(
            """
            SELECT source_document_id
            FROM postings
            WHERE id IN :ids
            """,
            candidate_posting_ids,
        )
    }

    possible_source_ids = (
        superseded_source_ids
        | candidate_posting_source_ids
    )

    remaining_posting_source_ids: set[str] = set()
    remaining_capture_source_ids: set[str] = set()

    if possible_source_ids:
        statement = text(
            """
            SELECT DISTINCT source_document_id
            FROM postings
            WHERE source_document_id IN :ids
              AND id NOT IN :candidate_ids
            """
        ).bindparams(
            bindparam("ids", expanding=True),
            bindparam("candidate_ids", expanding=True),
        )

        candidate_parameter = (
            sorted(candidate_posting_ids)
            if candidate_posting_ids
            else ["__none__"]
        )

        remaining_posting_source_ids = {
            str(row[0])
            for row in session.execute(
                statement,
                {
                    "ids": sorted(possible_source_ids),
                    "candidate_ids": candidate_parameter,
                },
            ).all()
            if row[0] is not None
        }

        statement = text(
            """
            SELECT DISTINCT source_document_id
            FROM capture_items
            WHERE source_document_id IN :ids
              AND capture_run_id NOT IN :run_ids
            """
        ).bindparams(
            bindparam("ids", expanding=True),
            bindparam("run_ids", expanding=True),
        )

        run_parameter = (
            sorted(superseded_run_ids)
            if superseded_run_ids
            else ["__none__"]
        )

        remaining_capture_source_ids = {
            str(row[0])
            for row in session.execute(
                statement,
                {
                    "ids": sorted(possible_source_ids),
                    "run_ids": run_parameter,
                },
            ).all()
            if row[0] is not None
        }

    candidate_source_document_ids = (
        possible_source_ids
        - remaining_posting_source_ids
        - remaining_capture_source_ids
    )

    blocked_reasons: list[str] = []

    if current_run_id is None:
        blocked_reasons.append(
            "No current non-archived capture exists."
        )

    if superseded_running_run_ids:
        blocked_reasons.append(
            "A non-current capture is still running; "
            "cleanup requires all superseded captures to be settled."
        )

    if missing_observation_pairs:
        blocked_reasons.append(
            "Market Intelligence extraction is incomplete for "
            f"{len(missing_observation_pairs)} verified capture items."
        )

    if dependency_counts["applications"]:
        blocked_reasons.append(
            "A capture-only candidate unexpectedly owns an application."
        )

    if dependency_counts["review_decisions"]:
        blocked_reasons.append(
            "A capture-only candidate unexpectedly owns a review decision."
        )

    if dependency_counts["outcomes"]:
        blocked_reasons.append(
            "A capture-only candidate unexpectedly owns an outcome."
        )

    confirmation = (
        "PURGE "
        f"{len(superseded_run_ids)} SUPERSEDED CAPTURE RUNS "
        "AND "
        f"{len(candidate_posting_ids)} CAPTURE-ONLY POSTINGS"
    )

    return {
        "current_capture_run_id": current_run_id,
        "superseded_run_ids": superseded_run_ids,
        "retained_posting_ids": retained_posting_ids,
        "candidate_posting_ids": candidate_posting_ids,
        "candidate_source_document_ids": (
            candidate_source_document_ids
        ),
        "expected_observation_pairs": (
            expected_observation_pairs
        ),
        "observed_pairs": observed_pairs,
        "missing_observation_pairs": (
            missing_observation_pairs
        ),
        "dependency_counts": dependency_counts,
        "blocked_reasons": blocked_reasons,
        "confirmation": confirmation,
    }


def build_guarded_retention_cleanup_plan(
    session,
) -> dict[str, object]:
    state = _guarded_retention_cleanup_state(session)

    return {
        "current_capture_run_id": (
            state["current_capture_run_id"]
        ),
        "superseded_capture_run_count": len(
            state["superseded_run_ids"]
        ),
        "retained_posting_count": len(
            state["retained_posting_ids"]
        ),
        "capture_only_posting_count": len(
            state["candidate_posting_ids"]
        ),
        "candidate_source_document_count": len(
            state["candidate_source_document_ids"]
        ),
        "verified_capture_observation_count": len(
            state["expected_observation_pairs"]
        ),
        "missing_market_observation_count": len(
            state["missing_observation_pairs"]
        ),
        "candidate_dependency_counts": dict(
            state["dependency_counts"]
        ),
        "blocked": bool(state["blocked_reasons"]),
        "blocked_reasons": list(
            state["blocked_reasons"]
        ),
        "required_confirmation": state["confirmation"],
    }


def execute_guarded_retention_cleanup(
    session,
    *,
    confirmation: str,
) -> dict[str, object]:
    from sqlalchemy import bindparam, text

    state = _guarded_retention_cleanup_state(session)

    if state["blocked_reasons"]:
        raise ValueError(
            "Guarded retention cleanup is blocked: "
            + "; ".join(state["blocked_reasons"])
        )

    expected_confirmation = str(
        state["confirmation"]
    )

    if confirmation != expected_confirmation:
        raise ValueError(
            "Exact cleanup confirmation does not match the "
            "current retention plan."
        )

    run_ids = set(state["superseded_run_ids"])
    posting_ids = set(
        state["candidate_posting_ids"]
    )
    source_ids = set(
        state["candidate_source_document_ids"]
    )

    deleted: dict[str, int] = {}

    def delete_where_ids(
        table_name: str,
        column_name: str,
        ids: set[str],
    ) -> int:
        if not ids:
            return 0

        statement = text(
            f"""
            DELETE FROM {table_name}
            WHERE {column_name} IN :ids
            """
        ).bindparams(
            bindparam("ids", expanding=True)
        )

        result = session.execute(
            statement,
            {"ids": sorted(ids)},
        )

        return int(result.rowcount or 0)

    item_ids = {
        str(row[0])
        for row in session.execute(
            text(
                """
                SELECT id
                FROM capture_items
                WHERE capture_run_id IN :ids
                """
            ).bindparams(
                bindparam("ids", expanding=True)
            ),
            {"ids": sorted(run_ids)},
        ).all()
    } if run_ids else set()

    with session.begin_nested():
        deleted["capture_artifacts"] = (
            delete_where_ids(
                "capture_artifacts",
                "capture_item_id",
                item_ids,
            )
        )

        deleted["capture_items"] = (
            delete_where_ids(
                "capture_items",
                "capture_run_id",
                run_ids,
            )
        )

        deleted["capture_pages"] = (
            delete_where_ids(
                "capture_pages",
                "capture_run_id",
                run_ids,
            )
        )

        deleted["capture_runs"] = (
            delete_where_ids(
                "capture_runs",
                "id",
                run_ids,
            )
        )

        deleted["application_readiness_reports"] = (
            delete_where_ids(
                "application_readiness_reports",
                "posting_id",
                posting_ids,
            )
        )

        deleted["evaluations"] = (
            delete_where_ids(
                "evaluations",
                "posting_id",
                posting_ids,
            )
        )

        deleted["postings"] = (
            delete_where_ids(
                "postings",
                "id",
                posting_ids,
            )
        )

        deleted["source_documents"] = (
            delete_where_ids(
                "source_documents",
                "id",
                source_ids,
            )
        )

        violations = session.execute(
            text("PRAGMA foreign_key_check")
        ).all()

        if violations:
            raise RuntimeError(
                "Foreign-key violations detected during "
                "guarded retention cleanup."
            )

    session.expire_all()

    return {
        "deleted": deleted,
        "preserved_market_observation_count": len(
            state["observed_pairs"]
        ),
        "preserved_retained_posting_count": len(
            state["retained_posting_ids"]
        ),
        "confirmation_used": expected_confirmation,
    }
