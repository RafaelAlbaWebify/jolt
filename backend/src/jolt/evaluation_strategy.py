from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from jolt.preparation_estimation import PreparationGap, estimate_preparation_hours

EvidenceLevel = Literal[0, 1, 2, 3, 4, 5]
RolePriority = Literal["primary", "secondary", "opportunistic", "excluded"]
Recommendation = Literal[
    "strong_pursue",
    "pursue",
    "pursue_if_condition_met",
    "review_manually",
    "defer",
    "do_not_pursue",
]
GapType = Literal[
    "ready_now",
    "preparable_in_days",
    "preparable_in_1_to_2_weeks",
    "preparable_in_1_to_3_months",
    "experience_gap",
    "fundamental_mismatch",
    "unknown",
]


class CapabilityEvidence(BaseModel):
    id: str
    label: str
    terms: list[str]
    evidence_level: EvidenceLevel
    transferable_to: list[str] = Field(default_factory=list)
    preparation_topics: list[str] = Field(default_factory=list)


class RoleFamily(BaseModel):
    id: str
    label: str
    priority: RolePriority
    terms: list[str]
    strategic_value: int = Field(default=50, ge=0, le=100)


class EligibilityRule(BaseModel):
    id: str
    label: str
    terms: list[str]
    outcome: Literal["eligible_with_conditions", "uncertain", "ineligible"]


class SpecialistPlatformRequirement(BaseModel):
    id: str
    label: str
    aliases: list[str]
    mandatory_markers: list[str]
    accepted_transfer_markers: list[str] = Field(default_factory=list)


def _default_specialist_platform_requirements() -> list[SpecialistPlatformRequirement]:
    return [
        SpecialistPlatformRequirement(
            id="aveva_pi_system",
            label="AVEVA PI System",
            aliases=[
                "aveva pi system",
                "pi data archive",
                "asset framework",
                "pi interfaces",
                "pi connectors",
                "pi vision",
                "pi points",
            ],
            mandatory_markers=[
                "experiencia demostrable trabajando con",
                "experiencia demostrable con",
                "demonstrable experience working with",
                "proven experience working with",
                "proven experience with",
                "hands-on experience with",
                "must have experience with",
                "required experience with",
            ],
            accepted_transfer_markers=[
                "or equivalent",
                "or similar",
                "training provided",
                "formación incluida",
                "willing to learn",
                "transferable experience accepted",
                "experience preferred",
                "experiencia valorable",
            ],
        )
    ]


class PreparationCapacity(BaseModel):
    hours_per_week: int = Field(default=10, ge=0, le=80)
    default_days_until_technical: int = Field(default=10, ge=0, le=90)
    ai_guided_study: bool = True
    documentation: bool = True
    labs: bool = False
    mock_interviews: bool = True
    maximum_parallel_processes: int = Field(default=3, ge=1, le=20)


class EvaluationWeights(BaseModel):
    role_alignment: int = Field(default=20, ge=0, le=100)
    demonstrated_capability: int = Field(default=25, ge=0, le=100)
    transferable_capability: int = Field(default=10, ge=0, le=100)
    gap_feasibility: int = Field(default=15, ge=0, le=100)
    opportunity_quality: int = Field(default=15, ge=0, le=100)
    strategic_value: int = Field(default=15, ge=0, le=100)

    @model_validator(mode="after")
    def weights_total_one_hundred(self) -> EvaluationWeights:
        if sum(self.model_dump().values()) != 100:
            raise ValueError("Evaluation weights must total 100.")
        return self


class StrategyProfile(BaseModel):
    schema_version: Literal[1] = 1
    profile_id: str
    version: int = Field(ge=1)
    display_name: str = "Local JOLT user"
    role_families: list[RoleFamily]
    capabilities: list[CapabilityEvidence]
    eligibility_rules: list[EligibilityRule] = Field(default_factory=list)
    specialist_platform_requirements: list[SpecialistPlatformRequirement] = Field(
        default_factory=_default_specialist_platform_requirements
    )
    preparation: PreparationCapacity = Field(default_factory=PreparationCapacity)
    weights: EvaluationWeights = Field(default_factory=EvaluationWeights)

    @property
    def version_id(self) -> str:
        return f"{self.profile_id}:v{self.version}"


@dataclass(frozen=True)
class CapabilityAssessment:
    capability_id: str
    label: str
    evidence_level: int
    gap_type: GapType
    matched_terms: tuple[str, ...]
    preparation_topics: tuple[str, ...]


@dataclass(frozen=True)
class StrategyAssessment:
    eligibility: str
    recommendation: Recommendation
    confidence: str
    role_family_id: str | None
    fit_now: int
    fit_by_interview: int
    fit_on_the_job: int
    interview_days: int
    estimated_preparation_hours: int
    dimensions: dict[str, int]
    strengths: tuple[str, ...]
    gaps: tuple[CapabilityAssessment, ...]
    blockers: tuple[str, ...]
    uncertainties: tuple[str, ...]
    preparation_plan: tuple[str, ...]


def default_profile_path() -> Path:
    configured = os.getenv("JOLT_PROFILE_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[3]
    return repository_root / ".jolt" / "profiles" / "active.private.json"


def load_strategy_profile(path: Path | None = None) -> StrategyProfile:
    profile_path = path or default_profile_path()
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    return StrategyProfile.model_validate(payload)


def _normalize_match_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _term_pattern(term: str) -> re.Pattern[str] | None:
    normalized = _normalize_match_text(term)
    if not normalized:
        return None
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    prefix = r"(?<!\w)" if normalized[0].isalnum() else ""
    suffix = r"(?!\w)" if normalized[-1].isalnum() else ""
    return re.compile(prefix + escaped + suffix)


def _matched_terms(text: str, terms: list[str]) -> tuple[str, ...]:
    normalized_text = _normalize_match_text(text)
    matches: list[str] = []
    for term in terms:
        pattern = _term_pattern(term)
        if pattern is not None and pattern.search(normalized_text):
            matches.append(term)
    return tuple(matches)


_WEAK_CAPABILITY_TERMS = frozenset(
    {
        "connectivity",
        "infrastructure",
        "json",
        "network",
    }
)


def _matched_capability_terms(
    title: str,
    text: str,
    capability: CapabilityEvidence,
) -> tuple[str, ...]:
    matches = _matched_terms(text, capability.terms)
    if not matches:
        return ()

    strong_matches = tuple(
        term for term in matches if _normalize_match_text(term) not in _WEAK_CAPABILITY_TERMS
    )
    if strong_matches:
        return matches

    capability_identity = _normalize_match_text(f"{capability.id} {capability.label}")
    identity_anchored_terms = [
        term for term in matches if _normalize_match_text(term) in capability_identity
    ]
    if not identity_anchored_terms:
        return ()

    title_matches = _matched_terms(title, identity_anchored_terms)
    return matches if title_matches else ()


def _role_term_specificity(terms: tuple[str, ...]) -> int:
    return sum(len(_normalize_match_text(term).split()) * 100 + len(term) for term in terms)


def _normalize_role_title(title: str) -> str:
    normalized = _normalize_match_text(title)
    normalized = re.sub(r"(?<=\w)/(?:a|o)(?=\s|$)", "", normalized)
    normalized = re.sub(r"(?<=\w)\((?:a|o)\)(?=\s|$)", "", normalized)
    return normalized


def _is_pure_management_exclusion_family(family: RoleFamily) -> bool:
    if family.priority != "excluded":
        return False

    identity = _normalize_match_text(f"{family.id.replace('_', ' ')} {family.label}")

    return "management" in identity and any(
        marker in identity for marker in ("project", "product", "people")
    )


def _has_explicit_pure_management_title(title: str) -> bool:
    normalized = _normalize_role_title(title)

    patterns = (
        r"\bproject\s+(?:manager|management|lead)\b",
        r"\bproduct\s+(?:manager|management|owner|lead)\b",
        r"\bprogramme?\s+(?:manager|management|lead)\b",
        r"\bpeople\s+(?:manager|management|lead)\b",
    )

    return any(re.search(pattern, normalized) for pattern in patterns)


def _role_family_bucket(family: RoleFamily) -> str | None:
    identity = _normalize_match_text(f"{family.id.replace('_', ' ')} {family.label}")

    if any(
        marker in identity
        for marker in (
            "service management",
            "service manager",
            "gestión de servicios",
            "gestion de servicios",
        )
    ):
        return "service_management"

    # Explicit operations/systems/infrastructure identity must win before
    # generic support wording. IT Operations families can legitimately
    # contain "support" in their labels without becoming support families.
    if any(
        marker in identity
        for marker in (
            "it operations",
            "operations",
            "systems",
            "system",
            "infrastructure",
            "endpoint",
            "sistemas",
            "infraestructura",
        )
    ):
        return "operations"

    if any(
        marker in identity
        for marker in (
            "application support",
            "enterprise application support",
            "support",
            "service desk",
            "help desk",
            "soporte",
        )
    ):
        return "support"

    return None


def _fallback_role_bucket(title: str) -> str | None:
    normalized = _normalize_role_title(title)

    service_management_patterns = (
        r"\bhelp\s*desk manager\b",
        r"\bservice manager\b",
        r"\bcoordinador de soporte\b",
        r"\bcoordinadora de soporte\b",
    )
    if any(re.search(pattern, normalized) for pattern in service_management_patterns):
        return "service_management"

    support_patterns = (
        r"\btechnical support\b",
        r"\btech support\b",
        r"\bapplication support\b",
        r"\btechnical service engineer\b",
        r"\btécnico de soporte\b",
        r"\btecnico de soporte\b",
        r"\bingeniero de soporte\b",
        r"\bingeniera de soporte\b",
        r"\bsoporte técnico\b",
        r"\bsoporte tecnico\b",
        r"\bsoporte de sistemas\b",
        r"\bhelp\s*desk\b",
        r"\bhelpdesk\b",
        r"\bsupport analyst\b",
        r"\bescalation engineer\b",
        r"\btechnical consultant\b",
    )
    if any(re.search(pattern, normalized) for pattern in support_patterns):
        return "support"

    operations_patterns = (
        r"\binfrastructure engineer\b",
        r"\btechops\b",
        r"\bit specialist\b",
        r"\binformation technology specialist\b",
        r"\bespecialista en ti\b",
        r"\btecnico de sistemas\b",
        r"\btécnico de sistemas\b",
        r"\bgestor de sistemas\b",
        r"\badministrador de sistemas\b",
        r"\binfraestructuras ti\b",
        r"\bmonitorizacion\b",
        r"\bmonitorización\b",
        r"\bsystems? administrator\b",
        r"\bsystems? engineer\b",
        r"\bnetwork operations cent(?:er|re)\b",
        r"\bnoc\b",
        r"\bit\s*(?:&|and)\s*operations specialist\b",
        r"\bit operations specialist\b",
    )
    if any(re.search(pattern, normalized) for pattern in operations_patterns):
        return "operations"

    return None


def _select_role_family(
    profile: StrategyProfile,
    title: str,
    location: str,
    description: str,
) -> RoleFamily | None:
    candidates: list[tuple[tuple[int, int, int, int, int], RoleFamily]] = []
    body = "\n".join([location, description])
    normalized_title = _normalize_role_title(title)
    priority_rank = {"primary": 3, "secondary": 2, "opportunistic": 1, "excluded": 0}

    if re.search(r"\b(?:microsoft\s*365|office\s*365|m365)\b", normalized_title):
        m365_families = [
            family
            for family in profile.role_families
            if any(
                marker in _normalize_match_text(f"{family.id.replace('_', ' ')} {family.label}")
                for marker in ("m365", "microsoft 365", "office 365")
            )
        ]
        if m365_families:
            return max(
                m365_families,
                key=lambda family: (
                    priority_rank[family.priority],
                    family.strategic_value,
                ),
            )

    for index, family in enumerate(profile.role_families):
        title_matches = _matched_terms(normalized_title, family.terms)
        body_matches = _matched_terms(body, family.terms)
        if not title_matches and not body_matches:
            continue

        if (
            _is_pure_management_exclusion_family(family)
            and title_matches
            and not _has_explicit_pure_management_title(title)
        ):
            continue

        excluded_title_precedence = int(family.priority == "excluded" and bool(title_matches))
        score = (
            excluded_title_precedence,
            int(bool(title_matches)),
            _role_term_specificity(title_matches) * 1000 + len(title_matches) * 100,
            _role_term_specificity(body_matches) * 10 + len(body_matches),
            priority_rank[family.priority] * 100 + family.strategic_value - index,
        )
        candidates.append((score, family))

    if candidates:
        return max(candidates, key=lambda item: item[0])[1]

    fallback_bucket = _fallback_role_bucket(title)
    if fallback_bucket is None:
        return None

    fallback_candidates: list[tuple[tuple[int, int], RoleFamily]] = []

    for index, family in enumerate(profile.role_families):
        if _role_family_bucket(family) != fallback_bucket:
            continue

        score = (
            priority_rank[family.priority] * 100 + family.strategic_value,
            -index,
        )
        fallback_candidates.append((score, family))

    if not fallback_candidates:
        return None

    return max(
        fallback_candidates,
        key=lambda item: item[0],
    )[1]


def _gap_type(evidence_level: int) -> GapType:
    mapping: dict[int, GapType] = {
        5: "ready_now",
        4: "ready_now",
        3: "preparable_in_days",
        2: "preparable_in_1_to_2_weeks",
        1: "preparable_in_1_to_3_months",
        0: "experience_gap",
    }
    return mapping[evidence_level]


def _capability_score(level: int) -> int:
    return {0: 0, 1: 15, 2: 35, 3: 60, 4: 82, 5: 100}[level]


def _preparation_hours(gap_type: GapType) -> int:
    return {
        "ready_now": 0,
        "preparable_in_days": 4,
        "preparable_in_1_to_2_weeks": 10,
        "preparable_in_1_to_3_months": 35,
        "experience_gap": 120,
        "fundamental_mismatch": 240,
        "unknown": 20,
    }[gap_type]


def _average(values: list[int], default: int = 0) -> int:
    return round(sum(values) / len(values)) if values else default


def _terms_are_near(
    text: str,
    left_terms: list[str],
    right_terms: list[str],
    *,
    maximum_characters: int = 180,
) -> bool:
    normalized = _normalize_match_text(text)
    left_patterns = [pattern for term in left_terms if (pattern := _term_pattern(term)) is not None]
    right_patterns = [
        pattern for term in right_terms if (pattern := _term_pattern(term)) is not None
    ]

    for left_pattern in left_patterns:
        for left_match in left_pattern.finditer(normalized):
            window_start = max(0, left_match.start() - maximum_characters)
            window_end = min(len(normalized), left_match.end() + maximum_characters)
            window = normalized[window_start:window_end]
            if any(right_pattern.search(window) for right_pattern in right_patterns):
                return True

    return False


def _profile_has_direct_platform_evidence(
    profile: StrategyProfile,
    requirement: SpecialistPlatformRequirement,
) -> bool:
    for capability in profile.capabilities:
        if capability.evidence_level <= 0:
            continue
        capability_text = "\n".join(
            [
                capability.id,
                capability.label,
                *capability.terms,
            ]
        )
        if _matched_terms(capability_text, requirement.aliases):
            return True
    return False


def _missing_required_specialist_platforms(
    profile: StrategyProfile,
    text: str,
) -> tuple[SpecialistPlatformRequirement, ...]:
    missing: list[SpecialistPlatformRequirement] = []

    for requirement in profile.specialist_platform_requirements:
        if not _matched_terms(text, requirement.aliases):
            continue

        mandatory = _terms_are_near(
            text,
            requirement.mandatory_markers,
            requirement.aliases,
        )
        if not mandatory:
            continue

        accepted_transfer = _terms_are_near(
            text,
            requirement.accepted_transfer_markers,
            requirement.aliases,
        )
        if accepted_transfer:
            continue

        if _profile_has_direct_platform_evidence(profile, requirement):
            continue

        missing.append(requirement)

    return tuple(missing)


def assess_posting(
    profile: StrategyProfile,
    title: str,
    location: str,
    description: str,
    *,
    days_until_technical: int | None = None,
) -> StrategyAssessment:
    text = "\n".join([title, location, description])
    interview_days = (
        profile.preparation.default_days_until_technical
        if days_until_technical is None
        else max(0, days_until_technical)
    )

    blockers: list[str] = []
    uncertainties: list[str] = []
    eligibility = "eligible"
    for rule in profile.eligibility_rules:
        matches = _matched_terms(text, rule.terms)
        if not matches:
            continue
        message = f"{rule.label}: {', '.join(matches)}."
        if rule.outcome == "ineligible":
            blockers.append(message)
            eligibility = "ineligible"
        elif rule.outcome == "uncertain" and eligibility != "ineligible":
            uncertainties.append(message)
            eligibility = "uncertain"
        elif eligibility == "eligible":
            uncertainties.append(message)
            eligibility = "eligible_with_conditions"

    missing_specialist_platforms = _missing_required_specialist_platforms(profile, text)
    for requirement in missing_specialist_platforms:
        blockers.append(
            f"Missing required direct specialist-platform experience: {requirement.label}."
        )
        eligibility = "ineligible"

    role_family = _select_role_family(profile, title, location, description)
    role_alignment = {
        "primary": 100,
        "secondary": 75,
        "opportunistic": 50,
        "excluded": 0,
    }.get(role_family.priority if role_family else "", 25)
    if role_family and role_family.priority == "excluded":
        blockers.append(f"Excluded role family: {role_family.label}.")

    capability_results: list[CapabilityAssessment] = []
    for capability in profile.capabilities:
        matches = _matched_capability_terms(
            title,
            text,
            capability,
        )
        if not matches:
            continue
        capability_results.append(
            CapabilityAssessment(
                capability_id=capability.id,
                label=capability.label,
                evidence_level=capability.evidence_level,
                gap_type=_gap_type(capability.evidence_level),
                matched_terms=matches,
                preparation_topics=tuple(capability.preparation_topics),
            )
        )

    demonstrated = _average(
        [_capability_score(item.evidence_level) for item in capability_results], default=20
    )
    transferable = _average(
        [
            min(100, _capability_score(capability.evidence_level) + 10)
            for capability in profile.capabilities
            if capability.transferable_to and _matched_terms(text, capability.transferable_to)
        ],
        default=25,
    )

    required_hours = estimate_preparation_hours(
        PreparationGap(
            capability_id=item.capability_id,
            gap_type=item.gap_type,
            preparation_topics=item.preparation_topics,
        )
        for item in capability_results
    )
    available_hours = round(profile.preparation.hours_per_week * interview_days / 7)
    preparation_feasibility = (
        100 if required_hours == 0 else min(100, available_hours * 100 // required_hours)
    )
    strategic_value = role_family.strategic_value if role_family else 35

    dimensions = {
        "role_alignment": role_alignment,
        "demonstrated_capability": demonstrated,
        "transferable_capability": transferable,
        "gap_feasibility": preparation_feasibility,
        "strategic_value": strategic_value,
    }
    weights = profile.weights.model_dump()
    available_weight = sum(weights[key] for key in dimensions)
    fit_now = (
        round(sum(dimensions[key] * weights[key] for key in dimensions) / available_weight)
        if available_weight
        else 0
    )

    preparable = [
        item
        for item in capability_results
        if item.gap_type in {"preparable_in_days", "preparable_in_1_to_2_weeks"}
    ]
    interview_uplift = min(
        25,
        round(preparation_feasibility * len(preparable) / max(1, len(capability_results)) / 4),
    )
    fit_by_interview = min(100, fit_now + interview_uplift)
    fit_on_the_job = min(
        100, max(fit_by_interview, round((fit_by_interview + strategic_value) / 2))
    )

    if missing_specialist_platforms:
        fit_now = 0
        fit_by_interview = 0
        fit_on_the_job = 0

    if eligibility == "ineligible" or (role_family and role_family.priority == "excluded"):
        recommendation: Recommendation = "do_not_pursue"
    elif fit_by_interview >= 80 and fit_now >= 70:
        recommendation = "strong_pursue"
    elif fit_by_interview >= 70:
        recommendation = "pursue"
    elif fit_by_interview >= 58 and preparation_feasibility >= 60:
        recommendation = "pursue_if_condition_met"
    elif uncertainties:
        recommendation = "review_manually"
    elif fit_by_interview >= 45:
        recommendation = "defer"
    else:
        recommendation = "do_not_pursue"

    confidence = "high" if role_family and capability_results else "medium"
    if not role_family or not capability_results:
        confidence = "low"
    if eligibility == "ineligible":
        confidence = "high"

    strengths = tuple(
        f"{item.label}: evidence level {item.evidence_level}; matched {', '.join(item.matched_terms)}."
        for item in capability_results
        if item.evidence_level >= 4
    )
    gaps = tuple(item for item in capability_results if item.evidence_level < 4)
    preparation_plan = tuple(
        topic
        for item in gaps
        if item.gap_type in {"preparable_in_days", "preparable_in_1_to_2_weeks"}
        for topic in item.preparation_topics
    )

    return StrategyAssessment(
        eligibility=eligibility,
        recommendation=recommendation,
        confidence=confidence,
        role_family_id=role_family.id if role_family else None,
        fit_now=fit_now,
        fit_by_interview=fit_by_interview,
        fit_on_the_job=fit_on_the_job,
        interview_days=interview_days,
        estimated_preparation_hours=required_hours,
        dimensions=dimensions,
        strengths=strengths,
        gaps=gaps,
        blockers=tuple(blockers),
        uncertainties=tuple(uncertainties),
        preparation_plan=preparation_plan,
    )
