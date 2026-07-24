from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.professional_intelligence_capture_plan import (
    ProfessionalCapturePlan,
    build_professional_capture_plan,
)
from jolt.professional_intelligence_capture_runs import (
    ProfessionalCaptureAuthorizationRequest,
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
    def professional_intelligence_execution_readiness() -> ProfessionalExecutionReadiness:
        return professional_execution_readiness()

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

    @router.post(
        "/api/professional-intelligence/capture-runs",
        response_model=ProfessionalCaptureRunResponse,
    )
    def record_professional_capture_preview(
        session: Session = session_dependency,
    ) -> ProfessionalCaptureRunResponse:
        return create_professional_capture_preview_run(session)

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

    return router
