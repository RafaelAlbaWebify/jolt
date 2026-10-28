from __future__ import annotations

import pytest
from pydantic import BaseModel

import jolt.unified_import_journal as journal


class ExampleUpdate(BaseModel):
    package_id: str
    payload: str


def test_interrupted_multistore_import_blocks_unsafe_replay(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(journal, "_journal_path", lambda: tmp_path / "journal.json")
    original = ExampleUpdate(package_id="package-1", payload="first")
    journal.begin(original, original.package_id)
    journal.checkpoint(original.package_id, "review_inbox", "applied")
    journal.checkpoint(original.package_id, "market_insights", "applying")
    evidence = journal.inspect(original.package_id)
    assert evidence is not None
    assert evidence["state"] == "applying"
    assert evidence["last_step"] == "market_insights"
    before = (tmp_path / "journal.json").read_bytes()
    with pytest.raises(ValueError, match="reconcile"):
        journal.begin(original, original.package_id)
    with pytest.raises(ValueError, match="Conflicting unified import replay"):
        journal.begin(
            ExampleUpdate(package_id="package-1", payload="changed"), "package-1"
        )
    assert (tmp_path / "journal.json").read_bytes() == before


def test_journal_write_interruption_preserves_previous_checkpoint(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(journal, "_journal_path", lambda: tmp_path / "journal.json")
    update = ExampleUpdate(package_id="package-2", payload="stable")
    journal.begin(update, update.package_id)
    before = (tmp_path / "journal.json").read_bytes()
    original_replace = journal.Path.replace

    def fail_replace(self, target):
        if self.suffix == ".tmp":
            raise OSError("failed journal replacement")
        return original_replace(self, target)

    monkeypatch.setattr(journal.Path, "replace", fail_replace)
    with pytest.raises(OSError, match="failed journal replacement"):
        journal.checkpoint(update.package_id, "stage", "applied")
    assert (tmp_path / "journal.json").read_bytes() == before
    assert not (tmp_path / "journal.json.tmp").exists()
