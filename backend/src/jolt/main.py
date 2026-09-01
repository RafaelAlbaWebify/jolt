from collections.abc import Iterator
from io import BytesIO
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from jolt.ai_review_import import (
    AIReviewImportRequest,
    AIReviewImportResponse,
    import_ai_review,
)
from jolt.ai_review_opportunity_index import (
    AIReviewOpportunityIndexItem,
    list_ai_review_opportunity_index,
)
from jolt.ai_review_pack import build_ai_review_json, build_ai_review_pack
from jolt.application_archival import (
    ApplicationArchiveRequest,
    ApplicationArchiveResponse,
    archive_application_card,
    restore_application_card,
)
from jolt.application_cleanup import (
    ApplicationDeleteResponse,
    delete_archived_application,
)
from jolt.application_preparation_pack import (
    PreparationPackPostingNotFound,
    build_application_preparation_pack,
)
from jolt.application_work_items_api import build_application_work_items_router
from jolt.automated_review import ensure_automated_reviews
from jolt.capture_analysis_pack import build_analysis_pack
from jolt.capture_archival import CaptureBatchArchiveResult, archive_capture_run
from jolt.capture_workflow import get_capture_run, list_capture_runs, run_linkedin_fixture_capture
from jolt.database import create_session_factory
from jolt.errors import JoltNotFoundError
from jolt.identity_evidence import list_identity_evidence, opportunity_identity_evidence
from jolt.job_search_preferences import (
    JobSearchPreferences,
    load_job_search_preferences,
    save_job_search_preferences,
)
from jolt.linkedin_command_center import (
    LinkedInCaptureRequest,
    LinkedInCaptureResponse,
    LinkedInCommandCenterResponse,
    LinkedInRecommendationImportRequest,
    LinkedInRecommendationImportResponse,
    LinkedInRecommendationRequest,
    LinkedInRecommendationResponse,
    LinkedInRecommendationStatusRequest,
    build_linkedin_analysis_pack,
    create_linkedin_capture,
    create_linkedin_recommendation,
    import_linkedin_recommendations,
    list_linkedin_command_center,
    update_linkedin_recommendation_status,
)
from jolt.linkedin_playwright_capture import (
    LinkedInPlaywrightBatchCaptureRequest,
    LinkedInPlaywrightBatchCaptureResponse,
    LinkedInPlaywrightCaptureRequest,
    run_linkedin_playwright_batch_capture,
    run_linkedin_playwright_capture,
)
from jolt.live_capture_workflow import run_linkedin_live_capture
from jolt.market_intelligence import build_market_intelligence
from jolt.market_preparation_import import (
    MarketPreparationImportIndex,
    MarketPreparationImportRequest,
    MarketPreparationImportResponse,
    import_market_preparation,
    list_market_preparation_imports,
)
from jolt.market_preparation_pack import build_market_preparation_pack
from jolt.opportunity_index import OpportunityIndexItem, list_opportunity_index
from jolt.opportunity_workbench import get_opportunity_workbench, list_opportunity_workbench
from jolt.pending_inbox_cleanup import (
    PendingInboxClearResponse,
    clear_pending_review_inbox,
)
from jolt.professional_intelligence_plan_api import build_professional_intelligence_plan_router
from jolt.readiness_workflow import list_readiness_history, refresh_readiness_report
from jolt.retention_ownership import (
    RetentionOwnershipPreview,
    build_retention_ownership_preview,
)
from jolt.review_pack import build_review_pack
from jolt.runtime_identity import RuntimeIdentityResponse, build_runtime_identity
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
from jolt.strategy_runtime import (
    ENGINE_VERSION,
    ensure_strategy_reviews,
    load_active_strategy_profile,
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

    app.include_router(build_application_work_items_router(get_session))
    app.include_router(build_professional_intelligence_plan_router(get_session))

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "jolt-backend", "version": "0.8.0"}

    @app.get("/api/runtime-identity", response_model=RuntimeIdentityResponse, tags=["system"])
    def runtime_identity(
        session: Annotated[Session, Depends(get_session)],
    ) -> RuntimeIdentityResponse:
        return build_runtime_identity(session)

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
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/captures/{capture_run_id}/archive",
        response_model=CaptureBatchArchiveResult,
        tags=["captures"],
    )
    def archive_capture_batch(
        capture_run_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> CaptureBatchArchiveResult:
        try:
            return archive_capture_run(session, capture_run_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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
        except JoltNotFoundError as exc:
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
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/opportunities/{posting_id}/readiness/history", tags=["readiness"])
    def readiness_history(
        posting_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> list[dict[str, object]]:
        try:
            return list_readiness_history(session, posting_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/opportunities/{posting_id}/readiness/refresh", tags=["readiness"])
    def refresh_readiness(
        posting_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, object]:
        try:
            return refresh_readiness_report(session, posting_id)
        except JoltNotFoundError as exc:
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
        except JoltNotFoundError as exc:
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
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/applications/{application_id}/archive",
        response_model=ApplicationArchiveResponse,
        tags=["applications"],
    )
    def archive_application(
        application_id: str,
        request: ApplicationArchiveRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> ApplicationArchiveResponse:
        try:
            return archive_application_card(session, application_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/applications/{application_id}/restore",
        response_model=ApplicationArchiveResponse,
        tags=["applications"],
    )
    def restore_application(
        application_id: str,
        request: ApplicationArchiveRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> ApplicationArchiveResponse:
        try:
            return restore_application_card(session, application_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/applications/{application_id}/delete",
        response_model=ApplicationDeleteResponse,
        tags=["applications"],
    )
    def delete_application(
        application_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> ApplicationDeleteResponse:
        try:
            return delete_archived_application(session, application_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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
        except JoltNotFoundError as exc:
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
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/review-inbox/clear-pending",
        response_model=PendingInboxClearResponse,
        tags=["opportunities"],
    )
    def clear_pending_inbox(
        session: Annotated[Session, Depends(get_session)],
    ) -> PendingInboxClearResponse:
        return clear_pending_review_inbox(session)

    @app.post("/api/evaluations/refresh", tags=["opportunities"])
    def refresh_evaluations(
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, object]:
        ensure_automated_reviews(session)
        profile = load_active_strategy_profile()
        assessments = ensure_strategy_reviews(session, profile) if profile is not None else {}
        return {
            "status": "refreshed",
            "authoritative_engine": ENGINE_VERSION if profile is not None else "profile-rules-v2",
            "strategy_evaluation_count": len(assessments),
        }

    @app.get(
        "/api/opportunity-index", response_model=list[OpportunityIndexItem], tags=["opportunities"]
    )
    def opportunity_index(
        session: Annotated[Session, Depends(get_session)],
        include_reviewed: bool = False,
    ) -> list[OpportunityIndexItem]:
        return list_opportunity_index(session, include_reviewed=include_reviewed)

    @app.get(
        "/api/ai-review/opportunity-index",
        response_model=list[AIReviewOpportunityIndexItem],
        tags=["ai-review"],
    )
    def ai_review_opportunity_index(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[AIReviewOpportunityIndexItem]:
        return list_ai_review_opportunity_index(session)

    @app.get(
        "/api/application-index", response_model=list[OpportunityIndexItem], tags=["applications"]
    )
    def application_index(
        session: Annotated[Session, Depends(get_session)],
        include_archived: bool = False,
    ) -> list[OpportunityIndexItem]:
        return list_opportunity_index(
            session, include_applied=True, include_archived=include_archived
        )

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
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/data-management/retention-preview",
        response_model=RetentionOwnershipPreview,
        tags=["data-management"],
    )
    def retention_preview(
        session: Annotated[Session, Depends(get_session)],
    ) -> RetentionOwnershipPreview:
        return build_retention_ownership_preview(session)

    @app.get("/api/market-intelligence", tags=["analysis"])
    def market_intelligence(
        session: Annotated[Session, Depends(get_session)],
        timeframe: str = "all",
        source_scope: str = "all",
    ) -> dict[str, object]:
        return build_market_intelligence(session, timeframe=timeframe, source_scope=source_scope)

    @app.get(
        "/api/job-search-preferences",
        response_model=JobSearchPreferences,
        tags=["preferences"],
    )
    def job_search_preferences() -> JobSearchPreferences:
        return load_job_search_preferences()

    @app.post(
        "/api/job-search-preferences",
        response_model=JobSearchPreferences,
        tags=["preferences"],
    )
    def update_job_search_preferences(
        request: JobSearchPreferences,
    ) -> JobSearchPreferences:
        return save_job_search_preferences(request)

    @app.get(
        "/api/market-intelligence/preparation-pack",
        tags=["exports"],
    )
    def market_preparation_pack(
        session: Annotated[Session, Depends(get_session)],
    ) -> StreamingResponse:
        content = build_market_preparation_pack(session)
        return StreamingResponse(
            BytesIO(content),
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=JOLT_MARKET_LINKEDIN_PREPARATION.zip"
            },
        )

    @app.get(
        "/api/market-intelligence/preparation-import",
        response_model=MarketPreparationImportIndex,
        tags=["analysis"],
    )
    def market_preparation_imports() -> MarketPreparationImportIndex:
        return list_market_preparation_imports()

    @app.post(
        "/api/market-intelligence/preparation-import",
        response_model=MarketPreparationImportResponse,
        tags=["analysis"],
    )
    def import_market_preparation_result(
        request: MarketPreparationImportRequest,
    ) -> MarketPreparationImportResponse:
        return import_market_preparation(request)

    @app.get(
        "/api/linkedin-command-center",
        response_model=LinkedInCommandCenterResponse,
        tags=["linkedin-command-center"],
    )
    def linkedin_command_center(
        session: Annotated[Session, Depends(get_session)],
    ) -> LinkedInCommandCenterResponse:
        return list_linkedin_command_center(session)

    @app.post(
        "/api/linkedin-command-center/captures",
        response_model=LinkedInCaptureResponse,
        tags=["linkedin-command-center"],
    )
    def create_linkedin_presence_capture(
        request: LinkedInCaptureRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> LinkedInCaptureResponse:
        return create_linkedin_capture(session, request)

    @app.post(
        "/api/linkedin-command-center/captures/playwright",
        response_model=LinkedInCaptureResponse,
        tags=["linkedin-command-center"],
    )
    def create_linkedin_playwright_capture(
        request: LinkedInPlaywrightCaptureRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> LinkedInCaptureResponse:
        try:
            return run_linkedin_playwright_capture(session, request)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/linkedin-command-center/captures/playwright-batch",
        response_model=LinkedInPlaywrightBatchCaptureResponse,
        tags=["linkedin-command-center"],
    )
    def create_linkedin_playwright_batch_capture(
        request: LinkedInPlaywrightBatchCaptureRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> LinkedInPlaywrightBatchCaptureResponse:
        try:
            return run_linkedin_playwright_batch_capture(session, request)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/linkedin-command-center/recommendations",
        response_model=LinkedInRecommendationResponse,
        tags=["linkedin-command-center"],
    )
    def create_linkedin_presence_recommendation(
        request: LinkedInRecommendationRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> LinkedInRecommendationResponse:
        try:
            return create_linkedin_recommendation(session, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/linkedin-command-center/recommendations/import",
        response_model=LinkedInRecommendationImportResponse,
        tags=["linkedin-command-center"],
    )
    def import_linkedin_presence_recommendations(
        request: LinkedInRecommendationImportRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> LinkedInRecommendationImportResponse:
        try:
            return import_linkedin_recommendations(session, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/linkedin-command-center/recommendations/{recommendation_id}/status",
        response_model=LinkedInRecommendationResponse,
        tags=["linkedin-command-center"],
    )
    def set_linkedin_recommendation_status(
        recommendation_id: str,
        request: LinkedInRecommendationStatusRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> LinkedInRecommendationResponse:
        try:
            return update_linkedin_recommendation_status(session, recommendation_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

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
        except PreparationPackPostingNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        filename = f"JOLT_PREPARATION_{posting_id}.zip"
        return StreamingResponse(
            BytesIO(content),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.post(
        "/api/ai-review/import",
        response_model=AIReviewImportResponse,
        tags=["ai-review"],
    )
    def ai_review_import(
        request: AIReviewImportRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> AIReviewImportResponse:
        try:
            return import_ai_review(session, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/exports/ai-review-pack", tags=["exports"])
    def ai_review_pack(
        session: Annotated[Session, Depends(get_session)],
    ) -> StreamingResponse:
        try:
            content = build_ai_review_pack(session)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return StreamingResponse(
            BytesIO(content),
            media_type="application/zip",
            headers={"Content-Disposition": ("attachment; filename=JOLT_AI_REVIEW_INPUT.zip")},
        )

    @app.get("/api/exports/ai-review-json", tags=["exports"])
    def ai_review_json(
        session: Annotated[Session, Depends(get_session)],
    ) -> StreamingResponse:
        try:
            content = build_ai_review_json(session)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return StreamingResponse(
            BytesIO(content),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=JOLT_AI_REVIEW_INPUT.json"},
        )

    @app.get("/api/exports/review-pack", tags=["exports"])
    def review_pack(
        session: Annotated[Session, Depends(get_session)],
    ) -> StreamingResponse:
        try:
            content = build_review_pack(session)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return StreamingResponse(
            BytesIO(content),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=JOLT_REVIEW_PACK.zip"},
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

    @app.get("/api/linkedin-command-center/export", tags=["exports"])
    def linkedin_analysis_pack(
        session: Annotated[Session, Depends(get_session)],
    ) -> StreamingResponse:
        content = build_linkedin_analysis_pack(session)
        return StreamingResponse(
            BytesIO(content),
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=JOLT_LINKEDIN_COMMAND_CENTER.zip"
            },
        )

    return app


app = create_app()
