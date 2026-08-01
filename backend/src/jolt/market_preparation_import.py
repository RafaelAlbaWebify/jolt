from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class MarketPreparationAction(BaseModel):
    action_type: str = Field(default="preparation", max_length=80)
    title: str = Field(default="", max_length=240)
    rationale: str = ""
    proposed_action: str = ""
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["pending", "accepted", "rejected", "implemented", "snoozed"] = "pending"
    source: str = "chatgpt_market_package"


class MarketPreparationImportRequest(BaseModel):
    source: str = "chatgpt_market_package"
    summary: str = ""
    market_recommendations: list[MarketPreparationAction] = Field(default_factory=list)
    preparation_plan: list[MarketPreparationAction] = Field(default_factory=list)
    search_filter_improvements: list[MarketPreparationAction] = Field(default_factory=list)
    linkedin_alignment_actions: list[MarketPreparationAction] = Field(default_factory=list)
    application_strategy: list[MarketPreparationAction] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class MarketPreparationImportRecord(BaseModel):
    id: str
    source: str
    summary: str
    imported_at: str
    action_count: int
    actions: list[MarketPreparationAction]
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class MarketPreparationImportResponse(BaseModel):
    imported_count: int
    latest_import: MarketPreparationImportRecord


class MarketPreparationImportIndex(BaseModel):
    import_count: int
    latest_import: MarketPreparationImportRecord | None = None
    imports: list[MarketPreparationImportRecord] = Field(default_factory=list)


def _data_path() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    data_dir = backend_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "market_preparation_imports.json"


def _read_records() -> list[MarketPreparationImportRecord]:
    path = _data_path()
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        MarketPreparationImportRecord.model_validate(item) for item in payload.get("imports", [])
    ]


def _write_records(records: list[MarketPreparationImportRecord]) -> None:
    path = _data_path()
    payload = {"imports": [record.model_dump(mode="json") for record in records[-25:]]}
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )


def _actions_from_request(request: MarketPreparationImportRequest) -> list[MarketPreparationAction]:
    actions: list[MarketPreparationAction] = []
    for group in (
        request.market_recommendations,
        request.preparation_plan,
        request.search_filter_improvements,
        request.linkedin_alignment_actions,
        request.application_strategy,
    ):
        actions.extend(group)
    return actions


def import_market_preparation(
    request: MarketPreparationImportRequest,
) -> MarketPreparationImportResponse:
    records = _read_records()
    actions = _actions_from_request(request)
    record = MarketPreparationImportRecord(
        id=str(uuid.uuid4()),
        source=request.source,
        summary=request.summary,
        imported_at=datetime.now(UTC).isoformat(),
        action_count=len(actions),
        actions=actions,
        raw_payload=request.raw_payload,
    )
    records.append(record)
    _write_records(records)
    return MarketPreparationImportResponse(imported_count=len(actions), latest_import=record)


def list_market_preparation_imports() -> MarketPreparationImportIndex:
    records = _read_records()
    latest = records[-1] if records else None
    return MarketPreparationImportIndex(
        import_count=len(records), latest_import=latest, imports=list(reversed(records))
    )
