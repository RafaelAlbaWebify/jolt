from collections.abc import Iterator
from io import BytesIO
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from jolt.application_preparation_pack import build_application_preparation_pack
from jolt.capture_analysis_pack import build_analysis_pack
from jolt.capture_workflow import get_capture_run, list_capture_runs, run_linkedin_fixture_capture
from jolt.database import create_session_factory
from jolt.identity_evidence import list_identity_evidence, opportunity_identity_evidence
from jolt.live_capture_workflow import run_linkedin_live_capture
from jolt.market_intelligence import build_market_intelligence
from jolt.opportunity_index import OpportunityIndexItem, list_opportunity_index
from jolt.opportunity_workbench import get_opportunity_workbench, list_opportunity_workbench
from jolt.readiness_workflow import list_readiness_history, refresh_readiness_report
from jolt.schemas import (
    ApplicationCreateRequest,
    ApplicationResponse,
    ApplicationTransitionRequest,
    CaptureRunResponse,
    CaptureRunSummary,
    IntakeResponse,
    LinkedInFixtureCaptureRequest,
    LinkedInLiveCaptureRequest,
    ManualIntakeRequest,
    OpportunitySummary,
    OutcomeRequest,
    ReviewRequest,
    ReviewResponse,
)
from jolt.workflow import (
    create_application,
    get_application,
    ingest_manual,
    record_outcome,
    record_review,
    transition_application,
)

LOCAL_FRONTEND_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="JOLT API", version="0.8.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_FRONTEND_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    session_factory = create_session_factory(database_url)

    def get_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "jolt-backend", "version": "0.8.0"}

    @app.post("/api/intake/manual", response_model=IntakeResponse, tags=["intake"])
    def manual_intake(
        request: ManualIntakeRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> IntakeResponse:
        return ingest_manual(session, request)

    @app.post(
        "/api/captures/linkedin/fixture", response_model=CaptureRunResponse, tags=["captures"]
    )
    def linkedin_fixture_capture(
        request: LinkedInFixtureCaptureRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> CaptureRunResponse:
        return run_linkedin_fixture_capture(session, request)

    @app.post("/api/captures/linkedin/live", response_model=CaptureRunResponse, tags=["captures"])
    def linkedin_live_capture(
        request: LinkedInLiveCaptureRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> CaptureRunResponse:
        return run_linkedin_live_capture(session, request)

    @app.get("/api/captures", response_model=list[CaptureRunSummary], tags=["captures"])
    def capture_history(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[CaptureRunSummary]:
        return list_capture_runs(session)

    @app.get("/api/captures/{capture_run_id}", response_model=CaptureRunResponse, tags=["captures"])
    def capture_run(
        capture_run_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> CaptureRunResponse:
        try:
            return get_capture_run(session, capture_run_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/opportunities/{posting_id}/reviews", response_model=ReviewResponse, tags=["review"]
    )
    def create_review(
        posting_id: str,
        request: ReviewRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> ReviewResponse:
        try:
            return record_review(session, posting_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/identity-evidence", tags=["identity"])
    def identity_evidence_index(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[dict[str, object]]:
        return list_identity_evidence(session)

    @app.get("/api/opportunities/{posting_id}/identity-evidence", tags=["identity"])
    def identity_evidence(
        posting_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, object]:
        try:
            return opportunity_identity_evidence(session, posting_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/opportunities/{posting_id}/readiness/history", tags=["readiness"])
    def readiness_history(
        posting_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> list[dict[str, object]]:
        try:
            return list_readiness_history(session, posting_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/opportunities/{posting_id}/readiness/refresh", tags=["readiness"])
    def refresh_readiness(
        posting_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, object]:
        try:
            return refresh_readiness_report(session, posting_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/opportunities/{posting_id}/applications",
        response_model=ApplicationResponse,
        tags=["applications"],
    )
    def start_application(
        posting_id: str,
        request: ApplicationCreateRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> ApplicationResponse:
        try:
            return create_application(session, posting_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/applications/{application_id}",
        response_model=ApplicationResponse,
        tags=["applications"],
    )
    def application(
        application_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> ApplicationResponse:
        try:
            return get_application(session, application_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/applications/{application_id}/transitions",
        response_model=ApplicationResponse,
        tags=["applications"],
    )
    def change_application_status(
        application_id: str,
        request: ApplicationTransitionRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> ApplicationResponse:
        try:
            return transition_application(session, application_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/applications/{application_id}/outcomes",
        response_model=ApplicationResponse,
        tags=["applications"],
    )
    def save_outcome(
        application_id: str,
        request: OutcomeRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> ApplicationResponse:
        try:
            return record_outcome(session, application_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/opportunity-index", response_model=list[OpportunityIndexItem], tags=["opportunities"]
    )
    def opportunity_index(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[OpportunityIndexItem]:
        return list_opportunity_index(session)

    @app.get(
        "/api/application-index", response_model=list[OpportunityIndexItem], tags=["applications"]
    )
    def application_index(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[OpportunityIndexItem]:
        return list_opportunity_index(session, include_applied=True)

    @app.get(
        "/api/opportunity-detail/{posting_id}",
        response_model=OpportunitySummary,
        tags=["opportunities"],
    )
    def opportunity_detail(
        posting_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> OpportunitySummary:
        try:
            return get_opportunity_workbench(session, posting_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/market-intelligence", tags=["analysis"])
    def market_intelligence(
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, object]:
        return build_market_intelligence(session)

    @app.get("/api/opportunities", response_model=list[OpportunitySummary], tags=["opportunities"])
    def opportunities(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[OpportunitySummary]:
        return list_opportunity_workbench(session)

    @app.get("/api/opportunities/{posting_id}/preparation-pack", tags=["exports"])
    def preparation_pack(
        posting_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> StreamingResponse:
        try:
            content = build_application_preparation_pack(session, posting_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        filename = f"JOLT_PREPARATION_{posting_id}.zip"
        return StreamingResponse(
            BytesIO(content),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.get("/api/exports/analysis-pack", tags=["exports"])
    def analysis_pack(
        session: Annotated[Session, Depends(get_session)],
    ) -> StreamingResponse:
        content = build_analysis_pack(session)
        return StreamingResponse(
            BytesIO(content),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=JOLT_ANALYSIS_PACK.zip"},
        )

    return app


app = create_app()
