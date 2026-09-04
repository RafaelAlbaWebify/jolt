from __future__ import annotations

import json

from sqlalchemy.orm import Session

from jolt.ai_review_pack import build_ai_review_json
from jolt.global_context import build_global_context_snapshot, global_context_version


def build_review_inbox_exchange_json(session: Session) -> bytes:
    """Enrich the proven AI review batch with JOLT's durable reasoning context."""

    document = json.loads(build_ai_review_json(session))
    context = build_global_context_snapshot()
    context_version = global_context_version(context)

    document["exchange_section"] = "review_inbox"
    document["context_version"] = context_version
    document["reasoning_context"] = context
    document["context_ownership"] = {
        "job_search_preferences": "jolt_user_owned",
        "ai_context": "chatgpt_derived_user_reviewable",
        "review_results": "chatgpt_analysis_importable",
        "human_review_decisions": "protected",
        "applications": "protected",
    }
    document["reasoning_instructions"] = {
        "authority": "chatgpt_source_first",
        "processing_mode": "strict_sequential_per_job",
        "source_priority": (
            "Vacancy body evidence outranks card labels, search filters, and inferred geography."
        ),
        "context_use": (
            "Use JOLT context as candidate/search state; do not invent or upgrade unsupported experience."
        ),
        "sequential_review_protocol": [
            "Process jobs in jobs[] order, one vacancy at a time.",
            "For the current vacancy, read its complete jobs[].analysis_text and deterministic evidence before considering any other vacancy.",
            "Complete and internally validate the current vacancy's Stage 1 result before moving to the next vacancy.",
            "If Stage 1 is REJECT or MANUAL_REVIEW, stop that vacancy immediately; do not perform technical-fit analysis.",
            "Only when Stage 1 is PASS, compare the vacancy with candidate_evidence and perform Stage 2 technical fit.",
            "Write exactly one review result for the current posting_id, then move to the next jobs[] entry.",
            "Do not compare, rank, shortlist, or aggregate vacancies until every jobs[] entry has one completed review result.",
        ],
        "per_job_stage_1_order": [
            "location and hiring territory",
            "employment and work-authorization constraints",
            "onsite, commute, travel, field, shift, weekend, or on-call constraints",
            "mandatory language requirements",
            "mandatory certification or clearance requirements",
            "mandatory experience and other explicit non-negotiables",
        ],
        "deterministic_location_authority": (
            "If jobs[].location_hardline_evidence.hardline_reject is true, Stage 1 MUST return REJECT, "
            "location_eligibility=ineligible, geography_status=ineligible, final_decision=reject, "
            "fit_analysis_allowed=false, and technical_fit_percent/technical_fit=null. The only exception "
            "is explicit contradictory Spain-compatible hiring evidence already present in the same vacancy; "
            "if such a contradiction exists, return MANUAL_REVIEW and cite both sides instead of overriding it silently."
        ),
        "stage_1_hardline_gate": (
            "Evaluate location/hiring geography, mandatory experience, employment/legal constraints, "
            "language/certification/clearance and other explicit non-negotiables before fit. "
            "Return PASS, REJECT, or rare MANUAL_REVIEW."
        ),
        "hardline_precedence": (
            "HARDLINE REJECT overrides everything. If hardline_status=REJECT, final_decision=reject, "
            "fit_analysis_allowed=false, and technical_fit_percent/technical_fit must be null."
        ),
        "conditional_rule": (
            "Conditional is not a fallback for lack of proof. Use conditional only when there is affirmative "
            "source evidence that eligibility may be possible but one decisive fact remains unresolved. A foreign-local "
            "requisition with no affirmative Spain/cross-border hiring evidence is not automatically conditional."
        ),
        "remote_rule": (
            "Remote is not global remote. Explicit US-only, US Remote, anywhere-in-US, residency, "
            "work-authorization, E-Verify, or state restrictions override a generic Remote label."
        ),
        "mandatory_experience_rule": (
            "Classify required vs preferred vs nice-to-have. Adjacent work, study, labs, or projects "
            "must not be upgraded to direct production experience. Material unmet required experience "
            "can be a hardline reject."
        ),
        "stage_2_fit": (
            "Only when Stage 1 PASS, evaluate direct verified, adjacent/transferable, project/lab/study, "
            "missing, and preferred-only gaps. Fit is informational and can never reverse Stage 1."
        ),
        "post_review_self_audit": [
            "Confirm every current jobs[] posting_id appears exactly once in the returned review payload.",
            "Confirm no returned posting_id falls outside this capture.",
            "Confirm every deterministic hardline_reject=true vacancy is REJECT unless explicitly marked MANUAL_REVIEW for contradictory same-vacancy evidence.",
            "Confirm every REJECT or MANUAL_REVIEW has fit_analysis_allowed=false and no technical-fit score.",
            "Confirm every pursue or strong_pursue passed Stage 1 and has location_eligibility=eligible.",
            "Confirm duplicates are not recommended for pursuit.",
            "Only after these checks pass may results be ranked or summarized across the capture.",
        ],
        "aggregation_rule": (
            "Aggregate, rank, and derive market/application strategy only after all per-job reviews and the final self-audit are complete."
        ),
        "return_contract": "Use response_template exactly for per-job review results.",
    }

    return json.dumps(
        document,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
