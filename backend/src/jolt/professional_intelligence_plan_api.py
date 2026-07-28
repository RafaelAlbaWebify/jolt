from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.professional_intelligence_bounded_capture import (
    start_bounded_professional_capture,
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
from jolt.professional_intelligence_retention import (
    ProfessionalRetentionCleanupRequest,
    ProfessionalRetentionCleanupResult,
    ProfessionalRetentionPreview,
    cleanup_expired_professional_evidence,
    preview_professional_retention_cleanup,
)
from jolt.professional_intelligence_structured_extraction import (
    ProfessionalStructuredExtraction,
    extract_professional_intelligence,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_professional_intelligence_plan_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["professional-intelligence"])
    session_dependency = Depends(get_session)

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
        except LookupError as exc:
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
        request: ProfessionalCaptureCreateRequest,
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
        except LookupError as exc:
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
        except LookupError as exc:
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
        except LookupError as exc:
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
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post(
        "/api/professional-intelligence/capture-runs/{run_id}/start",
        response_model=ProfessionalCaptureRunResponse,
    )
    def start_professional_capture(
        run_id: str,
        session: Session = session_dependency,
    ) -> ProfessionalCaptureRunResponse:
        try:
            return start_bounded_professional_capture(session, run_id)
        except LookupError as exc:
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
        except LookupError as exc:
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
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router
