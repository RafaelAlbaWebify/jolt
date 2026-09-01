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
        "source_priority": "vacancy body evidence outranks card labels, search filters, and inferred geography",
        "context_use": "Use JOLT context as candidate/search state; do not invent unsupported experience.",
        "return_contract": "Use response_template exactly for per-job review results.",
    }

    return json.dumps(
        document,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
