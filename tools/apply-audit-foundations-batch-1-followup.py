from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected marker not found: {label}")
    return text.replace(old, new, 1)


def patch_workflow(root: Path) -> None:
    path = root / "backend/src/jolt/workflow.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit\n",
        "",
        "unused URL imports",
    )
    text = replace_once(
        text,
        "from jolt.url_identity import canonicalize_source_url\nfrom jolt.schemas import (\n",
        "from jolt.schemas import (\n",
        "schema import order",
    )
    text = replace_once(
        text,
        ")\n\nPROFILE_ID = \"default-job-search\"\n",
        ")\nfrom jolt.url_identity import canonicalize_source_url\n\nPROFILE_ID = \"default-job-search\"\n",
        "canonical URL import order",
    )
    path.write_text(text, encoding="utf-8")


def patch_task_update(root: Path) -> None:
    path = root / "backend/src/jolt/application_work_items.py"
    text = path.read_text(encoding="utf-8")
    old = '''class TaskUpdateRequest(BaseModel):\n    title: str = Field(min_length=1, max_length=240)\n    notes: str = \"\"\n    due_at: datetime | None = None\n\n\n'''
    new = '''class TaskUpdateRequest(TaskCreateRequest):\n    pass\n\n\n'''
    text = replace_once(text, old, new, "task update normalization")
    path.write_text(text, encoding="utf-8")


def patch_tests(root: Path) -> None:
    path = root / "backend/tests/test_audit_foundations.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "import sqlite3\n", "", "sqlite3 import")
    text = replace_once(
        text,
        "from sqlalchemy import text\n",
        "from sqlalchemy import text\nfrom sqlalchemy.exc import IntegrityError\n",
        "SQLAlchemy IntegrityError import",
    )
    text = replace_once(
        text,
        "        with pytest.raises(sqlite3.IntegrityError):\n",
        "        with pytest.raises(IntegrityError):\n",
        "foreign-key exception assertion",
    )
    text = replace_once(
        text,
        '        (TaskCreateRequest, {"title": "   "}),\n',
        '        (TaskCreateRequest, {"title": "   "}),\n        (TaskUpdateRequest, {"title": "   "}),\n',
        "task update validation case",
    )
    text = replace_once(
        text,
        "from jolt.application_work_items import InterviewCreateRequest, TaskCreateRequest\n",
        "from jolt.application_work_items import (\n    InterviewCreateRequest,\n    TaskCreateRequest,\n    TaskUpdateRequest,\n)\n",
        "task update test import",
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    patch_workflow(root)
    patch_task_update(root)
    patch_tests(root)
    print("Audit foundations batch 1 follow-up applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
