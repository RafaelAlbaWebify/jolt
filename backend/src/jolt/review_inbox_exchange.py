from __future__ import annotations

import json

from sqlalchemy.orm import Session

from jolt.ai_review_pack import build_ai_review_json
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
            "Resolve the employer's official ATS/careers posting when possible. Verified official "
            "ATS/careers evidence outranks LinkedIn card/location metadata and LinkedIn vacancy text "
            "when they conflict. Record the official source URL, status, location, and evidence."
        ),
        "context_use": (
            "Use JOLT context as candidate/search state. Candidate evidence inventory is user-owned. "
            "Do not invent experience, certifications, credentials, or production depth."
        ),
        "pre_application_pipeline": [
            "1. Parse the complete vacancy.",
            "2. Resolve the official employer ATS/careers source when possible.",
            "3. Validate geography, remote scope, work authorization, salary/conditions and mandatory non-technical eligibility.",
            "4. Evaluate technical fit independently even when eligibility blocks applying; eligibility must not be converted into low technical fit.",
            "5. For every relevant technology/skill, classify candidate evidence as confirmed_experience, not_in_profile_yet, unknown_ask_user, or confirmed_gap.",
            "6. If a decisive requirement is unknown_ask_user, return NEEDS_USER_CONFIRMATION and explicit questions_for_user; do not penalize it as a gap.",
            "7. Use the complete credential inventory only when credential_inventory_complete=true; select at most 5-6 relevant credentials and never invent one.",
            "8. Decide APPLY/SKIP and independently decide whether the company should be watched.",
            "9. Only for APPLY decisions, recommend the CV master from vacancy language + role family. Do not tailor a CV for a skipped job.",
        ],
        "official_source_rule": (
            "Try to locate the employer's official ATS/careers vacancy. If verified, set "
            "official_source_status=verified and use it as geographic/employment authority over "
            "LinkedIn. If not found or unavailable, say so explicitly; never fabricate an ATS URL."
        ),
        "remote_scope_rule": (
            "Remote is not worldwide. Classify remote_scope as worldwide, EMEA, Europe, Spain, "
            "specific_country, USA_only, region_bound, or unknown. Treat phrases such as Remote USA "
            "- East Coast, US East Coast, North America region, must be based in, work authorization "
            "required, or a North America responsibility paired with a counterpart in EMEA as "
            "restrictive evidence. Generic Remote never overrides explicit territory restrictions."
        ),
        "eligibility_fit_separation": (
            "Eligibility and technical fit are orthogonal. A USA-only role may have technical_fit=95 "
            "and still be SKIP_BY_LOCATION. Never reduce technical fit merely because geography, work "
            "authorization, salary, or conditions make the role ineligible."
        ),
        "decision_codes": {
            "APPLY_HIGH_FIT": "Eligible and strong technical/role fit.",
            "APPLY_MEDIUM_FIT": "Eligible and credible medium fit.",
            "SKIP_BY_LOCATION": "Hiring territory or remote scope excludes the candidate location.",
            "SKIP_BY_WORK_AUTHORIZATION": "Required work authorization/visa/employment status is blocked.",
            "SKIP_BY_SALARY_CONDITIONS": "Explicit salary or non-negotiable conditions fail saved preferences.",
            "SKIP_BY_TECHNICAL_FIT": "Only for confirmed technical gaps materially blocking the role.",
            "TARGET_COMPANY_WATCH": "Use only when company targeting itself is the primary decision; normally combine a concrete SKIP code with company_watch=true.",
            "NEEDS_USER_CONFIRMATION": "A decisive experience fact is unknown and must be asked before applying or rejecting on technical grounds.",
        },
        "experience_evidence_rule": (
            "Absence from LinkedIn/CV is not evidence of absence. First consult "
            "reasoning_context.candidate_evidence_inventory. confirmed_experience and "
            "not_in_profile_yet count as evidence. unknown_ask_user must create a question and must "
            "not be scored as unmet. confirmed_gap means the user has actually confirmed the gap."
        ),
        "linkedin_skill_feedback_rule": (
            "When relevant experience is confirmed and the skill is absent from the known LinkedIn "
            "skills list, add it to linkedin_skill_suggestions. Prefer durable/transversal skills "
            "over one-off vacancy wording; still allow role-specific suggestions when genuinely reusable."
        ),
        "credential_rule": (
            "The user owns 38 credential entries. Do not rely only on CV masters. Use the complete "
            "candidate credential inventory when available and select at most 5-6 most relevant. "
            "If inventory is incomplete, do not invent or finalize certification recommendations. "
            "A DP-300 Cert Prep course is not the Microsoft DP-300 certification."
        ),
        "cv_master_rule": (
            "For an English vacancy choose an English master; for Spanish choose Spanish. "
            "Application Support / Technical Support / SaaS roles use Application Support master. "
            "Systems / Infrastructure / Automation roles use Systems & Automation master. "
            "Master files are immutable: master -> copy -> tailor copy -> formatting QA -> apply."
        ),
        "cv_format_rule": (
            "Tailoring must preserve exactly font, sizes, bold, colors, structure, page breaks, and "
            "two pages. Company=black bold; job title=blue bold; dates/location=black normal; "
            "certifications=credential name only bold; skills=category before ':' only bold; "
            "projects=title bold and description normal. After replaceAllText, verify textStyle "
            "because Google Docs may inherit bold/style from the replaced run."
        ),
        "company_watch_rule": (
            "If the current role is ineligible but the company/role family is a strong target, set "
            "company_watch=true with a reason and reusable role patterns. The job keeps its concrete "
            "SKIP reason; company watch is a separate durable fact."
        ),
        "schedule_rule": (
            "Shift pattern, night work, weekends, maintenance windows, and on-call participation are "
            "informational unless saved preferences explicitly exclude them."
        ),
        "professional_refresh_rule": (
            "Professional-domain refresh/training can support already-existing experience only when "
            "the user-owned context says so. Do not invent specialist production depth."
        ),
        "technical_fit_rule": (
            "Evaluate direct verified, adjacent/transferable, project/lab/study, unknown, and confirmed "
            "gaps. Technical fit can never make an ineligible role eligible, but it should still be "
            "recorded for market learning and company-watch decisions."
        ),
        "post_review_self_audit": [
            "Every jobs[] posting_id appears exactly once and no extra posting_id is returned.",
            "Every official_source_status=verified result has a real official_source_url and evidence.",
            "Every USA_only/region-bound incompatible role is SKIP_BY_LOCATION.",
            "No unknown_ask_user item is treated as an unmet/confirmed technical gap.",
            "SKIP_BY_TECHNICAL_FIT has at least one confirmed_gap.",
            "APPLY decisions have eligible geography, clear work authorization, no blocked conditions, and no unresolved user questions.",
            "No certification recommendation is returned when the complete credential inventory is unavailable.",
            "CV master/certification/tailoring guidance is only produced after eligibility and decisioning, never before.",
        ],
        "aggregation_rule": (
            "Aggregate market/application strategy only after all per-job reviews and self-audit."
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
