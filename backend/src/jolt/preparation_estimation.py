from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class PreparationGap:
    capability_id: str
    gap_type: str
    preparation_topics: tuple[str, ...]


_INTERVIEW_PREPARATION_HOURS = {
    "preparable_in_days": 4,
    "preparable_in_1_to_2_weeks": 10,
}


def _normalise_topic(topic: str) -> str:
    return " ".join(topic.casefold().split())


def estimate_preparation_hours(gaps: Iterable[PreparationGap]) -> int:
    """Estimate realistic preparation effort before a technical interview.

    Only gaps that can reasonably be improved within days or one to two weeks
    contribute to this number. Longer-term development, experience gaps,
    fundamental mismatches and unknown gaps remain represented by the gap model,
    but are not converted into misleading pre-interview study hours.

    A capability's estimate is its total preparation budget, not a cost to apply
    independently to every listed topic. The budget is divided across that
    capability's unique topics. Shared topics are then merged by keeping the
    largest contribution required by any capability.

    Capabilities without explicit topics retain a capability-specific fallback
    workstream so unrelated short-term preparation is not collapsed accidentally.
    """

    workstreams: dict[str, int] = {}
    for gap in gaps:
        hours = _INTERVIEW_PREPARATION_HOURS.get(gap.gap_type, 0)
        if hours == 0:
            continue

        topics = {
            _normalise_topic(topic)
            for topic in gap.preparation_topics
            if _normalise_topic(topic)
        }
        if not topics:
            topics = {f"capability:{gap.capability_id}"}

        hours_per_topic = math.ceil(hours / len(topics))
        for topic in topics:
            workstreams[topic] = max(workstreams.get(topic, 0), hours_per_topic)

    return sum(workstreams.values())
