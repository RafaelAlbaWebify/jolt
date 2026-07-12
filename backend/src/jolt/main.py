from collections.abc import Iterator
from io import BytesIO
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from jolt.analysis_pack import build_analysis_pack
from jolt.database import create_session_factory
from jolt.schemas import (
    ApplicationCreateRequest,
    ApplicationResponse,
    ApplicationTransitionRequest,
    IntakeResponse,
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
    list_opportunities,
    record_outcome,
    record_review,
    transition_application,
)

LOCAL_FRONTEND_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="JOLT API", version="0.5.0")
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
        return {"status": "ok", "service": "jolt-backend", "version": "0.5.0"}

    @app.post("/api/intake/manual", response_model=IntakeResponse, tags=["intake"])
    def manual_intake(
        request: ManualIntakeRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> IntakeResponse:
        return ingest_manual(session, request)

    @app.post(
        "/api/opportunities/{posting_id}/reviews",
        response_model=ReviewResponse,
        tags=["review"],
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

    @app.get("/api/opportunities", response_model=list[OpportunitySummary], tags=["opportunities"])
    def opportunities(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[OpportunitySummary]:
        return list_opportunities(session)

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
