from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected marker not found: {label}")
    return text.replace(old, new, 1)


def replace_block(text: str, start: str, end: str, replacement: str, label: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise RuntimeError(f"Expected start marker not found: {label}")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"Expected end marker not found: {label}")
    return text[:start_index] + replacement + text[end_index:]


def patch_package_init(root: Path) -> None:
    path = root / "backend/src/jolt/__init__.py"
    path.write_text('"""JOLT backend package."""\n', encoding="utf-8")


def patch_workflow(root: Path) -> None:
    path = root / "backend/src/jolt/workflow.py"
    text = path.read_text(encoding="utf-8")
    if "from jolt.url_identity import canonicalize_source_url" not in text:
        text = replace_once(
            text,
            "from jolt.schemas import (\n",
            "from jolt.url_identity import canonicalize_source_url\nfrom jolt.schemas import (\n",
            "workflow canonical URL import",
        )
    old_normalize = '''def normalize_url(value: str) -> str:\n    if not value.strip():\n        return ""\n    parts = urlsplit(value.strip())\n    query = [\n        (key, val)\n        for key, val in parse_qsl(parts.query, keep_blank_values=True)\n        if not key.lower().startswith("utm_") and key.lower() not in {"trk", "ref", "refid"}\n    ]\n    return urlunsplit(parts._replace(query=urlencode(query), fragment="")).rstrip("/")\n'''
    new_normalize = '''def normalize_url(value: str) -> str:\n    """Compatibility boundary for canonical posting identity."""\n    return canonicalize_source_url(value)\n'''
    text = replace_once(text, old_normalize, new_normalize, "workflow normalize_url")
    transition_wrapper = '''def transition_application(\n    session: Session, application_id: str, request: ApplicationTransitionRequest\n) -> ApplicationResponse:\n    """Delegate explicitly to the single reversible transition engine."""\n    from jolt.reversible_application_workflow import transition_application_reversibly\n\n    return transition_application_reversibly(session, application_id, request)\n\n\n'''
    text = replace_block(
        text,
        "def transition_application(\n",
        "def record_outcome(\n",
        transition_wrapper,
        "workflow transition implementation",
    )
    path.write_text(text, encoding="utf-8")


def patch_database(root: Path) -> None:
    path = root / "backend/src/jolt/database.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine\n",
        "from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine, event\n",
        "SQLAlchemy event import",
    )
    text = replace_once(
        text,
        '''    data_dir = Path.cwd() / "data"\n    data_dir.mkdir(parents=True, exist_ok=True)\n    return f"sqlite:///{(data_dir / 'jolt.db').as_posix()}"\n''',
        '''    project_root = Path(__file__).resolve().parents[3]\n    data_dir = project_root / "data"\n    data_dir.mkdir(parents=True, exist_ok=True)\n    return f"sqlite:///{(data_dir / 'jolt.db').as_posix()}"\n''',
        "stable database path",
    )
    text = replace_once(
        text,
        '''    engine = create_engine(url, connect_args=connect_args)\n    return sessionmaker(bind=engine, expire_on_commit=False)\n''',
        '''    engine = create_engine(url, connect_args=connect_args)\n    if url.startswith("sqlite"):\n        @event.listens_for(engine, "connect")\n        def _configure_sqlite(dbapi_connection, _connection_record) -> None:\n            cursor = dbapi_connection.cursor()\n            try:\n                cursor.execute("PRAGMA foreign_keys=ON")\n                cursor.execute("PRAGMA busy_timeout=5000")\n            finally:\n                cursor.close()\n    return sessionmaker(bind=engine, expire_on_commit=False)\n''',
        "SQLite connection safeguards",
    )
    text = replace_once(
        text,
        '''    try:\n        yield session\n    finally:\n        session.close()\n''',
        '''    try:\n        yield session\n    except Exception:\n        session.rollback()\n        raise\n    finally:\n        session.close()\n''',
        "session rollback",
    )
    path.write_text(text, encoding="utf-8")


def patch_work_item_validation(root: Path) -> None:
    path = root / "backend/src/jolt/application_work_items.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from pydantic import BaseModel, Field\n",
        "from pydantic import BaseModel, Field, field_validator\n",
        "work item field_validator import",
    )
    text = replace_once(
        text,
        '''class TaskCreateRequest(BaseModel):\n    title: str = Field(min_length=1, max_length=240)\n    notes: str = ""\n    due_at: datetime | None = None\n''',
        '''class TaskCreateRequest(BaseModel):\n    title: str = Field(min_length=1, max_length=240)\n    notes: str = ""\n    due_at: datetime | None = None\n\n    @field_validator("title")\n    @classmethod\n    def normalize_title(cls, value: str) -> str:\n        normalized = value.strip()\n        if not normalized:\n            raise ValueError("Task title is required.")\n        return normalized\n''',
        "task title validator",
    )
    text = replace_once(
        text,
        '''class InterviewCreateRequest(BaseModel):\n    interview_type: InterviewType\n    scheduled_at: datetime\n    timezone: str = Field(default="UTC", min_length=1, max_length=80)\n    format_location: str = ""\n    participants: str = ""\n    preparation_notes: str = ""\n''',
        '''class InterviewCreateRequest(BaseModel):\n    interview_type: InterviewType\n    scheduled_at: datetime\n    timezone: str = Field(default="UTC", min_length=1, max_length=80)\n    format_location: str = ""\n    participants: str = ""\n    preparation_notes: str = ""\n\n    @field_validator("timezone")\n    @classmethod\n    def normalize_timezone(cls, value: str) -> str:\n        normalized = value.strip()\n        if not normalized:\n            raise ValueError("Interview timezone is required.")\n        return normalized\n''',
        "interview timezone validator",
    )
    path.write_text(text, encoding="utf-8")


def patch_resource_validation(root: Path) -> None:
    path = root / "backend/src/jolt/application_resources.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from pydantic import BaseModel, Field\n",
        "from pydantic import BaseModel, Field, field_validator\n",
        "resource field_validator import",
    )
    text = replace_once(
        text,
        '''class ContactRequest(BaseModel):\n    name: str = Field(min_length=1, max_length=240)\n    role: str = ""\n    company: str = ""\n    email: str = ""\n    phone: str = ""\n    linkedin_url: str = ""\n    notes: str = ""\n''',
        '''class ContactRequest(BaseModel):\n    name: str = Field(min_length=1, max_length=240)\n    role: str = ""\n    company: str = ""\n    email: str = ""\n    phone: str = ""\n    linkedin_url: str = ""\n    notes: str = ""\n\n    @field_validator("name")\n    @classmethod\n    def normalize_name(cls, value: str) -> str:\n        normalized = value.strip()\n        if not normalized:\n            raise ValueError("Contact name is required.")\n        return normalized\n''',
        "contact name validator",
    )
    text = replace_once(
        text,
        '''class DocumentRequest(BaseModel):\n    document_type: DocumentType\n    title: str = Field(min_length=1, max_length=240)\n    file_path: str = ""\n    source_url: str = ""\n    status: DocumentStatus = "draft"\n    notes: str = ""\n''',
        '''class DocumentRequest(BaseModel):\n    document_type: DocumentType\n    title: str = Field(min_length=1, max_length=240)\n    file_path: str = ""\n    source_url: str = ""\n    status: DocumentStatus = "draft"\n    notes: str = ""\n\n    @field_validator("title")\n    @classmethod\n    def normalize_title(cls, value: str) -> str:\n        normalized = value.strip()\n        if not normalized:\n            raise ValueError("Document title is required.")\n        return normalized\n''',
        "document title validator",
    )
    path.write_text(text, encoding="utf-8")


def add_tests(root: Path) -> None:
    path = root / "backend/tests/test_audit_foundations.py"
    path.write_text(
        '''from __future__ import annotations\n\nimport sqlite3\nfrom pathlib import Path\n\nimport pytest\nfrom pydantic import ValidationError\nfrom sqlalchemy import text\n\nfrom jolt.application_resources import ContactRequest, DocumentRequest\nfrom jolt.application_work_items import InterviewCreateRequest, TaskCreateRequest\nfrom jolt.database import create_session_factory, default_database_url\nfrom jolt.workflow import transition_application\nfrom jolt.reversible_application_workflow import transition_application_reversibly\n\n\ndef test_transition_boundary_is_explicit_wrapper_not_package_monkeypatch() -> None:\n    assert transition_application is not transition_application_reversibly\n    assert transition_application.__module__ == "jolt.workflow"\n\n\ndef test_default_database_path_is_project_stable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:\n    monkeypatch.delenv("JOLT_DATABASE_URL", raising=False)\n    monkeypatch.chdir(tmp_path)\n    url = default_database_url()\n    assert url.endswith("/data/jolt.db")\n    assert str(tmp_path).replace("\\\\", "/") not in url\n\n\ndef test_sqlite_foreign_keys_are_enabled(tmp_path: Path) -> None:\n    factory = create_session_factory(f"sqlite:///{(tmp_path / 'integrity.db').as_posix()}")\n    with factory() as session:\n        assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1\n        with pytest.raises(sqlite3.IntegrityError):\n            session.execute(\n                text(\n                    "INSERT INTO application_events "\n                    "(id, application_id, event_type, from_status, to_status, notes, occurred_at) "\n                    "VALUES ('event', 'missing', 'test', '', 'recorded', '', CURRENT_TIMESTAMP)"\n                )\n            )\n            session.commit()\n\n\n@pytest.mark.parametrize(\n    ("factory", "payload"),\n    [\n        (TaskCreateRequest, {"title": "   "}),\n        (ContactRequest, {"name": "   "}),\n        (DocumentRequest, {"document_type": "resume", "title": "   "}),\n        (\n            InterviewCreateRequest,\n            {"interview_type": "recruiter_screen", "scheduled_at": "2026-07-26T12:00:00Z", "timezone": "   "},\n        ),\n    ],\n)\ndef test_required_resource_text_rejects_whitespace(factory, payload) -> None:\n    with pytest.raises(ValidationError):\n        factory.model_validate(payload)\n''',
        encoding="utf-8",
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    patch_package_init(root)
    patch_workflow(root)
    patch_database(root)
    patch_work_item_validation(root)
    patch_resource_validation(root)
    add_tests(root)
    print("Audit foundations batch 1 applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
