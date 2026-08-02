from __future__ import annotations

from types import SimpleNamespace

import jolt.reversible_application_workflow as reversible
import jolt.workflow as workflow
from jolt.schemas import ApplicationTransitionRequest


def test_public_workflow_boundary_delegates_to_reversible_engine(monkeypatch) -> None:
    calls: list[tuple[object, str, ApplicationTransitionRequest]] = []
    expected = SimpleNamespace(status="submitted")

    def fake_transition(session, application_id, request):
        calls.append((session, application_id, request))
        return expected

    monkeypatch.setattr(reversible, "transition_application_reversibly", fake_transition)
    session = object()
    request = ApplicationTransitionRequest(status="submitted", notes="Submitted manually.")

    result = workflow.transition_application(session, "application-1", request)

    assert result is expected
    assert calls == [(session, "application-1", request)]


def test_reversible_engine_uses_response_module_instead_of_workflow_module() -> None:
    assert reversible.build_application_response.__module__ == "jolt.application_response"
    assert "_application_response" not in reversible.__dict__
