from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput
from jolt.ai_review_import import AIReviewImportRequest, import_ai_review
from jolt.application_outcomes_exchange import (
    build_application_outcomes_exchange,
    import_application_outcomes_exchange,
)
from jolt.candidate_evidence import (
    build_candidate_evidence_ledger,
    validate_candidate_evidence_refs,
    validate_candidate_evidence_summary,
)
from jolt.data_quality_exchange import build_data_quality_exchange, import_data_quality_exchange
from jolt.errors import JoltNotFoundError
from jolt.global_context import (
    GlobalAIContextOverlay,
    build_global_context_snapshot,
    global_context_version,
    load_global_ai_context,
    save_global_ai_context,
)
from jolt.linkedin_profile_exchange import (
    build_linkedin_profile_exchange,
    import_linkedin_profile_exchange,
)
from jolt.market_intelligence_exchange import (
    build_market_intelligence_exchange,
    import_market_intelligence_exchange,
)
from jolt.professional_evidence_exchange import (
    build_professional_evidence_exchange,
    import_professional_evidence_exchange,
)
from jolt.review_inbox_exchange import build_review_inbox_exchange_json
from jolt.search_preference_exchange import (
    build_search_preference_exchange,
    import_search_preference_exchange,
)
from jolt.skills_preparation_exchange import (
    build_skills_preparation_exchange,
    import_skills_preparation_exchange,
)

_UNIFIED_CONTEXT_PATCH_KEYS = frozenset(
    {
        "market_summary",
        "skills_gap_summary",
        "candidate_evidence_summary",
        "application_strategy",
        "outcome_strategy",
        "profile_strategy",
        "capture_strategy",
        "audit_summary",
        "professional_evidence_summary",
    }
)
_SUPPORTED_SECTIONS = frozenset(
    {
        "market_insights",
        "applications",
        "linkedin_profile",
        "skills_gaps",
        "professional_evidence",
        "search_preferences",
        "data_quality",
    }
)


class UnifiedAIWorkPackage(BaseModel):
    contract_type: Literal["jolt_ai_work_package"] = "jolt_ai_work_package"
    contract_version: Literal["1.0"] = "1.0"
    package_id: str = Field(min_length=1)
    generated_at: datetime
    context_version: str
    global_context: dict[str, Any]
    candidate_evidence: dict[str, Any]
    review_inbox: dict[str, Any] | None = None
    exchanges: list[AIExchangeInput]
    instructions: dict[str, Any]


class UnifiedAIUpdate(BaseModel):
    contract_type: Literal["jolt_ai_work_package_update"] = "jolt_ai_work_package_update"
    contract_version: Literal["1.0"] = "1.0"
    package_id: str = Field(min_length=1)
    source_context_version: str = Field(min_length=1)
    reviewed_at: datetime
    review_source: Literal["chatgpt"] = "chatgpt"
    review_version: str = Field(min_length=1, max_length=80)
    review_inbox: AIReviewImportRequest | None = None
    exchanges: list[AIExchangeOutput] = Field(default_factory=list)
    context_patch: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class UnifiedAIImportResponse(BaseModel):
    package_id: str
    imported_sections: list[str]
    review_inbox_imported: bool
    context: GlobalAIContextOverlay
    section_results: dict[str, Any]


def _without_duplicate_context(exchange: AIExchangeInput) -> AIExchangeInput:
    return exchange.model_copy(update={"context": {}})


def _review_inbox_payload(session: Session) -> dict[str, Any] | None:
    try:
        payload = json.loads(build_review_inbox_exchange_json(session))
    except JoltNotFoundError:
        return None
    payload.pop("reasoning_context", None)
    payload["context_location"] = "global_context"
    payload["candidate_evidence_location"] = "candidate_evidence"
    return payload


def build_unified_ai_work_package(session: Session) -> UnifiedAIWorkPackage:
    context = build_global_context_snapshot()
    candidate_evidence = build_candidate_evidence_ledger(session)
    exchanges = [
        build_market_intelligence_exchange(session),
        build_application_outcomes_exchange(session),
        build_linkedin_profile_exchange(session),
        build_skills_preparation_exchange(session),
        build_professional_evidence_exchange(session),
        build_search_preference_exchange(session),
        build_data_quality_exchange(session),
    ]
    return UnifiedAIWorkPackage(
        package_id=str(uuid4()),
        generated_at=datetime.now(UTC),
        context_version=global_context_version(context),
        global_context=context,
        candidate_evidence=candidate_evidence,
        review_inbox=_review_inbox_payload(session),
        exchanges=[_without_duplicate_context(exchange) for exchange in exchanges],
        instructions={
            "workflow": (
                "Analyze this one file and return one jolt_ai_work_package_update JSON file."
            ),
            "reasoning_authority": (
                "ChatGPT performs semantic reasoning; JOLT provides evidence, deterministic facts, "
                "validation, storage, and workflow state."
            ),
            "context": (
                "Use global_context for user preferences and current AI-owned strategy. Use "
                "candidate_evidence as the canonical candidate-evidence surface for eligibility "
                "and fit. Do not invent unsupported experience or silently change user-owned preferences."
            ),
            "candidate_evidence": (
                "Treat candidate_evidence.source_evidence as raw provenance, not as pre-classified "
                "experience. If updating candidate_evidence_summary, return schema_version=1.0 and "
                "claims whose evidence_level is one of professional, project_lab, certification, "
                "education, language, explicit_non_claim, or unknown. Every claim must cite at least "
                "one evidence_ref from candidate_evidence.source_evidence. Never upgrade a mention, "
                "course, certification, lab, project, or adjacent exposure into unsupported "
                "professional production experience."
            ),
            "freshness": (
                "Copy context_version exactly into source_context_version in the returned update. "
                "JOLT rejects stale updates if its context changed after export."
            ),
            "review_inbox": (
                "If review_inbox is present, execute its hardline Stage 1 before Stage 2 fit and return "
                "its jolt_ai_review payload in review_inbox using its response_template exactly."
            ),
            "section_outputs": (
                "Return at most one AIExchangeOutput per supplied exchange section. Set each "
                "section output context_patch to an empty object."
            ),
            "context_patch": (
                "Put all durable AI-derived context changes only in the update's top-level "
                "context_patch. Allowed namespaces: market_summary, skills_gap_summary, "
                "candidate_evidence_summary, application_strategy, outcome_strategy, profile_strategy, "
                "capture_strategy, audit_summary, professional_evidence_summary."
            ),
            "protected": (
                "Never patch job_search_preferences, human review decisions, applications, "
                "outcomes, raw captures, source documents, postings, or candidate_evidence.source_evidence."
            ),
        },
    )


def build_unified_ai_work_package_json(session: Session) -> bytes:
    package = build_unified_ai_work_package(session)
    return package.model_dump_json(indent=2).encode("utf-8")


def _validate_unified_update(update: UnifiedAIUpdate) -> None:
    unknown_context = sorted(set(update.context_patch) - _UNIFIED_CONTEXT_PATCH_KEYS)
    if unknown_context:
        raise ValueError(
            "Unified AI context patch contains non-patchable keys: " + ", ".join(unknown_context)
        )

    candidate_summary = update.context_patch.get("candidate_evidence_summary")
    if candidate_summary is not None:
        if not isinstance(candidate_summary, dict):
            raise ValueError("candidate_evidence_summary must be an object")
        update.context_patch["candidate_evidence_summary"] = validate_candidate_evidence_summary(
            candidate_summary
        )

    current_context = build_global_context_snapshot()
    current_version = global_context_version(current_context)
    if update.source_context_version != current_version:
        raise ValueError(
            "Unified AI update is stale: source_context_version does not match current JOLT context"
        )

    seen: set[str] = set()
    for output in update.exchanges:
        section = output.scope.section
        if section not in _SUPPORTED_SECTIONS:
            raise ValueError(f"Unsupported unified AI exchange section: {section}")
        if section in seen:
            raise ValueError(f"Duplicate unified AI exchange section: {section}")
        if output.context_patch:
            raise ValueError(
                f"Section output {section} must leave context_patch empty; use top-level context_patch"
            )
        seen.add(section)


def _apply_unified_context_patch(update: UnifiedAIUpdate) -> GlobalAIContextOverlay:
    current = load_global_ai_context()
    payload = current.model_dump()
    for key, value in update.context_patch.items():
        if not isinstance(value, dict):
            raise ValueError(f"Unified context namespace '{key}' must be an object")
        payload[key] = value
    payload["updated_at"] = update.reviewed_at
    payload["updated_by"] = f"chatgpt:{update.review_version}"
    return save_global_ai_context(GlobalAIContextOverlay.model_validate(payload))


def _dispatch_section(session: Session, output: AIExchangeOutput) -> Any:
    section = output.scope.section
    if section == "market_insights":
        return import_market_intelligence_exchange(output)
    if section == "applications":
        return import_application_outcomes_exchange(output)
    if section == "linkedin_profile":
        return import_linkedin_profile_exchange(session, output)
    if section == "skills_gaps":
        return import_skills_preparation_exchange(output)
    if section == "professional_evidence":
        return import_professional_evidence_exchange(output)
    if section == "search_preferences":
        return import_search_preference_exchange(output)
    if section == "data_quality":
        return import_data_quality_exchange(output)
    raise ValueError(f"Unsupported unified AI exchange section: {section}")


def import_unified_ai_update(
    session: Session,
    update: UnifiedAIUpdate,
) -> UnifiedAIImportResponse:
    _validate_unified_update(update)

    candidate_summary = update.context_patch.get("candidate_evidence_summary")
    if candidate_summary is not None:
        validate_candidate_evidence_refs(session, candidate_summary)

    section_results: dict[str, Any] = {}
    imported_sections: list[str] = []
    review_inbox_imported = False

    if update.review_inbox is not None:
        review_result = import_ai_review(session, update.review_inbox)
        section_results["review_inbox"] = review_result.model_dump(mode="json")
        review_inbox_imported = True

    for output in update.exchanges:
        section = output.scope.section
        result = _dispatch_section(session, output)
        if hasattr(result, "model_dump"):
            section_results[section] = result.model_dump(mode="json")
        else:
            section_results[section] = result
        imported_sections.append(section)

    context = _apply_unified_context_patch(update)
    return UnifiedAIImportResponse(
        package_id=update.package_id,
        imported_sections=imported_sections,
        review_inbox_imported=review_inbox_imported,
        context=context,
        section_results=section_results,
    )
