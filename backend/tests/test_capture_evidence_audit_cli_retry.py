from __future__ import annotations

import socket

import pytest

from jolt import capture_evidence_audit_cli


class _Response:
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return b'{"status": "ok"}'


def test_get_json_retries_transient_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def fake_urlopen(url: str, timeout: int) -> _Response:
        nonlocal attempts
        attempts += 1
        assert timeout == capture_evidence_audit_cli.REQUEST_TIMEOUT_SECONDS
        if attempts < 3:
            raise socket.timeout("temporary timeout")
        return _Response()

    monkeypatch.setattr(capture_evidence_audit_cli.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(capture_evidence_audit_cli.time, "sleep", lambda seconds: None)

    assert capture_evidence_audit_cli._get_json("http://example.test") == {"status": "ok"}
    assert attempts == 3


def test_get_json_reports_exhausted_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: int) -> _Response:
        raise socket.timeout("still slow")

    monkeypatch.setattr(capture_evidence_audit_cli.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(capture_evidence_audit_cli.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError, match="request failed after 3 attempts"):
        capture_evidence_audit_cli._get_json("http://example.test")
