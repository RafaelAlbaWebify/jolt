from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from jolt.application_resources import ContactRequest, DocumentRequest
from jolt.application_work_items import (
    InterviewCreateRequest,
    TaskCreateRequest,
    TaskUpdateRequest,
)
from jolt.database import create_session_factory, default_database_url
from jolt.reversible_application_workflow import transition_application_reversibly
from jolt.workflow import transition_application


def test_transition_boundary_is_explicit_wrapper_not_package_monkeypatch() -> None:
    assert transition_application is not transition_application_reversibly
    assert transition_application.__module__ == "jolt.workflow"


def test_default_database_path_is_project_stable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("JOLT_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    url = default_database_url()
    assert url.endswith("/data/jolt.db")
    assert str(tmp_path).replace("\\", "/") not in url


def test_sqlite_foreign_keys_are_enabled(tmp_path: Path) -> None:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'integrity.db').as_posix()}")
    with factory() as session:
        assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "INSERT INTO application_events "
                    "(id, application_id, event_type, from_status, to_status, notes, occurred_at) "
                    "VALUES ('event', 'missing', 'test', '', 'recorded', '', CURRENT_TIMESTAMP)"
                )
            )
            session.commit()


@pytest.mark.parametrize(
    ("factory", "payload"),
    [
        (TaskCreateRequest, {"title": "   "}),
        (TaskUpdateRequest, {"title": "   "}),
        (ContactRequest, {"name": "   "}),
        (DocumentRequest, {"document_type": "resume", "title": "   "}),
        (
            InterviewCreateRequest,
            {"interview_type": "recruiter_screen", "scheduled_at": "2026-07-26T12:00:00Z", "timezone": "   "},
        ),
    ],
)
def test_required_resource_text_rejects_whitespace(factory, payload) -> None:
    with pytest.raises(ValidationError):
        factory.model_validate(payload)
