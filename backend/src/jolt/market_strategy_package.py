"""Compact strategic Market Insights package; no Review Inbox classifications."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeScope
from jolt.global_context import build_global_context_snapshot, global_context_version
from jolt.market_intelligence import build_market_intelligence
from jolt.unified_ai_work_package import UnifiedAIWorkPackage


def build_market_strategy_package_json(session: Session) -> bytes:
    """Export aggregated persisted evidence, never raw vacancy bodies."""
    context = build_global_context_snapshot()
    aggregates = build_market_intelligence(session)
    summary_keys = (
        "total_roles",
        "role_families",
        "work_modes",
        "seniority",
        "top_skills",
        "required_skills",
        "preferred_skills",
        "mentioned_skills",
        "learning_signals",
        "blocked_roles",
        "review_roles",
    )
    scoped = {}
    for name in ("target", "all"):
        raw_group = aggregates[name]
        group: dict[str, Any] = raw_group if isinstance(raw_group, dict) else {}
        scoped[name] = {key: group[key] for key in summary_keys if key in group}
    exchange = AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id=str(uuid4()),
        context_version=global_context_version(context),
        scope=AIExchangeScope(
            section="market_insights",
            analysis_types=["market_signal", "gap_signal", "recommendation", "context_update"],
            scope_label="Aggregated market strategy — no raw vacancy bodies",
        ),
        evidence={
            "aggregation": scoped,
            "total_unique_roles": aggregates["total_unique_roles"],
            "target_role_count": aggregates["target_role_count"],
            "evaluation_coverage": aggregates["evaluation_coverage"],
            "evidence_provenance": aggregates["evidence_provenance"],
            "limitations": [
                "Counts are deterministic aggregates, not proof of individual vacancy eligibility.",
                "Repeated observations are deduplicated by persisted posting identity.",
                "No individual vacancy bodies or Review Inbox decisions are included.",
                "Do not invent individual vacancy claims or references absent from this package.",
            ],
        },
        protected_state={
            "non_patchable": ["human_review_decisions", "applications", "job_search_preferences"],
        },
        requested_output={
            "feedback": "Evidence-based market signals, skills gaps and actionable recommendations.",
            "context_patch": "Put market_summary, skills_gap_summary, capture_strategy, application_strategy, or profile_strategy only in top-level context_patch.",
        },
    )
    package = UnifiedAIWorkPackage(
        generated_at=datetime.now(UTC),
        package_id=str(uuid4()),
        context_version=global_context_version(context),
        global_context=context,
        candidate_evidence={},
        review_inbox=None,
        exchanges=[exchange],
        instructions={
            "workflow": "Strategic Market Insights review only. Return a jolt_ai_work_package_update with review_inbox=null, one market_insights exchange output, and optional top-level context_patch. Never classify vacancies. Every claim must reflect the aggregate evidence limits.",
            "import_route": "/api/ai-work-package/import",
        },
    )
    return package.model_dump_json(indent=2).encode("utf-8")
