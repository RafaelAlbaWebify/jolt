from typing import cast

import pytest
from sqlalchemy.orm import Session

from jolt.professional_intelligence_evidence_review import (
    ProfessionalEvidenceArtifactReview,
    ProfessionalEvidenceRunReview,
    ProfessionalEvidenceSourceReview,
)
from jolt.professional_intelligence_structured_extraction import (
    extract_professional_intelligence,
)


def _review(*, ready: bool = True) -> ProfessionalEvidenceRunReview:
    text = (
        "Local IT Engineer in Vigo, Galicia, Spain. "
        "Experience with Active Directory, DNS, PowerShell, Azure, AWS, VMware and ServiceNow. "
        "Worked with FORVIA and Auxilion. "
        "Interested in remote Application Support and Service Manager opportunities. "
        "Completed AWS Cloud Solutions Architect and Google Cybersecurity training."
    )
    return ProfessionalEvidenceRunReview(
        capture_run_id="run-1",
        run_status="completed",
        integrity_valid=ready,
        review_available=True,
        ready_for_analysis=ready,
        sources=[
            ProfessionalEvidenceSourceReview(
                source_id="linkedin-profile",
                completeness_status="complete",
                artifacts=[
                    ProfessionalEvidenceArtifactReview(
                        id="artifact-1",
                        source_id="linkedin-profile",
                        artifact_type="rendered_text_json",
                        relative_path=(
                            "professional-intelligence/run-1/linkedin-profile/rendered-text.json"
                        ),
                        completeness_status="complete",
                        retention_days=30,
                        exists=True,
                        integrity_valid=ready,
                        reviewable=True,
                        content={"text": text},
                    )
                ],
            )
        ],
    )


def test_structured_extraction_preserves_explicit_source_and_snippet(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.professional_intelligence_structured_extraction.review_professional_capture_evidence",
        lambda _session, _run_id: _review(),
    )

    result = extract_professional_intelligence(cast(Session, object()), "run-1")

    assert result.integrity_verified is True
    assert result.extraction_method == "deterministic_bounded_v1"
    assert [item.value for item in result.role_signals] == [
        "Local IT Engineer",
        "Application Support",
        "Service Manager",
    ]
    assert {item.value for item in result.location_signals} >= {"Vigo", "Galicia", "Spain"}
    assert {item.value for item in result.skills} >= {
        "Active Directory",
        "DNS",
        "PowerShell",
        "Azure",
        "AWS",
        "VMware",
        "ServiceNow",
    }
    assert {item.value for item in result.employers} == {"FORVIA", "Auxilion"}
    assert {item.value for item in result.certifications} == {
        "AWS Cloud Solutions Architect",
        "Google Cybersecurity",
    }
    assert all(item.source_id == "linkedin-profile" for item in result.skills)
    assert all(item.supporting_snippet for item in result.skills)
    assert all(item.confidence == "explicit_match" for item in result.skills)


def test_structured_extraction_refuses_unreviewed_or_invalid_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        "jolt.professional_intelligence_structured_extraction.review_professional_capture_evidence",
        lambda _session, _run_id: _review(ready=False),
    )

    with pytest.raises(ValueError, match="integrity-verified reviewed evidence"):
        extract_professional_intelligence(cast(Session, object()), "run-1")
