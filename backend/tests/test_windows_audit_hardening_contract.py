from pathlib import Path


def test_windows_audit_uses_native_npm_tracks_active_database_and_stops_services() -> None:
    repository = Path(__file__).resolve().parents[2]
    runner = (repository / "tools" / "audit-jolt.ps1").read_text(encoding="utf-8")

    assert 'Invoke-TextCommand -FilePath "npm.cmd"' in runner
    assert 'Join-Path $BackendRoot "data"' in runner
    assert "Sort-Object FullName -Unique" in runner
    assert 'Join-Path $PSScriptRoot "stop-jolt.ps1"' in runner
    assert 'Invoke-TextCommand -FilePath "npm" ' not in runner
