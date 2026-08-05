from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Protocol


class DuplicateCandidate(Protocol):
    @property
    def posting_id(self) -> str: ...

    @property
    def company(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def recommendation(self) -> str: ...

    @property
    def confidence(self) -> str: ...

    @property
    def ranking_score(self) -> int: ...


_RECOMMENDATION_PRIORITY = {
    "strong_pursue": 0,
    "pursue": 1,
    "pursue_if_condition_met": 2,
    "review_manually": 3,
    "defer": 4,
    "do_not_pursue": 5,
}

_STOPWORDS = {
    "about",
    "and",
    "are",
    "company",
    "for",
    "from",
    "job",
    "our",
    "role",
    "the",
    "this",
    "to",
    "we",
    "with",
    "you",
    "your",
}


def normalize_duplicate_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    unaccented = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", unaccented)
    return " ".join(normalized.split())


def _description_tokens(description: str) -> frozenset[str]:
    return frozenset(
        token
        for token in normalize_duplicate_text(description).split()
        if len(token) >= 3 and token not in _STOPWORDS
    )


def descriptions_are_materially_similar(first: str, second: str) -> bool:
    first_normalized = normalize_duplicate_text(first)
    second_normalized = normalize_duplicate_text(second)

    if not first_normalized or not second_normalized:
        return False

    sequence_ratio = SequenceMatcher(
        None,
        first_normalized[:6000],
        second_normalized[:6000],
        autojunk=False,
    ).ratio()

    first_tokens = _description_tokens(first)
    second_tokens = _description_tokens(second)
    union = first_tokens | second_tokens
    token_ratio = len(first_tokens & second_tokens) / len(union) if union else 0.0

    return sequence_ratio >= 0.86 or token_ratio >= 0.82


def are_semantic_duplicates(
    first: DuplicateCandidate,
    second: DuplicateCandidate,
    *,
    descriptions: dict[str, str],
) -> bool:
    if normalize_duplicate_text(first.company) != normalize_duplicate_text(second.company):
        return False

    if normalize_duplicate_text(first.title) != normalize_duplicate_text(second.title):
        return False

    return descriptions_are_materially_similar(
        descriptions.get(first.posting_id, ""),
        descriptions.get(second.posting_id, ""),
    )


def canonical_sort_key(
    candidate: DuplicateCandidate,
) -> tuple[int, int, int, str]:
    return (
        _RECOMMENDATION_PRIORITY.get(candidate.recommendation, 4),
        -candidate.ranking_score,
        0 if candidate.confidence == "high" else 1,
        candidate.posting_id,
    )


def group_semantic_duplicates[CandidateT: DuplicateCandidate](
    candidates: Iterable[CandidateT],
    *,
    descriptions: dict[str, str],
) -> list[list[CandidateT]]:
    groups: list[list[CandidateT]] = []

    for candidate in candidates:
        matching_group = next(
            (
                group
                for group in groups
                if any(
                    are_semantic_duplicates(
                        member,
                        candidate,
                        descriptions=descriptions,
                    )
                    for member in group
                )
            ),
            None,
        )

        if matching_group is None:
            groups.append([candidate])
        else:
            matching_group.append(candidate)

    for group in groups:
        group.sort(key=canonical_sort_key)

    return groups
