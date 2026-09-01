from collections.abc import Callable, Iterator
from contextlib import suppress

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.database import utc_now
from jolt.errors import JoltNotFoundError
from jolt.global_context_api import build_global_context_router
from jolt.local_linkedin_capture import (
    LocalLinkedInCaptureRequest,
    LocalLinkedInCaptureStatus,
    get_local_linkedin_capture_status,
    queue_local_linkedin_capture,
    run_queued_local_linkedin_capture,
)
from jolt.professional_intelligence_capture_deletion import (
    ProfessionalCaptureDeletionRequest,
    ProfessionalCaptureDeletionResult,
    delete_professional_capture_run,
)
from jolt.professional_intelligence_capture_plan import (
    ProfessionalCapturePlan,
    build_professional_capture_plan,
)
from jolt.professional_intelligence_capture_runs import (
    ProfessionalCaptureAuthorizationRequest,
    ProfessionalCaptureCreateRequest,
    ProfessionalCaptureRunResponse,
    authorize_professional_capture_run,
    cancel_professional_capture_run,
    create_professional_capture_preview_run,
    get_professional_capture_run,
    list_professional_capture_runs,
)
from jolt.professional_intelligence_evidence_contract import (
    ProfessionalArtifactManifestEntry,
    ProfessionalEvidencePolicy,
    ProfessionalExecutionReadiness,
    professional_evidence_policy,
    professional_execution_readiness,
    validate_professional_artifact_manifest_entry,
)
from jolt.professional_intelligence_evidence_review import (
    ProfessionalEvidenceRunReview,
    review_professional_capture_evidence,
)
from jolt.professional_intelligence_evidence_root import (
    ProfessionalEvidenceRootRequest,
    ProfessionalEvidenceRootResponse,
    clear_professional_evidence_root,
    configure_professional_evidence_root,
    get_professional_evidence_root,
)
from jolt.professional_intelligence_opportunity_import import (
    ProfessionalOpportunityImportResult,
    import_professional_opportunity_candidates,
)
from jolt.professional_intelligence_records import ProfessionalCaptureRun
from jolt.professional_intelligence_retention import (
    ProfessionalRetentionCleanupRequest,
    ProfessionalRetentionCleanupResult,
    ProfessionalRetentionPreview,
    cleanup_expired_professional_evidence,
    preview_professional_retention_cleanup,
)
from jolt.professional_intelligence_routing_summary import (
    ProfessionalCaptureRoutingSummary,
    build_professional_capture_routing_summary,
)
from jolt.professional_intelligence_structured_extraction import (
    ProfessionalStructuredExtraction,
    extract_professional_intelligence,
)
from jolt.professional_intelligence_supervised_runtime import (
    start_bounded_professional_capture,
)

SessionProvider = Callable[[], Iterator[Session]]


def _run_professional_capture_background(
    get_session: SessionProvider,
    run_id: str,
) -> None:
    session_iterator = get_session()
    session: Session | None = None
    try:
        session = next(session_iterator)
        start_bounded_professional_capture(session, run_id)
    except Exception:
        if session is not None:
            session.rollback()
            run = session.get(ProfessionalCaptureRun, run_id)
            if run is not None:
                now = utc_now()
                run.status = "failed"
                run.completed_at = now
                run.current_source_id = ""
                run.progress_updated_at = now
                run.stop_reason = "capture_background_failure"
                session.commit()
    finally:
        close = getattr(session_iterator, "close", None)
        if callable(close):
            with suppress(Exception):
                close()
        elif session is not None:
            with suppress(Exception):
                session.close()


def _queued_capture_response(
    run: ProfessionalCaptureRunResponse,
) -> ProfessionalCaptureRunResponse:
    return run.model_copy(
        update={
            "mode": "supervised_read_only",
            "status": "running",
            "started_at": utc_now(),
            "stop_reason": "capture_queued",
        }
    )


def build_professional_intelligence_plan_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["professional-intelligence"])
    router.include_router(build_global_context_router())
    session_dependency = Depends(get_session)

    @router.post(
        "/api/captures/linkedin/local",
        response_model=LocalLinkedInCaptureStatus,
        tags=["captures"],
    )
    def start_local_linkedin_capture(
        request: LocalLinkedInCaptureRequest,
        background_tasks: BackgroundTasks,
    ) -> LocalLinkedInCaptureStatus:
        try:
            queued = queue_local_linkedin_capture(request)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        background_tasks.add_task(run_queued_local_linkedin_capture)
        return queued

    @router.get(
        "/api/captures/linkedin/local/status",
        response_model=LocalLinkedInCaptureStatus,
        tags=["captures"],
    )
    def local_linkedin_capture_status() -> LocalLinkedInCaptureStatus:
        return get_local_linkedin_capture_status()

    @router.get(
        "/api/professional-intelligence/capture-plan",
        response_model=ProfessionalCapturePlan,
    )
    def professional_intelligence_capture_plan(
        session: Session = session_dependency,
    ) -> ProfessionalCapturePlan:
        return build_professional_capture_plan(session)

    @router.get(
        "/api/professional-intelligence/evidence-policy",
        response_model=ProfessionalEvidencePolicy,
    )
    def professional_intelligence_evidence_policy() -> ProfessionalEvidencePolicy:
        return professional_evidence_policy()

    @router.get(
        "/api/professional-intelligence/execution-readiness",
        response_model=ProfessionalExecutionReadiness,
    )
    def professional_intelligence_execution_readiness(
        session: Session = session_dependency,
    ) -> ProfessionalExecutionReadiness:
        evidence_root = get_professional_evidence_root(session)
        return professional_execution_readiness(
            evidence_root_verified=evidence_root.configured
            and evidence_root.exists
            and evidence_root.writable
        )

    @router.get(
        "/api/professional-intelligence/evidence-root",
        response_model=ProfessionalEvidenceRootResponse,
    )
    def professional_intelligence_evidence_root(
        session: Session = session_dependency,
    ) -> ProfessionalEvidenceRootResponse:
        return get_professional_evidence_root(session)

    @router.post(
        "/api/professional-intelligence/evidence-root",
        response_model=ProfessionalEvidenceRootResponse,
    )
    def configure_professional_intelligence_evidence_root(
        request: ProfessionalEvidenceRootRequest,
        session: Session = session_dependency,
    ) -> ProfessionalEvidenceRootResponse:
        try:
            return configure_professional_evidence_root(session, request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.delete(
        "/api/professional-intelligence/evidence-root",
        response_model=ProfessionalEvidenceRootResponse,
    )
    def clear_professional_intelligence_evidence_root(
        session: Session = session_dependency,
    ) -> ProfessionalEvidenceRootResponse:
        return clear_professional_evidence_root(session)

    @router.post(
        "/api/professional-intelligence/artifact-manifest/validate",
        response_model=ProfessionalArtifactManifestEntry,
    )
    def validate_professional_intelligence_artifact_manifest(
        entry: ProfessionalArtifactManifestEntry,
        session: Session = session_dependency,
    ) -> ProfessionalArtifactManifestEntry:
        try:
            return validate_professional_artifact_manifest_entry(session, entry)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get(
        "/api/professional-intelligence/retention-preview",
        response_model=ProfessionalRetentionPreview,
    )
    def professional_intelligence_retention_preview(
        session: Session = session_dependency,
    ) -> ProfessionalRetentionPreview:
        try:
            return preview_professional_retention_cleanup(session)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post(
        "/api/professional-intelligence/retention-cleanup",
        response_model=ProfessionalRetentionCleanupResult,
    )
    def professional_intelligence_retention_cleanup(
        request: ProfessionalRetentionCleanupRequest,
        session: Session = session_dependency,
    ) -> ProfessionalRetentionCleanupResult:
        try:
            return cleanup_expired_professional_evidence(session, request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post(
        "/api/professional-intelligence/capture-runs",
        response_model=ProfessionalCaptureRunResponse,
    )
    def record_professional_capture_preview(
        request: ProfessionalCaptureCreateRequest | None = None,
        session: Session = session_dependency,
    ) -> ProfessionalCaptureRunResponse:
        return create_professional_capture_preview_run(session, request)

    @router.get(
        "/api/professional-intelligence/capture-runs",
        response_model=list[ProfessionalCaptureRunResponse],
    )
    def professional_capture_run_history(
        session: Session = session_dependency,
    ) -> list[ProfessionalCaptureRunResponse]:
        return list_professional_capture_runs(session)

    @router.get(
        "/api/professional-intelligence/capture-runs/{run_id}",
        response_model=ProfessionalCaptureRunResponse,
    )
    def professional_capture_run(
        run_id: str,
        session: Session = session_dependency,
    ) -> ProfessionalCaptureRunResponse:
        try:
            return get_professional_capture_run(session, run_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get(
        "/api/professional-intelligence/capture-runs/{run_id}/evidence-review",
        response_model=ProfessionalEvidenceRunReview,
    )
    def professional_capture_evidence_review(
        run_id: str,
        session: Session = session_dependency,
    ) -> ProfessionalEvidenceRunReview:
        try:
            return review_professional_capture_evidence(session, run_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get(
        "/api/professional-intelligence/capture-runs/{run_id}/routing-summary",
        response_model=ProfessionalCaptureRoutingSummary,
    )
    def professional_capture_routing_summary(
        run_id: str,
        session: Session = session_dependency,
    ) -> ProfessionalCaptureRoutingSummary:
        try:
            return build_professional_capture_routing_summary(session, run_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/professional-intelligence/capture-runs/{run_id}/opportunity-candidates/import",
        response_model=ProfessionalOpportunityImportResult,
    )
    def professional_capture_opportunity_candidate_import(
        run_id: str,
        session: Session = session_dependency,
    ) -> ProfessionalOpportunityImportResult:
        try:
            return import_professional_opportunity_candidates(session, run_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get(
        "/api/professional-intelligence/capture-runs/{run_id}/structured-extraction",
        response_model=ProfessionalStructuredExtraction,
    )
    def professional_capture_structured_extraction(
        run_id: str,
        session: Session = session_dependency,
    ) -> ProfessionalStructuredExtraction:
        try:
            return extract_professional_intelligence(session, run_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post(
        "/api/professional-intelligence/capture-runs/{run_id}/authorize",
        response_model=ProfessionalCaptureRunResponse,
    )
    def authorize_professional_capture_preview(
        run_id: str,
        request: ProfessionalCaptureAuthorizationRequest,
        session: Session = session_dependency,
    ) -> ProfessionalCaptureRunResponse:
        try:
            return authorize_professional_capture_run(session, run_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post(
        "/api/professional-intelligence/capture-runs/{run_id}/start",
        response_model=ProfessionalCaptureRunResponse,
    )
    def start_professional_capture(
        run_id: str,
        background_tasks: BackgroundTasks,
        session: Session = session_dependency,
    ) -> ProfessionalCaptureRunResponse:
        try:
            run = get_professional_capture_run(session, run_id)
            if run.status != "authorized":
                raise ValueError("Only authorized capture runs can be started.")
            background_tasks.add_task(_run_professional_capture_background, get_session, run_id)
            return _queued_capture_response(run)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post(
        "/api/professional-intelligence/capture-runs/{run_id}/cancel",
        response_model=ProfessionalCaptureRunResponse,
    )
    def cancel_professional_capture_preview(
        run_id: str,
        session: Session = session_dependency,
    ) -> ProfessionalCaptureRunResponse:
        try:
            return cancel_professional_capture_run(session, run_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post(
        "/api/professional-intelligence/capture-runs/{run_id}/delete",
        response_model=ProfessionalCaptureDeletionResult,
    )
    def delete_professional_capture(
        run_id: str,
        request: ProfessionalCaptureDeletionRequest,
        session: Session = session_dependency,
    ) -> ProfessionalCaptureDeletionResult:
        try:
            return delete_professional_capture_run(session, run_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router
