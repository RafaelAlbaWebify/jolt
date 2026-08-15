from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Literal
from zipfile import ZIP_DEFLATED, ZipFile

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import LinkedInPresenceCapture, LinkedInPresenceRecommendation, utc_now
from jolt.market_intelligence import build_market_intelligence

LinkedInCaptureCategory = Literal[
    "profile",
    "public_profile",
    "analytics",
    "activity",
    "network_contact",
    "network_request",
    "target_company",
    "target_recruiter",
    "job_search",
    "other",
]
LinkedInRecommendationType = Literal[
    "profile_update",
    "network_decision",
    "content_action",
    "outreach",
    "lead_research",
    "cleanup",
]
LinkedInPriority = Literal["high", "medium", "low"]
LinkedInRecommendationStatus = Literal["pending", "accepted", "rejected", "implemented", "snoozed"]

_CONNECTION_SCHEMA = "jolt_linkedin_connections_v1"


class LinkedInCaptureRequest(BaseModel):
    category: LinkedInCaptureCategory
    title: str = ""
    source_url: str = ""
    visible_text: str = Field(default="", max_length=200_000)
    notes: str = ""


class LinkedInRecommendationRequest(BaseModel):
    capture_id: str | None = None
    recommendation_type: LinkedInRecommendationType
    target_area: str = ""
    title: str = Field(min_length=1)
    rationale: str = ""
    proposed_action: str = ""
    proposed_text: str = ""
    priority: LinkedInPriority = "medium"


class LinkedInRecommendationImportItem(LinkedInRecommendationRequest):
    status: LinkedInRecommendationStatus = "pending"


class LinkedInRecommendationImportRequest(BaseModel):
    source: str = "chatgpt_package"
    recommendations: list[LinkedInRecommendationImportItem] = Field(
        default_factory=list, max_length=100
    )


class LinkedInRecommendationStatusRequest(BaseModel):
    status: LinkedInRecommendationStatus


class LinkedInCaptureResponse(BaseModel):
    id: str
    category: str
    title: str
    source_url: str
    visible_text: str
    notes: str
    content_hash: str
    previous_capture_id: str | None
    changed_since_previous: bool
    captured_at: str


class LinkedInRecommendationResponse(BaseModel):
    id: str
    capture_id: str | None
    recommendation_type: str
    target_area: str
    title: str
    rationale: str
    proposed_action: str
    proposed_text: str
    priority: str
    status: str
    created_at: str
    updated_at: str


class LinkedInRecommendationImportResponse(BaseModel):
    imported_count: int
    recommendations: list[LinkedInRecommendationResponse]


class LinkedInCommandCenterResponse(BaseModel):
    capture_count: int
    recommendation_count: int
    open_recommendation_count: int
    categories: dict[str, int]
    recommendation_statuses: dict[str, int]
    recommendation_types: dict[str, int]
    captures: list[LinkedInCaptureResponse]
    recommendations: list[LinkedInRecommendationResponse]


def _hash_capture(request: LinkedInCaptureRequest) -> str:
    payload = json.dumps(
        {
            "category": request.category,
            "source_url": request.source_url.strip(),
            "visible_text": request.visible_text.strip(),
            "notes": request.notes.strip(),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _capture_response(capture: LinkedInPresenceCapture) -> LinkedInCaptureResponse:
    return LinkedInCaptureResponse(
        id=capture.id,
        category=capture.category,
        title=capture.title,
        source_url=capture.source_url,
        visible_text=capture.visible_text,
        notes=capture.notes,
        content_hash=capture.content_hash,
        previous_capture_id=capture.previous_capture_id,
        changed_since_previous=capture.changed_since_previous,
        captured_at=capture.captured_at.isoformat(),
    )


def _recommendation_response(
    recommendation: LinkedInPresenceRecommendation,
) -> LinkedInRecommendationResponse:
    return LinkedInRecommendationResponse(
        id=recommendation.id,
        capture_id=recommendation.capture_id,
        recommendation_type=recommendation.recommendation_type,
        target_area=recommendation.target_area,
        title=recommendation.title,
        rationale=recommendation.rationale,
        proposed_action=recommendation.proposed_action,
        proposed_text=recommendation.proposed_text,
        priority=recommendation.priority,
        status=recommendation.status,
        created_at=recommendation.created_at.isoformat(),
        updated_at=recommendation.updated_at.isoformat(),
    )


def list_linkedin_command_center(session: Session) -> LinkedInCommandCenterResponse:
    captures = session.scalars(
        select(LinkedInPresenceCapture).order_by(LinkedInPresenceCapture.captured_at.desc())
    ).all()
    recommendations = session.scalars(
        select(LinkedInPresenceRecommendation).order_by(
            LinkedInPresenceRecommendation.updated_at.desc(),
            LinkedInPresenceRecommendation.created_at.desc(),
        )
    ).all()
    status_counts = Counter(item.status for item in recommendations)
    return LinkedInCommandCenterResponse(
        capture_count=len(captures),
        recommendation_count=len(recommendations),
        open_recommendation_count=sum(
            1 for item in recommendations if item.status in {"pending", "accepted", "snoozed"}
        ),
        categories=dict(Counter(item.category for item in captures)),
        recommendation_statuses=dict(status_counts),
        recommendation_types=dict(Counter(item.recommendation_type for item in recommendations)),
        captures=[_capture_response(item) for item in captures[:25]],
        recommendations=[_recommendation_response(item) for item in recommendations[:100]],
    )


def create_linkedin_capture(
    session: Session, request: LinkedInCaptureRequest
) -> LinkedInCaptureResponse:
    content_hash = _hash_capture(request)
    previous = session.scalars(
        select(LinkedInPresenceCapture)
        .where(LinkedInPresenceCapture.category == request.category)
        .order_by(LinkedInPresenceCapture.captured_at.desc())
    ).first()
    capture = LinkedInPresenceCapture(
        id=str(uuid.uuid4()),
        category=request.category,
        title=request.title.strip(),
        source_url=request.source_url.strip(),
        visible_text=request.visible_text.strip(),
        notes=request.notes.strip(),
        content_hash=content_hash,
        previous_capture_id=previous.id if previous else None,
        changed_since_previous=bool(previous and previous.content_hash != content_hash),
        captured_at=utc_now(),
    )
    session.add(capture)
    session.commit()
    return _capture_response(capture)


def _validate_capture_id(session: Session, capture_id: str | None) -> None:
    if capture_id:
        found = session.get(LinkedInPresenceCapture, capture_id)
        if found is None:
            raise LookupError(f"LinkedIn capture {capture_id} was not found")


def _create_recommendation_row(
    request: LinkedInRecommendationRequest,
    *,
    status: LinkedInRecommendationStatus = "pending",
) -> LinkedInPresenceRecommendation:
    now = utc_now()
    return LinkedInPresenceRecommendation(
        id=str(uuid.uuid4()),
        capture_id=request.capture_id,
        recommendation_type=request.recommendation_type,
        target_area=request.target_area.strip(),
        title=request.title.strip(),
        rationale=request.rationale.strip(),
        proposed_action=request.proposed_action.strip(),
        proposed_text=request.proposed_text.strip(),
        priority=request.priority,
        status=status,
        created_at=now,
        updated_at=now,
    )


def create_linkedin_recommendation(
    session: Session, request: LinkedInRecommendationRequest
) -> LinkedInRecommendationResponse:
    _validate_capture_id(session, request.capture_id)
    recommendation = _create_recommendation_row(request)
    session.add(recommendation)
    session.commit()
    return _recommendation_response(recommendation)


def import_linkedin_recommendations(
    session: Session, request: LinkedInRecommendationImportRequest
) -> LinkedInRecommendationImportResponse:
    imported: list[LinkedInPresenceRecommendation] = []
    for item in request.recommendations:
        _validate_capture_id(session, item.capture_id)
        imported.append(_create_recommendation_row(item, status=item.status))
    session.add_all(imported)
    session.commit()
    return LinkedInRecommendationImportResponse(
        imported_count=len(imported),
        recommendations=[_recommendation_response(item) for item in imported],
    )


def update_linkedin_recommendation_status(
    session: Session, recommendation_id: str, request: LinkedInRecommendationStatusRequest
) -> LinkedInRecommendationResponse:
    recommendation = session.get(LinkedInPresenceRecommendation, recommendation_id)
    if recommendation is None:
        raise LookupError(f"LinkedIn recommendation {recommendation_id} was not found")
    recommendation.status = request.status
    recommendation.updated_at = utc_now()
    session.add(recommendation)
    session.commit()
    return _recommendation_response(recommendation)


def _csv_bytes(rows: list[dict[str, object]], fieldnames: list[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _structured_connections(
    captures: list[LinkedInCaptureResponse],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    connections_by_identity: dict[str, dict[str, object]] = {}
    capture_runs: list[dict[str, object]] = []

    for capture in captures:
        if capture.category != "network_contact":
            continue

        try:
            payload = json.loads(capture.visible_text)
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict) or payload.get("schema") != _CONNECTION_SCHEMA:
            continue

        run = payload.get("capture_run")
        if isinstance(run, dict):
            capture_runs.append(
                {
                    "capture_id": capture.id,
                    "captured_at": capture.captured_at,
                    "source_url": capture.source_url,
                    **run,
                }
            )

        raw_connections = payload.get("connections")
        if not isinstance(raw_connections, list):
            continue

        for raw in raw_connections:
            if not isinstance(raw, dict):
                continue

            profile_url = str(raw.get("profile_url", "")).strip()
            name = str(raw.get("name", "")).strip()
            headline = str(raw.get("headline", "")).strip()
            identity = profile_url.casefold() if profile_url else f"{name}|{headline}".casefold()

            if not name or not identity or identity in connections_by_identity:
                continue

            connections_by_identity[identity] = {
                "name": name,
                "profile_url": profile_url,
                "headline": headline,
                "connection_context": str(raw.get("connection_context", "")).strip(),
                "capture_order": raw.get("capture_order"),
                "capture_id": capture.id,
                "captured_at": str(raw.get("captured_at", "")).strip() or capture.captured_at,
                "source_url": str(raw.get("source_url", "")).strip() or capture.source_url,
            }

    return list(connections_by_identity.values()), capture_runs


def _screenshot_path(notes: str) -> Path | None:
    for line in notes.splitlines():
        if line.startswith("Screenshot: "):
            candidate = Path(line.removeprefix("Screenshot: ").strip())
            return candidate if candidate.is_file() else None
    return None


def build_linkedin_analysis_pack(session: Session) -> bytes:
    command_center = list_linkedin_command_center(session)
    capture_rows = session.scalars(
        select(LinkedInPresenceCapture).order_by(LinkedInPresenceCapture.captured_at.desc())
    ).all()
    captures = [_capture_response(item) for item in capture_rows]
    recommendations = [item.model_dump() for item in command_center.recommendations]
    capture_dicts = [item.model_dump() for item in captures]
    connections, connection_capture_runs = _structured_connections(captures)

    market = build_market_intelligence(session, timeframe="all", source_scope="all")
    market_target = market.get("target", {})
    if not isinstance(market_target, dict):
        market_target = {}

    dataset = {
        "pack_type": "jolt_linkedin_command_center",
        "pack_version": 3,
        "generated_at": utc_now().isoformat(),
        "purpose": "User-supervised LinkedIn profile, activity, and network evidence capture.",
        "guardrails": [
            "JOLT captures and packages evidence only.",
            "All AI analysis and network decisions happen in ChatGPT.",
            "Do not automate LinkedIn actions.",
            "Do not infer private facts beyond captured evidence.",
        ],
        "import_contract": {
            "endpoint": "/api/linkedin-command-center/recommendations/import",
            "format": {
                "source": "chatgpt_package",
                "recommendations": [
                    {
                        "recommendation_type": (
                            "profile_update | network_decision | content_action | "
                            "outreach | lead_research | cleanup"
                        ),
                        "target_area": (
                            "LinkedIn section, person, company, topic, or workflow area"
                        ),
                        "title": "Short recommendation title",
                        "rationale": "Evidence-based reason",
                        "proposed_action": "User action to take manually",
                        "proposed_text": "Optional copy/message/profile text",
                        "priority": "high | medium | low",
                        "status": "pending",
                    }
                ],
            },
        },
        "captures": capture_dicts,
        "connections": connections,
        "connection_capture_runs": connection_capture_runs,
        "recommendations": recommendations,
        "market_summary": {
            "total_unique_roles": market.get("total_unique_roles", 0),
            "target_role_count": market.get("target_role_count", 0),
            "fit_explanation": market.get("fit_explanation", ""),
            "target_top_skills": market_target.get("top_skills", []),
        },
    }

    prompt = """# JOLT LinkedIn evidence analysis

JOLT collected the evidence in this package. Perform all analysis here in ChatGPT.

Analyse only what the package supports. Identify useful recruiters, hiring managers, former colleagues, target-company contacts, possible reconnection opportunities, low-relevance contacts, uncertain records, and evidence gaps.

Do not assume that missing profile information means a person is irrelevant. Do not perform or recommend automated LinkedIn actions.
"""

    readme = f"""# JOLT LinkedIn Command Center package

Generated: {dataset["generated_at"]}

JOLT captures and packages evidence. ChatGPT performs every AI-driven analysis and decision.

Included:

- Captures: {len(capture_dicts)}
- Structured unique connections: {len(connections)}
- Connection capture runs: {len(connection_capture_runs)}
- Existing JOLT recommendations: {len(recommendations)}
"""

    files: dict[str, bytes] = {
        "README.md": readme.encode("utf-8"),
        "prompt.md": prompt.encode("utf-8"),
        "data/linkedin_command_center.json": json.dumps(
            dataset, indent=2, ensure_ascii=False, sort_keys=True
        ).encode("utf-8"),
        "data/connections.json": json.dumps(
            connections, indent=2, ensure_ascii=False, sort_keys=True
        ).encode("utf-8"),
        "data/connection_capture_runs.json": json.dumps(
            connection_capture_runs, indent=2, ensure_ascii=False, sort_keys=True
        ).encode("utf-8"),
        "data/connections.csv": _csv_bytes(
            connections,
            [
                "name",
                "profile_url",
                "headline",
                "connection_context",
                "capture_order",
                "capture_id",
                "captured_at",
                "source_url",
            ],
        ),
        "data/linkedin_captures.csv": _csv_bytes(
            capture_dicts,
            [
                "id",
                "category",
                "title",
                "source_url",
                "content_hash",
                "previous_capture_id",
                "changed_since_previous",
                "captured_at",
            ],
        ),
        "data/linkedin_recommendations.csv": _csv_bytes(
            recommendations,
            [
                "id",
                "capture_id",
                "recommendation_type",
                "target_area",
                "title",
                "priority",
                "status",
                "created_at",
                "updated_at",
            ],
        ),
    }

    for capture in captures:
        files[f"evidence/raw_visible_text/{capture.id}.txt"] = capture.visible_text.encode("utf-8")
        screenshot = _screenshot_path(capture.notes)
        if screenshot is not None:
            files[f"evidence/screenshots/{capture.id}-{screenshot.name}"] = screenshot.read_bytes()

    manifest = {
        "pack_type": dataset["pack_type"],
        "pack_version": dataset["pack_version"],
        "generated_at": dataset["generated_at"],
        "files": {
            name: {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in sorted(files.items())
        },
    }
    files["manifest.json"] = json.dumps(
        manifest, indent=2, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")

    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return output.getvalue()
