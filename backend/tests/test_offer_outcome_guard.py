from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from jolt.api import create_app
from jolt.database import Application, Posting, SourceDocument, create_session_factory
from jolt.schemas import OutcomeRequest
from jolt.workflow import record_outcome


class GuardSession:
    def __init__(self, application: Application) -> None:
        self.application = application
        self.added: list[object] = []
        self.committed = False

    def get(self, model: object, application_id: str) -> Application | None:
        del model
        return self.application if application_id == self.application.id else None

    def scalar(self, statement: object) -> None:
        del statement
        return None

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.committed = True


@pytest.mark.parametrize("outcome_type", ["offer_accepted", "offer_declined"])
def test_offer_outcome_requires_offer_stage_without_mutation(outcome_type: str) -> None:
    now = datetime.now(UTC)
    application = Application(
        id="application-1",
        posting_id="posting-1",
        status="recruiter_screen",
        application_url="",
        resume_used="",
        notes="",
        created_at=now,
        updated_at=now,
    )
    session = GuardSession(application)

    with pytest.raises(
        ValueError,
        match="Offer outcomes can only be recorded from the offer stage",
    ):
        record_outcome(
            session,  # type: ignore[arg-type]
            application.id,
            OutcomeRequest(outcome_type=outcome_type),  # type: ignore[arg-type]
        )

    assert application.status == "recruiter_screen"
    assert application.updated_at == now
    assert session.added == []
    assert session.committed is False


def test_offer_outcome_api_returns_conflict_before_offer_stage(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'offer-guard.db').as_posix()}"
    factory = create_session_factory(database_url)
    now = datetime.now(UTC)
    with factory() as session:
        source = SourceDocument(
            id="source-1",
            source_type="manual",
            source_url="",
            raw_text="Role\nCompany",
            content_hash="a" * 64,
            captured_at=now,
        )
        session.add(source)
        session.flush()

        posting = Posting(
            id="posting-1",
            source_document_id=source.id,
            canonical_url="",
            identity_key="hash:" + "a" * 64,
            title="Role",
            company="Company",
            location="",
            description="Role",
            identity_status="new",
            created_at=now,
        )
        session.add(posting)
        session.flush()

        application = Application(
            id="application-1",
            posting_id=posting.id,
            status="preparing",
            application_url="",
            resume_used="",
            notes="",
            created_at=now,
            updated_at=now,
        )
        session.add(application)
        session.commit()

    client = TestClient(create_app(database_url))
    response = client.post(
        "/api/applications/application-1/outcomes",
        json={"outcome_type": "offer_accepted", "reason_code": "", "notes": ""},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Offer outcomes can only be recorded from the offer stage."
    }

    with factory() as session:
        persisted = session.get(Application, "application-1")
        assert persisted is not None
        assert persisted.status == "preparing"
