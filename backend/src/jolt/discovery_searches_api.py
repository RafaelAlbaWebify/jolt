from collections.abc import Callable, Iterator
from contextlib import suppress

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.discovery_execution import (
    DiscoveryExecutionCreateRequest,
    DiscoveryExecutionResponse,
    create_discovery_execution,
    execute_discovery_execution,
    get_discovery_execution,
    list_discovery_executions,
)
from jolt.discovery_searches import (
    DiscoverySavedSearchRequest,
    DiscoverySavedSearchResponse,
    DiscoverySource,
    DiscoverySourceResponse,
    create_discovery_search,
    delete_discovery_search,
    list_discovery_searches,
    list_discovery_sources,
    update_discovery_search,
)
from jolt.errors import JoltNotFoundError
from jolt.sources.confirmed_duplicates import (
    ConfirmDuplicateRequest,
    ConfirmDuplicateResponse,
    confirm_duplicate,
)
from jolt.sources.cross_portal_candidates import (
    CrossPortalDuplicateCandidate,
    list_cross_portal_duplicate_candidates,
)
from jolt.sources.posting_source_history import (
    PostingSourceHistoryResponse,
    get_posting_source_history,
)

SessionProvider = Callable[[], Iterator[Session]]


def _run_discovery_execution_background(
    get_session: SessionProvider,
    execution_id: str,
) -> None:
    session_iterator = get_session()
    session: Session | None = None
    try:
        session = next(session_iterator)
        execute_discovery_execution(session, execution_id)
    except Exception:
        if session is not None:
            session.rollback()
    finally:
        close = getattr(session_iterator, "close", None)
        if callable(close):
            with suppress(Exception):
                close()
        elif session is not None:
            with suppress(Exception):
                session.close()


def build_discovery_searches_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["discovery"])
    session_dependency = Depends(get_session)

    @router.post(
        "/api/discovery-confirm-duplicate",
        response_model=ConfirmDuplicateResponse,
    )
    def confirm_discovery_duplicate(
        request: ConfirmDuplicateRequest,
        session: Session = session_dependency,
    ) -> ConfirmDuplicateResponse:
        try:
            return confirm_duplicate(session, request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get(
        "/api/discovery-duplicate-candidates",
        response_model=list[CrossPortalDuplicateCandidate],
    )
    def discovery_duplicate_candidates(
        limit: int = 100,
        session: Session = session_dependency,
    ) -> list[CrossPortalDuplicateCandidate]:
        try:
            return list_cross_portal_duplicate_candidates(session, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get(
        "/api/discovery-postings/{posting_id}/source-history",
        response_model=PostingSourceHistoryResponse,
    )
    def discovery_posting_source_history(
        posting_id: str,
        limit: int = 100,
        session: Session = session_dependency,
    ) -> PostingSourceHistoryResponse:
        try:
            return get_posting_source_history(session, posting_id, limit=limit)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/api/discovery-sources", response_model=list[DiscoverySourceResponse])
    def discovery_sources() -> list[DiscoverySourceResponse]:
        return list_discovery_sources()

    @router.get("/api/discovery-searches", response_model=list[DiscoverySavedSearchResponse])
    def discovery_searches(
        source: DiscoverySource | None = None,
        session: Session = session_dependency,
    ) -> list[DiscoverySavedSearchResponse]:
        return list_discovery_searches(session, source=source)

    @router.post("/api/discovery-searches", response_model=DiscoverySavedSearchResponse)
    def add_discovery_search(
        request: DiscoverySavedSearchRequest,
        session: Session = session_dependency,
    ) -> DiscoverySavedSearchResponse:
        try:
            return create_discovery_search(session, request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post(
        "/api/discovery-searches/{saved_search_id}",
        response_model=DiscoverySavedSearchResponse,
    )
    def edit_discovery_search(
        saved_search_id: str,
        request: DiscoverySavedSearchRequest,
        session: Session = session_dependency,
    ) -> DiscoverySavedSearchResponse:
        try:
            return update_discovery_search(session, saved_search_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/api/discovery-searches/{saved_search_id}/delete")
    def remove_discovery_search(
        saved_search_id: str,
        session: Session = session_dependency,
    ) -> dict[str, bool]:
        try:
            delete_discovery_search(session, saved_search_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": True}

    @router.get(
        "/api/discovery-executions",
        response_model=list[DiscoveryExecutionResponse],
    )
    def discovery_executions(
        session: Session = session_dependency,
    ) -> list[DiscoveryExecutionResponse]:
        return list_discovery_executions(session)

    @router.post(
        "/api/discovery-executions",
        response_model=DiscoveryExecutionResponse,
    )
    def start_discovery_execution(
        request: DiscoveryExecutionCreateRequest,
        background_tasks: BackgroundTasks,
        session: Session = session_dependency,
    ) -> DiscoveryExecutionResponse:
        try:
            execution = create_discovery_execution(session, request)
            background_tasks.add_task(
                _run_discovery_execution_background,
                get_session,
                execution.id,
            )
            return execution
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get(
        "/api/discovery-executions/{execution_id}",
        response_model=DiscoveryExecutionResponse,
    )
    def discovery_execution(
        execution_id: str,
        session: Session = session_dependency,
    ) -> DiscoveryExecutionResponse:
        try:
            return get_discovery_execution(session, execution_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
