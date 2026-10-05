from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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

SessionProvider = Callable[[], Iterator[Session]]


def build_discovery_searches_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["discovery"])
    session_dependency = Depends(get_session)

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

    @router.post(\n        "/api/discovery-searches/{saved_search_id}", response_model=DiscoverySavedSearchResponse\n    )
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

    return router
