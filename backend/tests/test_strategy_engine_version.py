from __future__ import annotations

from jolt.strategy_runtime import ENGINE_VERSION


def test_corrected_strategy_uses_new_immutable_engine_version() -> None:
    assert ENGINE_VERSION == "profile-rules-v4"
