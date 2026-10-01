from __future__ import annotations

from jolt.job_search_preferences import JobSearchPreferences
from jolt.language_hardline import (
    REASON_LANGUAGE_UNCERTAIN,
    REASON_LANGUAGE_UNMET,
    REASON_UNSUPPORTED_DOCUMENT_LANGUAGE,
    analyze_language_evidence,
    detect_document_language,
)


def _preferences() -> JobSearchPreferences:
    return JobSearchPreferences(
        languages=["Spanish", "English"],
        language_levels={
            "Spanish": "native",
            "English": "professional",
        },
    )


def test_german_mandatory_without_german_rejects() -> None:
    result = analyze_language_evidence(
        source_text=(
            "Technical Support Engineer. German is mandatory for customer communication. "
            "English is also used internally."
        ),
        preferences=_preferences(),
    )

    assert result.hardline_reject is True
    assert REASON_LANGUAGE_UNMET in result.reason_codes
    assert any("German" in reason for reason in result.reasons)


def test_german_preferred_without_german_does_not_reject() -> None:
    result = analyze_language_evidence(
        source_text=(
            "Technical Support Engineer. English is required. German is preferred but not required."
        ),
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    assert result.manual_review is False


def test_english_mandatory_with_professional_english_passes() -> None:
    result = analyze_language_evidence(
        source_text="Professional English proficiency is required for this support role.",
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    assert result.manual_review is False


def test_spanish_mandatory_with_native_spanish_passes() -> None:
    result = analyze_language_evidence(
        source_text="Se requiere español para atender a clientes en España.",
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    assert result.manual_review is False


def test_french_c1_mandatory_without_french_rejects() -> None:
    result = analyze_language_evidence(
        source_text="French C1 is mandatory for daily customer support.",
        preferences=_preferences(),
    )

    assert result.hardline_reject is True
    assert REASON_LANGUAGE_UNMET in result.reason_codes
    requirement = next(item for item in result.requirements if "French" in item.languages)
    assert requirement.minimum_level == "c1"
    assert requirement.classification == "required"


def test_job_written_in_german_without_explicit_german_requirement_rejects() -> None:
    german_text = (
        "Wir suchen eine erfahrene Person für unseren technischen Support. "
        "Die Aufgabe umfasst die Bearbeitung von Anfragen, die Analyse von Störungen "
        "und die Zusammenarbeit mit unserem internationalen Team. Sie unterstützen "
        "unsere Kunden bei technischen Problemen und dokumentieren Lösungen sorgfältig. "
        "Wir bieten eine moderne Arbeitsumgebung, flexible Prozesse und die Möglichkeit, "
        "Verantwortung zu übernehmen. Erfahrung mit Windows, Netzwerken und Ticketsystemen "
        "ist hilfreich. Sie arbeiten selbstständig, strukturiert und zuverlässig mit "
        "anderen Kolleginnen und Kollegen zusammen."
    )

    language, status, confidence = detect_document_language(german_text)
    result = analyze_language_evidence(
        source_text=german_text,
        preferences=_preferences(),
    )

    assert language == "German"
    assert status == "unsupported"
    assert confidence >= 0.7
    assert result.hardline_reject is True
    assert REASON_UNSUPPORTED_DOCUMENT_LANGUAGE in result.reason_codes


def test_german_is_a_plus_does_not_reject() -> None:
    result = analyze_language_evidence(
        source_text=(
            "English is required for the role. German is a plus for some customer conversations."
        ),
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    assert result.manual_review is False


def test_ambiguous_language_wording_requires_manual_review_not_reject() -> None:
    result = analyze_language_evidence(
        source_text=(
            "The role supports customers across Europe. German language skills may be relevant "
            "for some accounts, alongside English customer communication."
        ),
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    assert result.manual_review is True
    assert REASON_LANGUAGE_UNCERTAIN in result.reason_codes


def test_multiple_language_alternatives_pass_when_one_is_available() -> None:
    result = analyze_language_evidence(
        source_text="Fluent German or French or Spanish is required for customer support.",
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    matching = [
        item for item in result.requirements if item.languages == ("German", "French", "Spanish")
    ]
    assert matching
    assert matching[0].classification == "required"


def test_german_or_english_requirement_passes_with_english() -> None:
    result = analyze_language_evidence(
        source_text="German or English is required for this technical support role.",
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    assert result.manual_review is False


def test_nortal_wording_is_detected_as_mandatory_german() -> None:
    result = analyze_language_evidence(
        source_text=(
            "Help Desk Specialist. Sehr gute Deutsch- sowie gute Englischkenntnisse "
            "in Wort und Schrift. Erfahrung im IT-Support und mit Ticketsystemen."
        ),
        preferences=_preferences(),
    )

    assert result.hardline_reject is True
    assert REASON_LANGUAGE_UNMET in result.reason_codes
    assert any(
        "German" in requirement.languages and requirement.classification == "required"
        for requirement in result.requirements
    )


def test_english_document_is_supported() -> None:
    text = (
        "We are looking for a technical support engineer to join our team. "
        "The role will work with customers and internal teams to investigate incidents, "
        "analyse logs, document solutions and provide clear communication. You will support "
        "our applications and work with engineering to resolve issues. Experience with "
        "Windows, APIs and ticketing systems is useful for this position."
    )

    language, status, confidence = detect_document_language(text)

    assert language == "English"
    assert status == "supported"
    assert confidence >= 0.7


def test_spanish_document_is_supported() -> None:
    text = (
        "Buscamos una persona para el equipo de soporte técnico. El puesto incluye la "
        "resolución de incidencias, atención a usuarios y documentación de soluciones. "
        "Trabajarás con nuestro equipo para analizar problemas y mejorar los procesos. "
        "Se requiere experiencia con Windows, redes y herramientas de ticketing, además "
        "de buena comunicación con usuarios y capacidad para trabajar de forma autónoma."
    )

    language, status, confidence = detect_document_language(text)

    assert language == "Spanish"
    assert status == "supported"
    assert confidence >= 0.7


def test_plain_german_market_reference_is_not_a_language_requirement() -> None:
    result = analyze_language_evidence(
        source_text=(
            "This English-language support role serves the German market and German customers. "
            "All internal and customer communication for this position is conducted in English."
        ),
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    assert result.manual_review is False
    assert not any("German" in item.languages for item in result.requirements)


def test_english_c1_is_satisfied_by_professional_english_profile() -> None:
    result = analyze_language_evidence(
        source_text="English C1 is required for written and spoken customer communication.",
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    assert result.manual_review is False


def test_catalan_written_job_is_not_treated_as_spanish() -> None:
    text = (
        "Busquem una persona per incorporar-se al nostre equip de suport tècnic. "
        "El lloc de treball inclou la resolució d'incidències, l'atenció als usuaris "
        "i la documentació de solucions. Treballaràs amb l'equip per analitzar problemes "
        "i millorar processos. Es valora experiència amb Windows, xarxes i sistemes de "
        "ticketing, així com capacitat per treballar de manera autònoma."
    )

    language, status, confidence = detect_document_language(text)

    assert language == "Catalan"
    assert status == "unsupported"
    assert confidence >= 0.7

def test_preferred_qualifications_section_does_not_create_language_reject() -> None:
    result = analyze_language_evidence(
        source_text=(
            "Required Qualifications: 2+ years of technical support experience. "
            "Strong Windows Server knowledge. "
            "Preferred Qualifications: CompTIA certifications. "
            "Multilingual skills in Spanish, Arabic, or French."
        ),
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    assert result.manual_review is False
    multilingual = [
        item
        for item in result.requirements
        if item.languages == ("Spanish", "Arabic", "French")
    ]
    assert multilingual
    assert multilingual[0].classification == "preferred"


def test_required_qualifications_section_can_create_language_reject() -> None:
    result = analyze_language_evidence(
        source_text=(
            "Required Qualifications: German language skills. "
            "Preferred Qualifications: French is a plus."
        ),
        preferences=_preferences(),
    )

    assert result.hardline_reject is True
    assert REASON_LANGUAGE_UNMET in result.reason_codes


def test_comma_or_language_list_keeps_all_alternatives() -> None:
    result = analyze_language_evidence(
        source_text="Fluent German, French, or Spanish is required.",
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    requirement = next(
        item
        for item in result.requirements
        if item.languages == ("German", "French", "Spanish")
    )
    assert requirement.classification == "required"


def test_and_language_list_means_all_languages_are_required() -> None:
    result = analyze_language_evidence(
        source_text="English, German and French are required for customer support.",
        preferences=_preferences(),
    )

    assert result.hardline_reject is True
    required_languages = {
        item.languages[0]
        for item in result.requirements
        if item.classification == "required" and len(item.languages) == 1
    }
    assert {"English", "German", "French"} <= required_languages


def test_scriptpro_wording_does_not_false_reject_language() -> None:
    result = analyze_language_evidence(
        source_text=(
            "Required Qualifications: 2+ years of related experience in technical support. "
            "Strong working knowledge of Windows Server. "
            "Preferred Qualifications: CompTIA A+, Network+, Security+, Microsoft certifications. "
            "Experience supporting Windows Server environments. "
            "Knowledge of the healthcare industry. "
            "Multilingual skills in Spanish, Arabic, or French. "
            "Remote Work Requirements: Must have reliable internet access."
        ),
        preferences=_preferences(),
    )

    assert result.hardline_reject is False
    assert result.manual_review is False

