from __future__ import annotations

from dataclasses import dataclass

import pytest

from jolt.evaluation_strategy import CapabilityEvidence, RoleFamily, StrategyProfile
from jolt.job_search_preferences import JobSearchPreferences
from jolt.language_hardline import analyze_language_evidence
from jolt.strategy_runtime import calibrated_strategy_assessment


def _profile() -> StrategyProfile:
    return StrategyProfile(
        schema_version=1,
        profile_id="historical-hardline-regression",
        version=1,
        role_families=[
            RoleFamily(
                id="it_operations",
                label="IT Operations / Support",
                priority="primary",
                terms=[
                    "it support",
                    "technical support",
                    "application support",
                    "infrastructure engineer",
                    "systems administrator",
                    "cloud administrator",
                    "customer support engineer",
                ],
                strategic_value=95,
            )
        ],
        capabilities=[
            CapabilityEvidence(
                id="windows_identity",
                label="Windows / Active Directory / Microsoft 365",
                terms=[
                    "windows",
                    "active directory",
                    "microsoft 365",
                    "entra id",
                    "intune",
                    "vmware",
                    "technical support",
                    "application support",
                ],
                evidence_level=5,
            )
        ],
    )


@dataclass(frozen=True)
class HistoricalCase:
    name: str
    original: str
    blocker: str
    location: str
    description: str
    expected: str


CASES = (
    HistoricalCase(
        "PSI CRO France",
        "preparing/positive application path",
        "France-based employment",
        "St.-Maur-des-Fossés, Île-de-France, France",
        "Full-time employment based in France. IT infrastructure support with Windows, Active Directory and VMware.",
        "reject",
    ),
    HistoricalCase(
        "Nortal",
        "pursue, technical fit 88",
        "mandatory German",
        "Germany",
        "Sehr gute Deutschkenntnisse sowie gute Englischkenntnisse in Wort und Schrift. IT Support.",
        "reject",
    ),
    HistoricalCase(
        "Prosana",
        "pursue, technical fit 84",
        "mandatory Lithuanian",
        "Lithuania",
        "Written English & Lithuanian are required for this technical support role.",
        "reject",
    ),
    HistoricalCase(
        "BV TECH",
        "pursue, technical fit 88",
        "unsupported/required Italian",
        "Italy",
        "Il ruolo richiede esperienza nel supporto IT. Italiano fluente obbligatorio per il supporto agli utenti.",
        "reject",
    ),
    HistoricalCase(
        "ACTION ICT",
        "pursue, technical fit 88",
        "unsupported/required Italian",
        "Italy",
        "Luogo di lavoro: Bologna con attuale parziale smart working. IT support specialist.",
        "reject",
    ),
    HistoricalCase(
        "Mediatica Digital",
        "positive before language audit",
        "unsupported/required Italian",
        "Italy",
        "La posizione richiede supporto tecnico e conoscenza fluente della lingua italiana.",
        "reject",
    ),
    HistoricalCase(
        "LucidLink",
        "strong_pursue, technical fit 91",
        "US-only employment",
        "United States · Remote",
        "While our ideal candidate is in the Pacific or Mountain time zone, we welcome stellar applicants from anywhere in the US. At least 2 years of Technical Support experience.",
        "reject",
    ),
    HistoricalCase(
        "Unily",
        "strong_pursue, technical fit 92",
        "US-only remote",
        "United States · Remote",
        "Location: United States. Application Support Engineer for the USA careers requisition; hybrid employment terms apply to the role.",
        "reject",
    ),
    HistoricalCase(
        "Prompt Health",
        "pursue, technical fit 92",
        "US-only employment / E-Verify",
        "United States · Remote",
        "Location: United States. Support Engineer for healthcare SaaS; US employment eligibility applies to this requisition.",
        "reject",
    ),
    HistoricalCase(
        "Nebius",
        "strong_pursue, technical fit 91",
        "US-only plus unmet primary IAM experience",
        "United States · Remote",
        "Location: United States. Microsoft Entra ID is the primary identity plane and center of gravity for the role; Google Workspace, Cloud Identity and Google Cloud IAM form a second substantial domain.",
        "reject",
    ),
    HistoricalCase(
        "Stripe/Metronome",
        "positive before source-first geography correction",
        "US requisition",
        "United States",
        "This position is within the United States and supports cloud infrastructure.",
        "reject",
    ),
    HistoricalCase(
        "GT Global Services",
        "pursue, technical fit 88",
        "US work authorization + mandatory networking certification",
        "United States · Remote",
        "Must be authorized to work in the United States. CCNA certification required. IT support role.",
        "reject",
    ),
    HistoricalCase(
        "Lumen",
        "pursue, technical fit 80",
        "Poland-only employment",
        "Poland · Remote",
        "Location: Poland. This opportunity is a work from home position in a Virtual IT Service Desk.",
        "reject",
    ),
    HistoricalCase(
        "Taraki/ARC9",
        "pursue, technical fit 80",
        "Lahore/local shift",
        "Lahore, Pakistan",
        "Applicants must be based in Lahore and work the local support shift.",
        "reject",
    ),
    HistoricalCase(
        "Exa Capital/PrecisionCare",
        "pursue, technical fit 88",
        "US-only + mandatory EHR/healthcare SaaS experience",
        "United States · Remote",
        "Location: Remote (USA). Required Education and Qualifications: 2+ years of customer or technical support experience; 1+ years of experience supporting Electronic Health Records (EHR) or other healthcare SaaS applications.",
        "reject",
    ),
    HistoricalCase(
        "KPA",
        "pursue, technical fit 80",
        "US work eligibility",
        "United States · Remote",
        "Candidates must be legally authorized to work in the United States. Remote support role.",
        "reject",
    ),
    HistoricalCase(
        "Russell Tobin",
        "pursue, technical fit 80",
        "W2 / US-only",
        "United States",
        "W2 only. Applicants must be authorized to work in the United States.",
        "reject",
    ),
    HistoricalCase(
        "Fever",
        "positive/conditional before source verification",
        "Mexico City hiring location",
        "Mexico City, Mexico",
        "Technical support role based in Mexico City.",
        "reject",
    ),
    HistoricalCase(
        "Aircall",
        "pursue, technical fit 80",
        "Portugal-only remote",
        "Portugal · Remote",
        "Remote from Portugal. SaaS technical support.",
        "reject",
    ),
    HistoricalCase(
        "Moxie",
        "pursue, technical fit 80",
        "Philippines-only remote",
        "Philippines · Remote",
        "Remote Philippines customer technical support role.",
        "reject",
    ),
    HistoricalCase(
        "Tailscale",
        "pursue, technical fit 86",
        "US remote + legal authorization",
        "United States · Remote",
        "Remote US. Must be legally authorized to work in the United States.",
        "reject",
    ),
    HistoricalCase(
        "Outmarket AI",
        "pursue, technical fit 84",
        "US/India employment scope",
        "United States",
        "IT Engineer. Location: United States. Remote-first flexibility; own identity, devices, SaaS, endpoint security and internal IT operations.",
        "reject",
    ),
    HistoricalCase(
        "PTG/Courser",
        "pursue, technical fit 88",
        "US-only remote",
        "United States",
        "IT Support Services II-Help Desk. Location: United States. Remote work is scoped to the United States.",
        "reject",
    ),
    HistoricalCase(
        "Roy Jorgensen",
        "conditional, priority 74, technical fit 86",
        "Frederick, Maryland / US employment",
        "Frederick, MD",
        "IT Support & Operations Specialist. Frederick, Maryland. 401(k), US medical benefits, MVR and controlled-substance testing.",
        "reject",
    ),
    HistoricalCase(
        "Anaconda",
        "pursue, technical fit 88",
        "Austin TX / US authorization",
        "Austin, TX",
        "Location: Austin, TX. IT Support Specialist. What US State do you live in? US employment terms and benefits apply.",
        "reject",
    ),
    HistoricalCase(
        "Beckman Coulter Italy",
        "reject; first parser reason included false state token before fix",
        "mandatory Italian / Italy role",
        "Italy",
        "Field technical support in Italy. Italian fluency is required. Frequent travel within Italy.",
        "reject",
    ),
    HistoricalCase(
        "Tilla",
        "conditional, technical fit 92",
        "territorial employment from Spain not established",
        "Remote",
        "Fully remote role for a distributed team. Working hours CET +/- 2. Employment countries are not stated.",
        "hold",
    ),
    HistoricalCase(
        "Jobright",
        "conditional / VERIFY FIRST",
        "UK/full-time remote but Spain eligibility unproven",
        "Remote",
        "Full-time remote role advertised for the UK. No statement confirms employment or contracting from Spain.",
        "hold",
    ),
    HistoricalCase(
        "TheyDo",
        "strong_pursue, technical fit 91",
        "USA East Coast customer territory",
        "Remote",
        "Our fully remote team spans 27 countries. You will be the technical face of TheyDo for customers in North America and work the USA East Coast customer window.",
        "hold",
    ),
    HistoricalCase(
        "Newmark",
        "high-fit cloud/support candidate",
        "Poland hiring location",
        "Mazowieckie, Poland",
        "Senior Cloud Administrator supporting Microsoft 365, Entra ID, Intune and Windows infrastructure.",
        "reject",
    ),
    HistoricalCase(
        "ENCAMINA",
        "pursue, eligible, technical fit 88",
        "conflicting work model: LinkedIn remote vs official hybrid",
        "Remote",
        "LinkedIn says Remote. Official employer source says Hybrid in Sagunto. Authoritative work model conflict must be verified.",
        "hold",
    ),
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_historical_false_positive_never_auto_pursues(case: HistoricalCase) -> None:
    assessment = calibrated_strategy_assessment(
        _profile(),
        title="IT Support / Infrastructure Support",
        location=case.location,
        description=case.description,
    )

    assert assessment.recommendation not in {"pursue", "strong_pursue"}, (
        f"{case.name}: historical={case.original}; blocker={case.blocker}; "
        f"current recommendation={assessment.recommendation}; "
        f"eligibility={assessment.eligibility}; blockers={assessment.blockers}; "
        f"uncertainties={assessment.uncertainties}"
    )

    if case.expected == "reject":
        assert assessment.recommendation == "do_not_pursue", (
            f"{case.name}: expected a hard reject for {case.blocker}; "
            f"got {assessment.recommendation}, blockers={assessment.blockers}, "
            f"uncertainties={assessment.uncertainties}"
        )
    else:
        assert assessment.recommendation in {"pursue_if_condition_met", "review_manually"}, (
            f"{case.name}: ambiguous evidence must stay HOLD/VERIFY; "
            f"got {assessment.recommendation}"
        )


@pytest.mark.parametrize(
    ("description", "expected_fragment"),
    [
        (
            "Security clearance is required before start.",
            "clearance",
        ),
        (
            "CCNA certification required for this support position.",
            "certification",
        ),
        (
            "Minimum 5 years of professional experience in infrastructure support is required.",
            "experience",
        ),
    ],
)
def test_generic_explicit_hard_requirements_cannot_be_overridden_by_fit(
    description: str,
    expected_fragment: str,
) -> None:
    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Senior IT Support Engineer",
        location="Spain · Remote",
        description=description,
    )

    assert assessment.recommendation not in {"pursue", "strong_pursue"}
    combined = " ".join((*assessment.blockers, *assessment.uncertainties)).casefold()
    assert expected_fragment in combined


def test_required_certification_is_allowed_when_profile_evidences_it() -> None:
    profile = _profile()
    profile.capabilities.append(
        CapabilityEvidence(
            id="ccna",
            label="CCNA",
            terms=["ccna", "cisco certified network associate"],
            evidence_level=5,
        )
    )

    assessment = calibrated_strategy_assessment(
        profile,
        title="IT Support Engineer",
        location="Spain · Remote",
        description="CCNA certification required for this support position.",
    )

    assert not any(
        "mandatory certification not evidenced" in blocker.casefold()
        for blocker in assessment.blockers
    )


def test_preferred_certification_does_not_create_a_hard_blocker() -> None:
    assessment = calibrated_strategy_assessment(
        _profile(),
        title="IT Support Engineer",
        location="Spain · Remote",
        description="CCNA certification preferred but not required.",
    )

    assert not any("certification" in blocker.casefold() for blocker in assessment.blockers)
    assert not any(
        "certification" in uncertainty.casefold() for uncertainty in assessment.uncertainties
    )


def test_unspecified_mandatory_certification_is_hold_verify_not_auto_pursue() -> None:
    assessment = calibrated_strategy_assessment(
        _profile(),
        title="IT Support Engineer",
        location="Spain · Remote",
        description="A relevant networking certification is required for this position.",
    )

    assert assessment.recommendation == "pursue_if_condition_met"
    assert any("certification" in item.casefold() for item in assessment.uncertainties)


@pytest.mark.parametrize(
    ("name", "description"),
    [
        (
            "Nortal",
            "IT Support. Sehr gute Deutschkenntnisse sowie gute Englischkenntnisse "
            "in Wort und Schrift are required.",
        ),
        (
            "Prosana",
            "Written English and Lithuanian are required for this technical support role.",
        ),
        (
            "BV TECH",
            "Fluent Italian is required for this IT support position.",
        ),
        (
            "ACTION ICT",
            "Italiano fluente obbligatorio per il supporto tecnico agli utenti.",
        ),
        (
            "Mediatica Digital",
            "La posizione richiede supporto tecnico. Italiano fluente obbligatorio.",
        ),
        (
            "Beckman Coulter Italy",
            "Fluent Italian is required for field technical support in Italy.",
        ),
    ],
)
def test_historical_required_language_cases_are_hard_rejects(
    name: str,
    description: str,
) -> None:
    result = analyze_language_evidence(
        source_text=description,
        preferences=JobSearchPreferences(),
    )

    assert result.hardline_reject, name
    assert not result.manual_review, name


def test_one_year_explicit_minimum_experience_is_hold_verify() -> None:
    assessment = calibrated_strategy_assessment(
        _profile(),
        title="Application Support Engineer",
        location="Spain · Remote",
        description=("At least 1 year of EHR or healthcare SaaS support experience is required."),
    )

    assert assessment.recommendation == "pursue_if_condition_met"
    assert any("experience" in item.casefold() for item in assessment.uncertainties)


def test_clearance_eligibility_is_hold_verify() -> None:
    assessment = calibrated_strategy_assessment(
        _profile(),
        title="IT Support Engineer",
        location="Spain · Remote",
        description="Candidate must be eligible to obtain a security clearance.",
    )

    assert assessment.recommendation == "pursue_if_condition_met"
    assert any("clearance" in item.casefold() for item in assessment.uncertainties)


def test_company_history_does_not_become_candidate_experience_blocker() -> None:
    assessment = calibrated_strategy_assessment(
        _profile(),
        title="IT Support Engineer",
        location="Spain · Remote",
        description=(
            "We are a company with 10+ years of experience delivering managed IT services. "
            "The role provides Windows and Microsoft 365 support."
        ),
    )

    assert assessment.recommendation not in {"pursue_if_condition_met", "review_manually"}
    assert not any("experience" in item.casefold() for item in assessment.uncertainties)


def test_one_evidenced_certification_does_not_hide_a_second_missing_requirement() -> None:
    profile = _profile()
    profile.capabilities.append(
        CapabilityEvidence(
            id="ccna",
            label="CCNA",
            terms=["ccna", "cisco certified network associate"],
            evidence_level=5,
        )
    )

    assessment = calibrated_strategy_assessment(
        profile,
        title="IT Support Engineer",
        location="Spain · Remote",
        description="CCNA certification required. ITIL certification required.",
    )

    assert assessment.recommendation == "do_not_pursue"
    assert any("ITIL" in blocker for blocker in assessment.blockers)


def test_active_clearance_must_have_phrase_is_a_hard_reject() -> None:
    assessment = calibrated_strategy_assessment(
        _profile(),
        title="IT Support Engineer",
        location="Spain · Remote",
        description="Candidates must have an active security clearance before start.",
    )

    assert assessment.recommendation == "do_not_pursue"
    assert any("clearance" in blocker.casefold() for blocker in assessment.blockers)
