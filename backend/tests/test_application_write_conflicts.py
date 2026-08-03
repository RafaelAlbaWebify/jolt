from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

import jolt.workflow as workflow
from jolt.schemas import ApplicationCreateRequest, OutcomeRequest


@dataclass
class FakePosting:
    id: str = "posting-1"


@dataclass
class FakeReview:
    decision: str = "pursue"


@dataclass
class FakeApplication:
    id: str = "application-1"
    posting_id: str = "posting-1"
    status: str = "preparing"
    application_url: str = ""
    resume_used: str = ""
    notes: str = ""
    updated_at: object | None = None


@dataclass
class FakeOutcome:
    id: str = "outcome-1"


class FakeSession:
    def __init__(
        self,
        *,
        scalar_results: list[object | None],
        flush_error: IntegrityError | None = None,
        commit_error: IntegrityError | None = None,
    ) -> None:
        self.scalar_results = list(scalar_results)
        self.flush_error = flush_error
        self.commit_error = commit_error
        self.added: list[object] = []
        self.rollback_count = 0
        self.commit_count = 0

    def get(self, model: object, identity: str) -> object | None:
        del model
        if identity == "posting-1":
            return FakePosting()
        if identity == "application-1":
            return FakeApplication()
        return None

    def scalar(self, statement: object) -> object | None:
        del statement
        return self.scalar_results.pop(0)

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        if self.flush_error is not None:
            error = self.flush_error
            self.flush_error = None
            raise error

    def commit(self) -> None:
        self.commit_count += 1
        if self.commit_error is not None:
            error = self.commit_error
            self.commit_error = None
            raise error

    def rollback(self) -> None:
        self.rollback_count += 1


def unique_error() -> IntegrityError:
    return IntegrityError("insert", {}, RuntimeError("unique constraint"))


def test_application_creation_recovers_winning_row_after_flush_race(monkeypatch) -> None:
    winner = FakeApplication(id="winner-application")
    session = FakeSession(
        scalar_results=[FakeReview(), None, winner],
        flush_error=unique_error(),
    )
    monkeypatch.setattr(
        workflow,
        "build_application_response",
        lambda _session, application: SimpleNamespace(application_id=application.id),
    )

    response = workflow.create_application(
        session,
        "posting-1",
        ApplicationCreateRequest(notes="Prepare application."),
    )

    assert response.application_id == "winner-application"
    assert session.rollback_count == 1
    assert session.commit_count == 0


def test_application_creation_reraises_unrelated_integrity_error(monkeypatch) -> None:
    session = FakeSession(
        scalar_results=[FakeReview(), None, None],
        flush_error=unique_error(),
    )
    monkeypatch.setattr(
        workflow,
        "build_application_response",
        lambda _session, application: SimpleNamespace(application_id=application.id),
    )

    with pytest.raises(IntegrityError):
        workflow.create_application(session, "posting-1", ApplicationCreateRequest())

    assert session.rollback_count == 1


def test_outcome_race_becomes_existing_outcome_conflict() -> None:
    session = FakeSession(
        scalar_results=[None, FakeOutcome()],
        commit_error=unique_error(),
    )

    with pytest.raises(ValueError, match="already has an outcome"):
        workflow.record_outcome(
            session,
            "application-1",
            OutcomeRequest(outcome_type="rejected_by_employer"),
        )

    assert session.rollback_count == 1
    assert session.commit_count == 1


def test_outcome_reraises_unrelated_integrity_error() -> None:
    session = FakeSession(
        scalar_results=[None, None],
        commit_error=unique_error(),
    )

    with pytest.raises(IntegrityError):
        workflow.record_outcome(
            session,
            "application-1",
            OutcomeRequest(outcome_type="rejected_by_employer"),
        )

    assert session.rollback_count == 1
