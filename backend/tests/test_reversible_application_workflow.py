from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import jolt.reversible_application_workflow as reversible
from jolt.schemas import ApplicationTransitionRequest


@dataclass
class FakeApplication:
    id: str = "application-1"
    status: str = "technical_interview"
    updated_at: object | None = None


@dataclass
class FakeOutcome:
    outcome_type: str = "rejected_by_employer"
    reason_code: str = "skills_gap"
    notes: str = "Employer closed the process."


class FakeSession:
    def __init__(self, application: FakeApplication, outcome: FakeOutcome | None = None) -> None:
        self.application = application
        self.outcome = outcome
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.committed = False

    def get(self, model: object, application_id: str) -> FakeApplication | None:
        del model
        return self.application if application_id == self.application.id else None

    def scalar(self, statement: object) -> FakeOutcome | None:
        del statement
        return self.outcome

    def add(self, value: object) -> None:
        self.added.append(value)

    def delete(self, value: object) -> None:
        self.deleted.append(value)
        self.outcome = None

    def commit(self) -> None:
        self.committed = True


def test_application_can_move_backward_with_audited_event(monkeypatch) -> None:
    application = FakeApplication(status="technical_interview")
    session = FakeSession(application)
    monkeypatch.setattr(
        reversible,
        "_application_response",
        lambda _session, value: SimpleNamespace(status=value.status),
    )

    response = reversible.transition_application_reversibly(
        session,
        application.id,
        ApplicationTransitionRequest(status="recruiter_screen", notes="Corrected stage."),
    )

    assert response.status == "recruiter_screen"
    event = session.added[-1]
    assert event.event_type == "status_changed"
    assert event.from_status == "technical_interview"
    assert event.to_status == "recruiter_screen"
    assert event.notes == "Corrected stage."
    assert session.committed is True


def test_closed_application_can_reopen_and_preserve_outcome_in_history(monkeypatch) -> None:
    application = FakeApplication(status="rejected")
    outcome = FakeOutcome()
    session = FakeSession(application, outcome)
    monkeypatch.setattr(
        reversible,
        "_application_response",
        lambda _session, value: SimpleNamespace(status=value.status),
    )

    response = reversible.transition_application_reversibly(
        session,
        application.id,
        ApplicationTransitionRequest(status="submitted", notes="Employer reopened the role."),
    )

    assert response.status == "submitted"
    assert session.deleted == [outcome]
    event = session.added[-1]
    assert event.event_type == "application_reopened"
    assert event.from_status == "rejected"
    assert event.to_status == "submitted"
    assert "Previous outcome: rejected_by_employer." in event.notes
    assert "Reason: skills_gap." in event.notes
    assert "Employer closed the process." in event.notes
    assert session.committed is True
