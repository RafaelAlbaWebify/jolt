from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Literal

from jolt.job_search_preferences import JobSearchPreferences

LanguageRequirementKind = Literal["required", "preferred", "ambiguous"]
DocumentLanguageStatus = Literal["supported", "unsupported", "unknown"]

REASON_LANGUAGE_UNMET = "LANGUAGE_REQUIREMENT_UNMET"
REASON_LANGUAGE_UNCERTAIN = "LANGUAGE_REQUIREMENT_UNCERTAIN"
REASON_UNSUPPORTED_DOCUMENT_LANGUAGE = "UNSUPPORTED_JOB_LANGUAGE"

_LANGUAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "English": ("english", "inglés", "ingles", "englisch", "anglais", "inglese"),
    "Spanish": (
        "spanish",
        "español",
        "espanol",
        "castellano",
        "spanisch",
        "espagnol",
        "spagnolo",
    ),
    "German": ("german", "deutsch", "alemán", "aleman", "allemand", "tedesco"),
    "French": ("french", "français", "francais", "französisch", "franzoesisch", "francés", "frances"),
    "Dutch": ("dutch", "nederlands", "niederländisch", "niederlaendisch", "neerlandés", "neerlandes"),
    "Italian": ("italian", "italiano", "italienisch", "italien", "italiano"),
    "Portuguese": ("portuguese", "português", "portugues", "portugiesisch"),
    "Swedish": ("swedish", "svenska", "schwedisch"),
    "Danish": ("danish", "dansk", "dänisch", "daenisch"),
    "Norwegian": ("norwegian", "norsk", "norwegisch"),
    "Finnish": ("finnish", "suomi", "finnisch"),
    "Polish": ("polish", "polski", "polnisch"),
    "Czech": ("czech", "čeština", "cestina", "tschechisch"),
    "Slovak": ("slovak", "slovenčina", "slovencina", "slowakisch"),
    "Romanian": ("romanian", "română", "romana", "rumänisch", "rumaenisch"),
    "Hungarian": ("hungarian", "magyar", "ungarisch"),
    "Bulgarian": ("bulgarian", "български"),
    "Croatian": ("croatian", "hrvatski"),
    "Serbian": ("serbian", "srpski", "српски"),
    "Slovenian": ("slovenian", "slovenščina", "slovenscina"),
    "Lithuanian": ("lithuanian", "lietuvių", "lietuviu"),
    "Latvian": ("latvian", "latviešu", "latviesu"),
    "Estonian": ("estonian", "eesti"),
    "Ukrainian": ("ukrainian", "українська"),
    "Russian": ("russian", "русский"),
    "Catalan": ("catalan", "catalán", "català", "catala"),
    "Galician": ("galician", "galego", "gallego"),
    "Basque": ("basque", "euskara", "vasco"),
    "Arabic": ("arabic", "العربية"),
    "Hebrew": ("hebrew", "עברית"),
    "Chinese": ("chinese", "mandarin", "中文", "普通话"),
    "Japanese": ("japanese", "日本語"),
    "Korean": ("korean", "한국어"),
    "Hindi": ("hindi", "हिन्दी", "हिंदी"),
}

_REQUIRED_MARKERS = (
    "required",
    "mandatory",
    "must speak",
    "must have",
    "need to speak",
    "needs to speak",
    "fluent",
    "fluency",
    "proficient",
    "proficiency",
    "professional proficiency",
    "excellent",
    "very good",
    "good command",
    "native",
    "mother tongue",
    "obligatorio",
    "obligatoria",
    "imprescindible",
    "requerido",
    "requerida",
    "se requiere",
    "dominio",
    "fluido",
    "fluida",
    "nivel profesional",
    "erforderlich",
    "zwingend",
    "voraussetzung",
    "sehr gute",
    "gute kenntnisse",
    "verhandlungssicher",
    "fließend",
    "fliessend",
    "obligatoire",
    "requis",
    "requise",
    "courant",
    "maîtrise",
    "maitrise",
    "richiesto",
    "richiesta",
    "obbligatorio",
    "obbligatoria",
    "fluente",
    "vereist",
    "vloeiend",
)

_PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "a plus",
    "is a plus",
    "advantage",
    "advantageous",
    "desirable",
    "optional",
    "valorable",
    "se valorará",
    "se valorara",
    "deseable",
    "wünschenswert",
    "wuenschenswert",
    "von vorteil",
    "souhaité",
    "souhaite",
    "préféré",
    "prefere",
)

_LANGUAGE_SKILL_MARKERS = (
    "language",
    "languages",
    "written",
    "spoken",
    "speaking",
    "speaker",
    "skills",
    "knowledge",
    "command",
    "idioma",
    "idiomas",
    "hablado",
    "hablada",
    "escrito",
    "escrita",
    "conocimientos",
    "kenntnisse",
    "wort und schrift",
)

_LEVEL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("native", re.compile(r"\b(?:native|mother tongue|nativo|nativa|muttersprache)\b", re.I)),
    ("c2", re.compile(r"\bC2\b", re.I)),
    ("c1", re.compile(r"\bC1\b", re.I)),
    ("b2", re.compile(r"\bB2\b", re.I)),
    ("b1", re.compile(r"\bB1\b", re.I)),
    (
        "fluent",
        re.compile(
            r"\b(?:fluent|fluency|fluido|fluida|fließend|fliessend|verhandlungssicher|courant|fluente|vloeiend)\b",
            re.I,
        ),
    ),
    (
        "very_good",
        re.compile(r"\b(?:very good|excellent|sehr gute|excelente)\b", re.I),
    ),
    (
        "professional",
        re.compile(r"\b(?:professional proficiency|nivel profesional|good command)\b", re.I),
    ),
)

_SUPPORTED_WORDS: dict[str, frozenset[str]] = {
    "English": frozenset(
        {
            "the", "and", "to", "of", "in", "for", "with", "you", "we", "our", "a", "an",
            "is", "are", "as", "will", "this", "that", "from", "your", "on", "be", "have",
            "work", "role", "team", "experience", "support", "skills", "job", "about",
        }
    ),
    "Spanish": frozenset(
        {
            "el", "la", "los", "las", "y", "de", "en", "para", "con", "que", "un", "una",
            "por", "como", "se", "del", "al", "es", "son", "tu", "tus", "nuestro", "nuestra",
            "trabajo", "puesto", "equipo", "experiencia", "soporte", "requisitos", "sobre",
        }
    ),
}

_UNSUPPORTED_WORDS: dict[str, frozenset[str]] = {
    "German": frozenset(
        {
            "der", "die", "das", "und", "zu", "den", "von", "mit", "für", "fuer", "auf", "im",
            "ist", "wir", "sie", "du", "eine", "einer", "unser", "ihre", "als", "bei", "sowie",
            "kenntnisse", "erfahrung", "aufgaben", "anforderungen", "arbeit", "team",
        }
    ),
    "French": frozenset(
        {
            "le", "la", "les", "de", "des", "du", "et", "à", "a", "en", "pour", "avec", "vous",
            "nous", "une", "un", "est", "sont", "sur", "dans", "votre", "expérience", "experience",
            "poste", "équipe", "equipe", "compétences", "competences",
        }
    ),
    "Italian": frozenset(
        {
            "il", "lo", "la", "gli", "le", "di", "del", "della", "e", "a", "in", "per", "con",
            "che", "un", "una", "si", "sono", "è", "nostro", "vostro", "esperienza",
            "ruolo", "team", "requisiti",
        }
    ),
    "Dutch": frozenset(
        {
            "de", "het", "een", "en", "van", "voor", "met", "op", "in", "je", "jij", "wij", "we",
            "ons", "is", "zijn", "als", "bij", "naar", "ervaring", "functie", "team", "vereisten",
        }
    ),
    "Portuguese": frozenset(
        {
            "o", "a", "os", "as", "de", "do", "da", "e", "em", "para", "com", "que", "um", "uma",
            "por", "como", "se", "é", "são", "sao", "nosso", "sua", "experiência", "experiencia",
            "vaga", "equipe", "requisitos",
        }
    ),
    "Swedish": frozenset({"och", "att", "i", "en", "ett", "som", "för", "for", "med", "på", "pa", "du", "vi", "är", "ar", "erfarenhet"}),
    "Danish": frozenset({"og", "at", "i", "en", "et", "som", "for", "med", "på", "pa", "du", "vi", "er", "erfaring"}),
    "Norwegian": frozenset({"og", "at", "i", "en", "et", "som", "for", "med", "på", "pa", "du", "vi", "er", "erfaring"}),
    "Finnish": frozenset({"ja", "on", "että", "etta", "se", "ei", "työ", "tyo", "kokemus", "tehtävä", "tehtava", "me", "sinä", "sina"}),
    "Polish": frozenset({"i", "w", "na", "z", "do", "dla", "oraz", "jest", "są", "sa", "praca", "doświadczenie", "doswiadczenie", "zespół", "zespol"}),
}

_LEVEL_ORDER = {
    "unknown": 0,
    "basic": 1,
    "b1": 2,
    "conversational": 2,
    "b2": 3,
    "professional": 3,
    "very_good": 3,
    "c1": 4,
    "fluent": 4,
    "c2": 5,
    "native": 5,
}


@dataclass(frozen=True)
class LanguageRequirementEvidence:
    languages: tuple[str, ...]
    minimum_level: str
    classification: LanguageRequirementKind
    evidence: str
    confidence: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LanguageHardlineResult:
    document_language: str
    document_language_status: DocumentLanguageStatus
    document_language_confidence: float
    requirements: tuple[LanguageRequirementEvidence, ...]
    hardline_reject: bool
    manual_review: bool
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "document_language": self.document_language,
            "document_language_status": self.document_language_status,
            "document_language_confidence": self.document_language_confidence,
            "requirements": [item.as_dict() for item in self.requirements],
            "hardline_reject": self.hardline_reject,
            "manual_review": self.manual_review,
            "reason_codes": list(self.reason_codes),
            "reasons": list(self.reasons),
        }


def _normalise(text: str) -> str:
    return " ".join(text.casefold().replace("’", "'").split())


def _tokens(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]+(?:['’-][^\W\d_]+)?", text.casefold(), flags=re.UNICODE)


def _non_latin_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    non_latin = 0
    for char in letters:
        name = unicodedata.name(char, "")
        if name and "LATIN" not in name:
            non_latin += 1
    return non_latin / len(letters)


def _profile_score(tokens: list[str], profile: frozenset[str]) -> float:
    if not tokens:
        return 0.0
    hits = sum(token in profile for token in tokens)
    return hits / len(tokens)


def detect_document_language(text: str) -> tuple[str, DocumentLanguageStatus, float]:
    tokens = _tokens(text)
    if len(tokens) < 24:
        return "unknown", "unknown", 0.0

    non_latin = _non_latin_ratio(text)
    if non_latin >= 0.12:
        return "other_non_latin", "unsupported", min(1.0, 0.75 + non_latin)

    supported_scores = {
        language: _profile_score(tokens, profile)
        for language, profile in _SUPPORTED_WORDS.items()
    }
    unsupported_scores = {
        language: _profile_score(tokens, profile)
        for language, profile in _UNSUPPORTED_WORDS.items()
    }

    supported_language, supported_score = max(supported_scores.items(), key=lambda item: item[1])
    unsupported_language, unsupported_score = max(
        unsupported_scores.items(), key=lambda item: item[1]
    )
    competing_supported = min(supported_scores.values())

    if supported_score >= 0.045 and supported_score >= unsupported_score * 1.35:
        margin = max(0.0, supported_score - max(unsupported_score, competing_supported))
        return supported_language, "supported", min(0.99, 0.72 + margin * 4)

    if unsupported_score >= 0.035 and unsupported_score >= supported_score * 1.25:
        margin = max(0.0, unsupported_score - supported_score)
        return unsupported_language, "unsupported", min(0.99, 0.72 + margin * 4)

    if len(tokens) >= 80 and supported_score < 0.018:
        return "other", "unsupported", 0.72

    return "unknown", "unknown", 0.45


def _segments(text: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(r"[\n\r]+|(?<=[.!?;])\s+", text)
        if part.strip()
    ]


def _marker_positions(segment: str, markers: tuple[str, ...]) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    for marker in markers:
        for match in re.finditer(re.escape(marker), segment, flags=re.I):
            positions.append((match.start(), match.end()))
    return positions


def _distance(position: int, marker: tuple[int, int]) -> int:
    start, end = marker
    if start <= position <= end:
        return 0
    return min(abs(position - start), abs(position - end))


def _nearest_kind(segment: str, position: int) -> LanguageRequirementKind | None:
    preferred = _marker_positions(segment, _PREFERRED_MARKERS)
    required = _marker_positions(segment, _REQUIRED_MARKERS)
    cefr = [(match.start(), match.end()) for match in re.finditer(r"\b[ABC][12]\b", segment, re.I)]
    required.extend(cefr)

    nearest_preferred = min((_distance(position, marker) for marker in preferred), default=999)
    nearest_required = min((_distance(position, marker) for marker in required), default=999)

    if nearest_preferred <= 45 and nearest_preferred < nearest_required:
        return "preferred"
    if nearest_required <= 80:
        return "required"

    folded = segment.casefold()
    if any(marker in folded for marker in _LANGUAGE_SKILL_MARKERS):
        return "ambiguous"
    return None


def _minimum_level(segment: str, position: int) -> str:
    start = max(0, position - 70)
    end = min(len(segment), position + 100)
    window = segment[start:end]
    for level, pattern in _LEVEL_PATTERNS:
        if pattern.search(window):
            return level
    return "unknown"


def _language_mentions(segment: str) -> list[tuple[str, int, int]]:
    mentions: list[tuple[str, int, int]] = []
    for language, aliases in _LANGUAGE_ALIASES.items():
        for alias in aliases:
            pattern = re.compile(rf"(?<!\w){re.escape(alias)}(?!\w)", re.I)
            for match in pattern.finditer(segment):
                mentions.append((language, match.start(), match.end()))
    mentions.sort(key=lambda item: item[1])
    return mentions


def _has_explicit_or(segment: str, left_end: int, right_start: int) -> bool:
    between = segment[left_end:right_start].casefold()
    return bool(re.search(r"\b(?:or|o|oder|ou|oppure)\b", between))


def extract_language_requirements(text: str) -> tuple[LanguageRequirementEvidence, ...]:
    results: list[LanguageRequirementEvidence] = []

    for raw_segment in _segments(text):
        segment = _normalise(raw_segment)
        mentions = _language_mentions(segment)
        if not mentions:
            continue

        consumed: set[int] = set()
        for index, (language, start, _end) in enumerate(mentions):
            if index in consumed:
                continue

            alternatives = [language]
            alternative_indexes = [index]
            cursor = index
            while cursor + 1 < len(mentions):
                next_language, next_start, next_end = mentions[cursor + 1]
                if not _has_explicit_or(segment, mentions[cursor][2], next_start):
                    break
                alternatives.append(next_language)
                alternative_indexes.append(cursor + 1)
                cursor += 1

            if len(alternatives) > 1:
                consumed.update(alternative_indexes)
                midpoint = (start + mentions[alternative_indexes[-1]][2]) // 2
                kinds = [_nearest_kind(segment, mentions[i][1]) for i in alternative_indexes]
                if all(kind is None for kind in kinds):
                    continue
                classification: LanguageRequirementKind = (
                    "preferred"
                    if all(kind == "preferred" for kind in kinds)
                    else "required"
                    if any(kind == "required" for kind in kinds)
                    else "ambiguous"
                )
                levels = [_minimum_level(segment, mentions[i][1]) for i in alternative_indexes]
                minimum_level = max(levels, key=lambda value: _LEVEL_ORDER.get(value, 0))
                confidence = 0.96 if classification != "ambiguous" else 0.65
                results.append(
                    LanguageRequirementEvidence(
                        languages=tuple(dict.fromkeys(alternatives)),
                        minimum_level=minimum_level,
                        classification=classification,
                        evidence=raw_segment.strip(),
                        confidence=confidence,
                    )
                )
                continue

            classification = _nearest_kind(segment, start)
            if classification is None:
                continue
            level = _minimum_level(segment, start)
            confidence = 0.95 if classification != "ambiguous" else 0.62
            results.append(
                LanguageRequirementEvidence(
                    languages=(language,),
                    minimum_level=level,
                    classification=classification,
                    evidence=raw_segment.strip(),
                    confidence=confidence,
                )
            )

    deduplicated: list[LanguageRequirementEvidence] = []
    seen: set[tuple[tuple[str, ...], str, str]] = set()
    for item in results:
        key = (item.languages, item.minimum_level, item.classification)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return tuple(deduplicated)


def _candidate_levels(preferences: JobSearchPreferences) -> dict[str, str]:
    allowed = {language.casefold() for language in preferences.languages}
    configured_levels = {
        language.casefold(): level
        for language, level in preferences.language_levels.items()
    }
    levels = {
        language.casefold(): configured_levels.get(language.casefold(), "professional")
        for language in preferences.languages
    }
    return {language: level for language, level in levels.items() if language in allowed}


def analyze_language_evidence(
    *,
    source_text: str,
    preferences: JobSearchPreferences,
) -> LanguageHardlineResult:
    document_language, document_status, document_confidence = detect_document_language(source_text)
    requirements = extract_language_requirements(source_text)
    candidate_levels = _candidate_levels(preferences)

    reason_codes: list[str] = []
    reasons: list[str] = []
    hardline_reject = False
    manual_review = False

    if document_status == "unsupported":
        hardline_reject = True
        reason_codes.append(REASON_UNSUPPORTED_DOCUMENT_LANGUAGE)
        reasons.append(
            f"{REASON_UNSUPPORTED_DOCUMENT_LANGUAGE}: detected job-ad language "
            f"{document_language} (confidence {document_confidence:.2f}); only Spanish and English are accepted."
        )

    for requirement in requirements:
        if requirement.classification == "preferred":
            continue

        candidate_matches = [
            (language, candidate_levels.get(language.casefold()))
            for language in requirement.languages
            if candidate_levels.get(language.casefold()) is not None
        ]

        if requirement.classification == "required" and not candidate_matches:
            hardline_reject = True
            if REASON_LANGUAGE_UNMET not in reason_codes:
                reason_codes.append(REASON_LANGUAGE_UNMET)
            required = " OR ".join(requirement.languages)
            reasons.append(
                f"{REASON_LANGUAGE_UNMET}: required {required}"
                + (
                    f" ({requirement.minimum_level})"
                    if requirement.minimum_level != "unknown"
                    else ""
                )
                + "; candidate has no listed proficiency in the required language option(s). "
                f"Evidence: {requirement.evidence}"
            )
            continue

        if requirement.classification == "ambiguous":
            unsupported_mentions = [
                language
                for language in requirement.languages
                if language.casefold() not in candidate_levels
            ]
            if unsupported_mentions:
                manual_review = True
                if REASON_LANGUAGE_UNCERTAIN not in reason_codes:
                    reason_codes.append(REASON_LANGUAGE_UNCERTAIN)
                reasons.append(
                    f"{REASON_LANGUAGE_UNCERTAIN}: "
                    f"{' OR '.join(unsupported_mentions)} is mentioned as a language skill but "
                    f"mandatory status is unclear. Evidence: {requirement.evidence}"
                )
            continue

        if requirement.classification == "required" and candidate_matches:
            required_level = _LEVEL_ORDER.get(requirement.minimum_level, 0)
            if required_level:
                best_candidate = max(
                    (_LEVEL_ORDER.get(level or "unknown", 0) for _, level in candidate_matches),
                    default=0,
                )
                if best_candidate and best_candidate < required_level:
                    manual_review = True
                    if REASON_LANGUAGE_UNCERTAIN not in reason_codes:
                        reason_codes.append(REASON_LANGUAGE_UNCERTAIN)
                    reasons.append(
                        f"{REASON_LANGUAGE_UNCERTAIN}: candidate has "
                        f"{' OR '.join(language for language, _ in candidate_matches)}, but the "
                        f"advertisement states level {requirement.minimum_level}. Evidence: "
                        f"{requirement.evidence}"
                    )

    if hardline_reject:
        manual_review = False

    return LanguageHardlineResult(
        document_language=document_language,
        document_language_status=document_status,
        document_language_confidence=document_confidence,
        requirements=requirements,
        hardline_reject=hardline_reject,
        manual_review=manual_review,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        reasons=tuple(dict.fromkeys(reasons)),
    )
