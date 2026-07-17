from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class PreparationGap:
    capability_id: str
    gap_type: str
    preparation_topics: tuple[str, ...]


_GAP_HOURS = {
    "ready_now": 0,
    "preparable_in_days": 4,
    "preparable_in_1_to_2_weeks": 10,
    "preparable_in_1_to_3_months": 35,
    "experience_gap": 120,
    "fundamental_mismatch": 240,
    "unknown": 20,
}


def _normalise_topic(topic: str) -> str:
    return " ".join(topic.casefold().split())


def estimate_preparation_hours(gaps: Iterable[PreparationGap]) -> int:
    """Estimate preparation effort without double-counting overlapping work.

    Each unique preparation topic is one workstream. When several capabilities
    point to the same workstream, the largest applicable estimate wins rather
    than adding the same study effort repeatedly. Capabilities without an
    explicit topic retain a capability-specific fallback workstream.
    """

    workstreams: dict[str, int] = {}
    for gap in gaps:
        hours = _GAP_HOURS.get(gap.gap_type, _GAP_HOURS["unknown"])
        if hours == 0:
            continue

        topics = {
            _normalise_topic(topic)
            for topic in gap.preparation_topics
            if _normalise_topic(topic)
        }
        if not topics:
            topics = {f"capability:{gap.capability_id}"}

        for topic in topics:
            workstreams[topic] = max(workstreams.get(topic, 0), hours)

    return sum(workstreams.values())
