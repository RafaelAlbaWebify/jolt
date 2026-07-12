from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from jolt.database import create_session_factory
from jolt.schemas import (
    IntakeResponse,
    ManualIntakeRequest,
    OpportunitySummary,
    ReviewRequest,
    ReviewResponse,
)
from jolt.workflow import ingest_manual, list_opportunities, record_review

LOCAL_FRONTEND_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="JOLT API", version="0.3.0")
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
        return {"status": "ok", "service": "jolt-backend", "version": "0.3.0"}

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

    @app.get("/api/opportunities", response_model=list[OpportunitySummary], tags=["opportunities"])
    def opportunities(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[OpportunitySummary]:
        return list_opportunities(session)

    return app


app = create_app()
