from __future__ import annotations

import pytest

import jolt.market_preparation_import as market


def test_keyed_market_replay_is_idempotent_and_conflict_safe(tmp_path, monkeypatch) -> None:
    path = tmp_path / "market_preparation_imports.json"
    monkeypatch.setattr(market, "_data_path", lambda: path)
    request = market.MarketPreparationImportRequest(
        idempotency_key="package-123:market",
        summary="Checked market evidence",
        preparation_plan=[market.MarketPreparationAction(title="Inspect Spain eligibility")],
    )
    first = market.import_market_preparation(request)
    written = path.read_bytes()
    replay = market.import_market_preparation(request)
    assert replay.latest_import.id == first.latest_import.id
    assert path.read_bytes() == written
    assert market.list_market_preparation_imports().import_count == 1

    conflict = request.model_copy(update={"summary": "Changed output"})
    with pytest.raises(ValueError, match="Conflicting market preparation replay"):
        market.import_market_preparation(conflict)
    assert path.read_bytes() == written


def test_unkeyed_legacy_market_imports_still_append(tmp_path, monkeypatch) -> None:
    path = tmp_path / "market_preparation_imports.json"
    monkeypatch.setattr(market, "_data_path", lambda: path)
    request = market.MarketPreparationImportRequest(summary="Legacy")
    market.import_market_preparation(request)
    market.import_market_preparation(request)
    assert market.list_market_preparation_imports().import_count == 2


def test_market_atomic_replace_failure_preserves_previous_file(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "market_preparation_imports.json"
    monkeypatch.setattr(market, "_data_path", lambda: path)
    market.import_market_preparation(
        market.MarketPreparationImportRequest(
            idempotency_key="first",
            summary="Preserve persisted history",
        )
    )
    before = path.read_bytes()
    original_replace = market.Path.replace

    def interrupted_replace(self, target):
        if self.name.endswith(".tmp"):
            raise OSError("simulated interrupted replace")
        return original_replace(self, target)

    monkeypatch.setattr(market.Path, "replace", interrupted_replace)
    with pytest.raises(OSError, match="simulated interrupted replace"):
        market.import_market_preparation(
            market.MarketPreparationImportRequest(
                idempotency_key="second",
                summary="Interrupted write",
            )
        )
    assert path.read_bytes() == before
    assert not path.with_suffix(".json.tmp").exists()
