from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
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
    id: str = "outcome-1"
    posting_id: str = "posting-1"
    application_id: str = "application-1"
    outcome_type: str = "rejected_by_employer"
    stage_reached: str = "technical_interview"
    reason_code: str = "skills_gap"
    notes: str = "Employer closed the process."
    recorded_at: datetime = datetime(2026, 8, 18, 18, 0, tzinfo=UTC)


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


def _patch_response(monkeypatch) -> None:
    monkeypatch.setattr(
        reversible,
        "build_application_response",
        lambda _session, value: SimpleNamespace(status=value.status),
    )


def test_application_can_move_backward_with_audited_event(monkeypatch) -> None:
    application = FakeApplication(status="technical_interview")
    session = FakeSession(application)
    _patch_response(monkeypatch)

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
    _patch_response(monkeypatch)

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

    prefix = "Preserved outcome JSON: "
    assert prefix in event.notes
    preserved = json.loads(event.notes.split(prefix, 1)[1])

    assert preserved == {
        "id": "outcome-1",
        "posting_id": "posting-1",
        "application_id": "application-1",
        "outcome_type": "rejected_by_employer",
        "stage_reached": "technical_interview",
        "reason_code": "skills_gap",
        "notes": "Employer closed the process.",
        "recorded_at": "2026-08-18T18:00:00+00:00",
    }
    assert session.committed is True


def test_selecting_the_current_stage_is_a_safe_no_op(monkeypatch) -> None:
    application = FakeApplication(status="submitted")
    session = FakeSession(application)
    _patch_response(monkeypatch)

    response = reversible.transition_application_reversibly(
        session,
        application.id,
        ApplicationTransitionRequest(status="submitted", notes="No change."),
    )

    assert response.status == "submitted"
    assert session.added == []
    assert session.deleted == []
    assert session.committed is False


def test_unknown_status_is_rejected_before_mutation(monkeypatch) -> None:
    application = FakeApplication(status="submitted")
    session = FakeSession(application)
    _patch_response(monkeypatch)

    try:
        reversible.transition_application_reversibly(
            session,
            application.id,
            ApplicationTransitionRequest.model_construct(status="invented", notes="Invalid."),
        )
    except ValueError as exc:
        assert str(exc) == "Unknown application status: invented."
    else:
        raise AssertionError("Unknown application status was accepted.")

    assert application.status == "submitted"
    assert session.added == []
    assert session.deleted == []
    assert session.committed is False
