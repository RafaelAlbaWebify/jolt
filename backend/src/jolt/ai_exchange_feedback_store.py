from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from jolt.ai_exchange_contract import AIExchangeFeedbackItem, AIExchangeOutput

_FEEDBACK_FILE = "ai_exchange_feedback.json"
_MAX_RECORDS = 100


class AIExchangeFeedbackRecord(BaseModel):
    id: str
    exchange_id: str
    section: str
    review_version: str
    reviewed_at: datetime
    imported_at: datetime
    feedback: list[AIExchangeFeedbackItem] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class AIExchangeFeedbackIndex(BaseModel):
    total_import_count: int
    records: list[AIExchangeFeedbackRecord] = Field(default_factory=list)


def _data_path() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    data_dir = backend_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / _FEEDBACK_FILE


def _read_index() -> AIExchangeFeedbackIndex:
    path = _data_path()
    if not path.exists():
        return AIExchangeFeedbackIndex(total_import_count=0)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return AIExchangeFeedbackIndex.model_validate(payload)
    except (json.JSONDecodeError, OSError, ValueError):
        return AIExchangeFeedbackIndex(total_import_count=0)


def _write_index(index: AIExchangeFeedbackIndex) -> None:
    path = _data_path()
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary_path.write_text(index.model_dump_json(indent=2), encoding="utf-8")
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def save_ai_exchange_feedback(output: AIExchangeOutput) -> AIExchangeFeedbackRecord:
    index = _read_index()
    record = AIExchangeFeedbackRecord(
        id=str(uuid4()),
        exchange_id=output.exchange_id,
        section=output.scope.section,
        review_version=output.review_version,
        reviewed_at=output.reviewed_at,
        imported_at=datetime.now(UTC),
        feedback=output.feedback,
        summary=output.summary,
    )
    records = [*index.records, record][-_MAX_RECORDS:]
    _write_index(
        AIExchangeFeedbackIndex(
            total_import_count=index.total_import_count + 1,
            records=records,
        )
    )
    return record


def list_ai_exchange_feedback(section: str | None = None) -> AIExchangeFeedbackIndex:
    index = _read_index()
    records = index.records
    if section is not None:
        records = [record for record in records if record.section == section]
    return AIExchangeFeedbackIndex(
        total_import_count=index.total_import_count,
        records=list(reversed(records)),
    )
