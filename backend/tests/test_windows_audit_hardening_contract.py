from pathlib import Path


def test_windows_audit_uses_verified_snapshot_provenance_and_stops_services() -> None:
    repository = Path(__file__).resolve().parents[2]
    runner = (repository / "tools" / "audit-jolt.ps1").read_text(encoding="utf-8")

    assert 'Invoke-TextCommand -FilePath "npm.cmd"' in runner
    assert "JOLT_AUDIT_SNAPSHOT_" in runner
    assert 'Join-Path $PSScriptRoot "backup-jolt.ps1"' in runner
    assert 'evidence_type = "consistent_sqlite_backup_snapshot"' in runner
    assert "source_file_read_directly = $false" in runner
    assert "snapshot_archive_included = $false" in runner
    assert 'Join-Path $PSScriptRoot "stop-jolt.ps1"' in runner
    assert 'Invoke-TextCommand -FilePath "npm" ' not in runner
    assert "Get-FileHash" not in runner
