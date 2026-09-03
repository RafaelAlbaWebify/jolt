from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeScope
from jolt.unified_ai_work_package import (
    UnifiedAIUpdate,
    _validate_unified_update,
    build_unified_ai_work_package,
)


def _exchange(section: str) -> AIExchangeInput:
    return AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id=f"exchange-{section}",
        context_version="context-1",
        scope=AIExchangeScope(
            section=section,
            analysis_types=["audit_result"],
        ),
        context={"duplicated": "must be removed"},
        evidence={},
        protected_state={},
        requested_output={},
    )


def test_unified_package_exposes_one_canonical_candidate_evidence_surface(monkeypatch) -> None:
    from jolt import unified_ai_work_package as module

    monkeypatch.setattr(
        module,
        "build_global_context_snapshot",
        lambda: {"job_search_preferences": {"languages": ["English", "Spanish"]}},
    )
    monkeypatch.setattr(module, "global_context_version", lambda _snapshot: "context-1")
    monkeypatch.setattr(
        module,
        "build_candidate_evidence_ledger",
        lambda _session: {
            "schema_version": "1.0",
            "source_evidence": [
                {
                    "evidence_ref": "linkedin_capture:experience",
                    "title": "Experience",
                    "visible_text": "Verified employment evidence",
                }
            ],
            "reviewed_summary": {},
            "counts": {"exported_profile_sources": 1},
            "authority_notes": {},
        },
    )
    monkeypatch.setattr(
        module,
        "_review_inbox_payload",
        lambda _session: {
            "response_template": {"contract_version": "1.1"},
            "candidate_evidence_location": "candidate_evidence",
        },
    )

    builders = [
        "build_market_intelligence_exchange",
        "build_application_outcomes_exchange",
        "build_linkedin_profile_exchange",
        "build_skills_preparation_exchange",
        "build_professional_evidence_exchange",
        "build_search_preference_exchange",
        "build_data_quality_exchange",
    ]
    sections = [
        "market_insights",
        "applications",
        "linkedin_profile",
        "skills_gaps",
        "professional_evidence",
        "search_preferences",
        "data_quality",
    ]
    for builder, section in zip(builders, sections, strict=True):
        monkeypatch.setattr(module, builder, lambda _session, section=section: _exchange(section))

    package = build_unified_ai_work_package(object())

    assert package.candidate_evidence["source_evidence"][0]["evidence_ref"] == (
        "linkedin_capture:experience"
    )
    assert package.review_inbox is not None
    assert package.review_inbox["candidate_evidence_location"] == "candidate_evidence"
    assert all(exchange.context == {} for exchange in package.exchanges)
    instructions = package.instructions["candidate_evidence"]
    assert "Never upgrade" in instructions
    assert "evidence_ref" in instructions


def _update(context_patch: dict) -> UnifiedAIUpdate:
    return UnifiedAIUpdate(
        package_id="package-1",
        source_context_version="context-1",
        reviewed_at=datetime.now(UTC),
        review_version="candidate-evidence-test",
        context_patch=context_patch,
    )


def test_unified_update_validates_candidate_claim_provenance_before_persistence(monkeypatch) -> None:
    from jolt import unified_ai_work_package as module

    monkeypatch.setattr(module, "build_global_context_snapshot", lambda: {})
    monkeypatch.setattr(module, "global_context_version", lambda _snapshot: "context-1")

    valid = _update(
        {
            "candidate_evidence_summary": {
                "schema_version": "1.0",
                "as_of": "2026-09-03",
                "claims": [
                    {
                        "claim": "Intune administration",
                        "evidence_level": "project_lab",
                        "evidence_summary": "Lab/project evidence only.",
                        "evidence_refs": ["linkedin_capture:skills"],
                    }
                ],
            }
        }
    )
    _validate_unified_update(valid)
    assert valid.context_patch["candidate_evidence_summary"]["claims"][0][
        "evidence_level"
    ] == "project_lab"

    invalid = _update(
        {
            "candidate_evidence_summary": {
                "schema_version": "1.0",
                "claims": [
                    {
                        "claim": "3+ years primary Entra administration",
                        "evidence_level": "professional",
                        "evidence_refs": [],
                    }
                ],
            }
        }
    )
    with pytest.raises(ValidationError):
        _validate_unified_update(invalid)
