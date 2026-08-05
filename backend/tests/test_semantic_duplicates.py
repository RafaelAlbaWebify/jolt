from dataclasses import dataclass

from jolt.semantic_duplicates import (
    descriptions_are_materially_similar,
    group_semantic_duplicates,
    normalize_duplicate_text,
)


@dataclass
class Candidate:
    posting_id: str
    company: str
    title: str
    recommendation: str = "do_not_pursue"
    confidence: str = "high"
    ranking_score: int = 0


def test_normalization_handles_accents_case_and_dashes() -> None:
    assert normalize_duplicate_text("T\u00c9CHNICAL \u2013 Support") == "technical support"


def test_materially_similar_descriptions_match() -> None:
    first = (
        "Provide technical product support across EMEA. Investigate customer "
        "issues, analyse logs, troubleshoot integrations and work with engineering."
    )
    second = (
        "Provide technical product support across EMEA. Investigate customer "
        "issues, analyze logs, troubleshoot integrations, and work with engineering."
    )

    assert descriptions_are_materially_similar(first, second)


def test_materially_different_descriptions_do_not_match() -> None:
    first = (
        "Support payroll customers, configure HR workflows and investigate "
        "employee data synchronisation problems."
    )
    second = (
        "Maintain industrial control systems, diagnose PLC communication and "
        "support factory production equipment."
    )

    assert not descriptions_are_materially_similar(first, second)


def test_ashby_location_variants_form_one_group() -> None:
    madrid = Candidate(
        posting_id="ashby-madrid",
        company="Ashby",
        title="Product Support Specialist - EMEA",
    )
    barcelona = Candidate(
        posting_id="ashby-barcelona",
        company="ASHBY",
        title="Product Support Specialist ? EMEA",
    )

    descriptions = {
        "ashby-madrid": (
            "Support Ashby customers across EMEA, troubleshoot product behaviour, "
            "investigate logs and collaborate with engineering."
        ),
        "ashby-barcelona": (
            "Support Ashby customers across EMEA, troubleshoot product behavior, "
            "investigate logs, and collaborate with engineering."
        ),
    }

    groups = group_semantic_duplicates(
        [madrid, barcelona],
        descriptions=descriptions,
    )

    assert len(groups) == 1
    assert {item.posting_id for item in groups[0]} == {
        "ashby-madrid",
        "ashby-barcelona",
    }


def test_same_company_and_title_with_different_work_remain_separate() -> None:
    first = Candidate(
        posting_id="first",
        company="Example",
        title="Technical Support Specialist",
    )
    second = Candidate(
        posting_id="second",
        company="Example",
        title="Technical Support Specialist",
    )

    descriptions = {
        "first": ("Support payroll applications, HR workflows and employee data integrations."),
        "second": ("Support industrial PLC systems, production machinery and factory networks."),
    }

    groups = group_semantic_duplicates(
        [first, second],
        descriptions=descriptions,
    )

    assert len(groups) == 2


def test_best_actionable_member_becomes_canonical() -> None:
    blocked = Candidate(
        posting_id="blocked",
        company="Example",
        title="Technical Support Specialist",
        recommendation="do_not_pursue",
        ranking_score=0,
    )
    actionable = Candidate(
        posting_id="actionable",
        company="Example",
        title="Technical Support Specialist",
        recommendation="strong_pursue",
        ranking_score=79,
    )

    descriptions = {
        "blocked": ("Support the same SaaS platform and investigate customer API failures."),
        "actionable": ("Support the same SaaS platform and investigate customer API failures."),
    }

    groups = group_semantic_duplicates(
        [blocked, actionable],
        descriptions=descriptions,
    )

    assert len(groups) == 1
    assert groups[0][0].posting_id == "actionable"
    assert groups[0][1].posting_id == "blocked"
