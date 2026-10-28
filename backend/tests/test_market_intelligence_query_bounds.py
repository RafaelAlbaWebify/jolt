from types import SimpleNamespace
from unittest.mock import MagicMock

from jolt.market_intelligence import _effective_evaluations
from jolt.strategy_runtime import ENGINE_VERSION


def test_manual_market_evaluations_query_is_scoped_to_relevant_postings() -> None:
    session = MagicMock()
    session.scalars.return_value.all.return_value = [
        SimpleNamespace(
            posting_id="manual-only",
            engine_version=ENGINE_VERSION,
            created_at="2026-10-28",
        )
    ]
    posting = SimpleNamespace(id="manual-only")
    effective, coverage = _effective_evaluations(session, [posting])
    assert set(effective) == {"manual-only"}
    assert coverage["evaluated_count"] == 1
    statement = session.scalars.call_args.args[0]
    assert "posting_id IN" in str(statement)


def test_empty_manual_market_set_skips_historical_evaluation_query() -> None:
    session = MagicMock()
    effective, coverage = _effective_evaluations(session, [])
    session.scalars.assert_not_called()
    assert effective == {}
    assert coverage["posting_count"] == 0
