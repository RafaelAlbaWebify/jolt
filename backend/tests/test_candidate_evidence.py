from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from jolt import candidate_evidence
from jolt.candidate_evidence import (
    CandidateEvidenceSummary,
    build_candidate_evidence_ledger,
)
from jolt.database import LinkedInPresenceCapture, create_session_factory


def _capture(
    *,
    suffix: str,
    captured_at: datetime,
    category: str = "profile",
    title: str = "Experience",
    source_url: str | None = None,
    content_hash: str | None = None,
    visible_text: str | None = None,
) -> LinkedInPresenceCapture:
    return LinkedInPresenceCapture(
        id=f"capture-{suffix}",
        category=category,
        title=title,
        source_url=source_url or f"https://linkedin.example/in/profile/details/{suffix}",
        visible_text=visible_text or f"Evidence {suffix}",
        notes="",
        content_hash=content_hash or suffix.rjust(64, "0")[-64:],
        previous_capture_id=None,
        changed_since_previous=False,
        captured_at=captured_at,
    )


def test_candidate_evidence_is_provenance_only_deduplicated_and_bounded(
    tmp_path,
    monkeypatch,
) -> None:
    factory = create_session_factory(f"sqlite:///{(tmp_path / 'candidate.db').as_posix()}")
    now = datetime.now(UTC)

    monkeypatch.setattr(
        candidate_evidence,
        "load_global_ai_context",
        lambda: SimpleNamespace(candidate_evidence_summary={}),
    )

    with factory() as session:
        captures = [
            _capture(
                suffix=f"{index:02d}",
                captured_at=now - timedelta(minutes=index),
                title=("Experience" if index % 2 == 0 else "Skills"),
            )
            for index in range(22)
        ]
        duplicate = _capture(
            suffix="duplicate",
            captured_at=now + timedelta(minutes=1),
            title=captures[0].title,
            source_url=captures[0].source_url,
            content_hash=captures[0].content_hash,
            visible_text=captures[0].visible_text,
        )
        unrelated = _capture(
            suffix="activity",
            captured_at=now + timedelta(minutes=2),
            category="activity",
            title="Activity",
        )
        session.add_all([*captures, duplicate, unrelated])
        session.commit()

        ledger = build_candidate_evidence_ledger(session)

    assert ledger["counts"]["available_profile_captures"] == 23
    assert ledger["counts"]["exported_profile_sources"] == 20
    assert ledger["counts"]["source_limit"] == 20
    assert len(ledger["source_evidence"]) == 20
    assert all(item["category"] in {"profile", "public_profile"} for item in ledger["source_evidence"])
    assert all(item["evidence_ref"].startswith("linkedin_capture:") for item in ledger["source_evidence"])

    exported_keys = {
        (item["category"].casefold(), item["source_url"], item["content_hash"])
        for item in ledger["source_evidence"]
    }
    assert len(exported_keys) == len(ledger["source_evidence"])

    # JOLT must not add semantic skill/depth judgments to deterministic source evidence.
    forbidden = {
        "professional_experience",
        "experience_level",
        "years_experience",
        "skill_score",
        "candidate_fit",
    }
    assert all(forbidden.isdisjoint(item) for item in ledger["source_evidence"])


def test_reviewed_candidate_claims_require_controlled_level_and_evidence_refs() -> None:
    summary = CandidateEvidenceSummary.model_validate(
        {
            "schema_version": "1.0",
            "as_of": "2026-09-03",
            "claims": [
                {
                    "claim": "Microsoft 365 support",
                    "evidence_level": "professional",
                    "evidence_summary": "Supported by employment-history evidence.",
                    "evidence_refs": ["linkedin_capture:experience"],
                },
                {
                    "claim": "Intune administration",
                    "evidence_level": "project_lab",
                    "evidence_summary": "Current lab/project exposure; not production depth.",
                    "evidence_refs": ["linkedin_capture:skills"],
                },
                {
                    "claim": "3+ years primary Entra administration",
                    "evidence_level": "explicit_non_claim",
                    "evidence_summary": "No verified evidence supports this production-depth claim.",
                    "evidence_refs": ["linkedin_capture:experience"],
                },
            ],
        }
    )

    assert [claim.evidence_level for claim in summary.claims] == [
        "professional",
        "project_lab",
        "explicit_non_claim",
    ]

    with pytest.raises(ValidationError):
        CandidateEvidenceSummary.model_validate(
            {
                "schema_version": "1.0",
                "claims": [
                    {
                        "claim": "Unsupported professional claim",
                        "evidence_level": "professional",
                        "evidence_refs": [],
                    }
                ],
            }
        )

    with pytest.raises(ValidationError):
        CandidateEvidenceSummary.model_validate(
            {
                "schema_version": "1.0",
                "claims": [
                    {
                        "claim": "Unsupported level",
                        "evidence_level": "assumed_professional",
                        "evidence_refs": ["linkedin_capture:x"],
                    }
                ],
            }
        )
