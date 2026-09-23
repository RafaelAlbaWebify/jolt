from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from jolt.errors import JoltNotFoundError
from jolt.linkedin_search_portfolio import (
    DiscoveryBatchCreateRequest,
    DiscoveryBatchResponse,
    SavedLinkedInSearchRequest,
    SavedLinkedInSearchResponse,
    create_discovery_batch,
    create_saved_linkedin_search,
    delete_saved_linkedin_search,
    get_discovery_batch,
    get_saved_linkedin_search,
    list_discovery_batches,
    list_saved_linkedin_searches,
    update_saved_linkedin_search,
)

SessionProvider = Callable[[], Iterator[Session]]


def build_linkedin_search_portfolio_router(get_session: SessionProvider) -> APIRouter:
    router = APIRouter(tags=["linkedin-search-portfolio"])
    session_dependency = Depends(get_session)

    @router.get(
        "/api/linkedin-searches",
        response_model=list[SavedLinkedInSearchResponse],
    )
    def saved_linkedin_searches(
        session: Session = session_dependency,
    ) -> list[SavedLinkedInSearchResponse]:
        return list_saved_linkedin_searches(session)

    @router.post(
        "/api/linkedin-searches",
        response_model=SavedLinkedInSearchResponse,
    )
    def add_saved_linkedin_search(
        request: SavedLinkedInSearchRequest,
        session: Session = session_dependency,
    ) -> SavedLinkedInSearchResponse:
        try:
            return create_saved_linkedin_search(session, request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get(
        "/api/linkedin-searches/{saved_search_id}",
        response_model=SavedLinkedInSearchResponse,
    )
    def saved_linkedin_search(
        saved_search_id: str,
        session: Session = session_dependency,
    ) -> SavedLinkedInSearchResponse:
        try:
            return get_saved_linkedin_search(session, saved_search_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post(
        "/api/linkedin-searches/{saved_search_id}",
        response_model=SavedLinkedInSearchResponse,
    )
    def edit_saved_linkedin_search(
        saved_search_id: str,
        request: SavedLinkedInSearchRequest,
        session: Session = session_dependency,
    ) -> SavedLinkedInSearchResponse:
        try:
            return update_saved_linkedin_search(session, saved_search_id, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/api/linkedin-searches/{saved_search_id}/delete")
    def remove_saved_linkedin_search(
        saved_search_id: str,
        session: Session = session_dependency,
    ) -> dict[str, bool]:
        try:
            delete_saved_linkedin_search(session, saved_search_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"deleted": True}

    @router.get(
        "/api/linkedin-discovery-batches",
        response_model=list[DiscoveryBatchResponse],
    )
    def discovery_batches(
        session: Session = session_dependency,
    ) -> list[DiscoveryBatchResponse]:
        return list_discovery_batches(session)

    @router.post(
        "/api/linkedin-discovery-batches",
        response_model=DiscoveryBatchResponse,
    )
    def add_discovery_batch(
        request: DiscoveryBatchCreateRequest,
        session: Session = session_dependency,
    ) -> DiscoveryBatchResponse:
        try:
            return create_discovery_batch(session, request)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get(
        "/api/linkedin-discovery-batches/{batch_id}",
        response_model=DiscoveryBatchResponse,
    )
    def discovery_batch(
        batch_id: str,
        session: Session = session_dependency,
    ) -> DiscoveryBatchResponse:
        try:
            return get_discovery_batch(session, batch_id)
        except JoltNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
