from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.ai_review_opportunity_index import list_ai_review_opportunity_index
from jolt.ai_review_pack import build_ai_review_document, build_ai_review_json
from jolt.capture_archival import ARCHIVED_CAPTURE_STATUS
from jolt.database import CaptureItem, CaptureRun
from jolt.global_context import build_global_context_snapshot, global_context_version


def enrich_review_inbox_document(document: dict[str, object]) -> dict[str, object]:
    """Add JOLT's durable reasoning context to an AI review document."""
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
            "official ATS/careers source verification for location and work model",
            "location and hiring territory",
            "employment and work-authorization constraints",
            "onsite, commute, travel, and field constraints",
            "mandatory language requirements",
            "mandatory certification or clearance requirements",
            "mandatory experience and other explicit non-negotiables",
        ],
        "deterministic_location_authority": (
            "If jobs[].location_hardline_evidence.hardline_reject is true, Stage 1 MUST return REJECT, "
            "location_eligibility=ineligible, geography_status=ineligible, final_decision=reject, "
            "fit_analysis_allowed=false, and technical_fit_percent/technical_fit=null. Do not reinterpret "
            "or soften deterministic hardline evidence in the AI review; JOLT will reject a contradictory return payload."
        ),
        "deterministic_language_authority": (
            "Treat jobs[].language_hardline_evidence as deterministic Stage 1 evidence. If hardline_reject=true, "
            "return hardline_status=REJECT, language_status=blocked, final_decision=reject, "
            "fit_analysis_allowed=false, and no technical-fit score. Preserve the supplied reason code/evidence, "
            "including LANGUAGE_REQUIREMENT_UNMET or UNSUPPORTED_JOB_LANGUAGE. If manual_review=true, return "
            "hardline_status=MANUAL_REVIEW and language_status=conditional; do not score fit. A preferred/nice-to-have "
            "language must not cause rejection. Explicit OR alternatives are satisfied when the candidate has any one "
            "of the permitted languages."
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
        "source_verification_rule": (
            "LinkedIn is a discovery source, not the final authority for work model or hiring location. "
            "Before treating a LinkedIn Remote label as confirmed, locate the employer's official ATS, "
            "official careers page, or company job page when one exists. Record linkedin_work_model, "
            "official_work_model, authoritative_source, official_source_url, source_conflict, "
            "remote_status, location_verification_status and source_confidence. Official ATS/careers "
            "evidence outranks LinkedIn. If sources diverge, set source_conflict=true, "
            "location_verification_status=conflict and remote_status=not_confirmed_remote; geography "
            "must remain conditional/unknown and the final decision cannot be pursue/strong_pursue "
            "until the conflict is resolved. If no official source can be found, do not convert a "
            "LinkedIn Remote label into confirmed_remote."
        ),
        "remote_rule": (
            "Remote is not global remote. Explicit US-only, US Remote, anywhere-in-US, residency, "
            "work-authorization, E-Verify, or state restrictions override a generic Remote label. "
            "A LinkedIn Remote badge alone is insufficient evidence for REMOTE_ELIGIBLE."
        ),
        "schedule_rule": (
            "Shift pattern, night work, weekends, maintenance windows, and on-call participation are "
            "informational only unless the current user-owned preferences explicitly exclude them. "
            "They must not independently cause Stage 1 rejection when excluded_shifts is empty."
        ),
        "professional_refresh_rule": (
            "Explicit user-owned/AI-context professional-domain refresh records may state that a completed "
            "training track systematizes and refreshes an already-existing professional domain with a stated "
            "minimum number of real-world years. Treat the stated years as professional evidence for the "
            "domain, and the completed track as recent structured/hands-on refresh evidence. Do not invent "
            "additional years or specialist production depth beyond the stated domain."
        ),
        "mandatory_experience_rule": (
            "Classify required vs preferred vs nice-to-have. Do not hard-reject merely because a required "
            "technology is not named verbatim in one profile capture when current context contains direct "
            "professional-domain evidence plus a completed refresh. Reserve mandatory-experience hard rejects "
            "for materially different specializations or explicit deep/specialist production requirements "
            "that the candidate evidence does not support."
        ),
        "stage_2_fit": (
            "Only when Stage 1 PASS, evaluate direct verified, adjacent/transferable, project/lab/study, "
            "missing, and preferred-only gaps. Fit is informational and can never reverse Stage 1."
        ),
        "post_review_self_audit": [
            "Confirm every current jobs[] posting_id appears exactly once in the returned review payload.",
            "Confirm no returned posting_id falls outside this capture.",
            "Confirm every deterministic location hardline_reject=true vacancy is REJECT.",
            "Confirm every deterministic language hardline_reject=true vacancy is REJECT with language_status=blocked.",
            "Confirm every deterministic language manual_review=true vacancy is MANUAL_REVIEW with language_status=conditional.",
            "Confirm every REJECT or MANUAL_REVIEW has fit_analysis_allowed=false and no technical-fit score.",
            "Confirm every pursue or strong_pursue passed Stage 1 and has location_eligibility=eligible.",
            "Confirm every LinkedIn-Remote pursue/strong_pursue has official-source verification, confirmed_remote, and no source conflict.",
            "Confirm every source conflict remains conditional/unknown geography and is not recommended for pursuit.",
            "Confirm duplicates are not recommended for pursuit.",
            "Only after these checks pass may results be ranked or summarized across the capture.",
        ],
        "aggregation_rule": (
            "Aggregate, rank, and derive market/application strategy only after all per-job reviews and the final self-audit are complete."
        ),
        "return_contract": "Use response_template exactly for per-job review results.",
    }

    return document


def build_review_inbox_exchange_json(session: Session) -> bytes:
    """Enrich the proven AI review batch with JOLT's durable reasoning context."""

    document = json.loads(build_ai_review_json(session))
    enriched = enrich_review_inbox_document(document)
    return json.dumps(
        enriched,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")


def build_current_review_inbox_bundle(session: Session) -> dict[str, object]:
    """Export every currently pending Review Inbox posting across active capture runs."""

    pending_posting_ids = {
        item.posting_id
        for item in list_ai_review_opportunity_index(session)
        if item.ai_review_status == "awaiting_ai_review"
    }
    if not pending_posting_ids:
        raise ValueError("No pending Review Inbox jobs exist to export for AI review.")

    groups: dict[str, set[str]] = defaultdict(set)
    unresolved: list[str] = []

    for posting_id in sorted(pending_posting_ids):
        match = session.execute(
            select(CaptureItem, CaptureRun)
            .join(CaptureRun, CaptureRun.id == CaptureItem.capture_run_id)
            .where(CaptureItem.posting_id == posting_id)
            .where(CaptureItem.detail_status == "verified")
            .where(CaptureRun.status != ARCHIVED_CAPTURE_STATUS)
            .where(CaptureRun.status != "running")
            .order_by(CaptureRun.started_at.desc(), CaptureItem.id.desc())
            .limit(1)
        ).first()
        if match is None:
            unresolved.append(posting_id)
            continue
        item, run = match
        groups[run.id].add(posting_id)

    if unresolved:
        raise ValueError(
            "Pending Review Inbox jobs lack reviewable capture provenance: "
            + ", ".join(unresolved)
        )

    review_groups = [
        build_ai_review_document(
            session,
            capture_run_id=capture_run_id,
            posting_ids=posting_ids,
        )
        for capture_run_id, posting_ids in sorted(groups.items())
    ]
    jobs = [
        job
        for group in review_groups
        for job in group.get("jobs", [])
        if isinstance(job, dict)
    ]

    bundle: dict[str, object] = {
        "pack_type": "jolt_ai_review_bundle_input",
        "pack_version": "1.0",
        "review_contract_version": "1.2",
        "classification_authority": "external_ai",
        "capture_run_ids": [group["capture_run_id"] for group in review_groups],
        "counts": {
            "capture_runs": len(review_groups),
            "capture_items": len(jobs),
            "verified_items": sum(
                int(group.get("counts", {}).get("verified_items", 0))
                for group in review_groups
                if isinstance(group.get("counts"), dict)
            ),
        },
        "review_groups": review_groups,
        "jobs": jobs,
        "response_template": {
            "contract_type": "jolt_ai_review_bundle",
            "contract_version": "1.0",
            "reviews": [group["response_template"] for group in review_groups],
        },
    }
    return enrich_review_inbox_document(bundle)
