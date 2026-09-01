from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from jolt.database import create_session_factory
from jolt.review_inbox_exchange_api import build_review_inbox_exchange_router


def test_review_inbox_exchange_export_returns_404_without_capture(tmp_path) -> None:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")

    def get_session() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app = FastAPI()
    app.include_router(build_review_inbox_exchange_router(get_session))
    client = TestClient(app)

    response = client.get("/api/exports/review-inbox-ai-exchange")

    assert response.status_code == 404
    assert "No capture run exists" in response.json()["detail"]
