from __future__ import annotations

from jolt.ai_exchange_contract import AIExchangeOutput


def require_unified_context_authority(
    output: AIExchangeOutput,
    *,
    section_label: str,
) -> None:
    """Keep durable AI strategy changes on the unified work-package path only."""

    if output.context_patch:
        raise ValueError(
            f"{section_label} section context_patch must be empty; "
            "use the unified work package top-level context_patch"
        )
