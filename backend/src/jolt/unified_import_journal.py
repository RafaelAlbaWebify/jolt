"""Crash-safe import progress journal for multi-store unified AI updates.

The journal detects interrupted writes. It deliberately does not claim atomicity
between SQLite and JSON sidecars, and blocks unsafe automatic replay.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import BaseModel

_LOCK = Lock()


def _journal_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "unified_import_journal.json"


def _read() -> dict[str, Any]:
    path = _journal_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(payload: dict[str, Any]) -> None:
    path = _journal_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def _digest(update: BaseModel) -> str:
    # Stable across JSON key order; distinct from package ID.
    data = update.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def begin(update: BaseModel, package_id: str) -> None:
    with _LOCK:
        items = _read()
        digest = _digest(update)
        previous = items.get(package_id)
        if previous is not None:
            if previous["digest"] != digest:
                raise ValueError("Conflicting unified import replay: package ID has different content")
            raise ValueError(
                "Unified import previously attempted; inspect journal and reconcile "
                "before replaying (cross-store automatic recovery is not certified)"
            )
        items[package_id] = {
            "digest": digest,
            "state": "started",
            "last_step": None,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        _write(items)


def checkpoint(package_id: str, step: str, state: str) -> None:
    with _LOCK:
        items = _read()
        entry = items[package_id]
        entry["state"] = state
        entry["last_step"] = step
        entry["updated_at"] = datetime.now(UTC).isoformat()
        _write(items)


def inspect(package_id: str) -> dict[str, Any] | None:
    with _LOCK:
        item = _read().get(package_id)
        return dict(item) if item is not None else None
