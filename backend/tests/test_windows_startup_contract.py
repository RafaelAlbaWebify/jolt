from pathlib import Path


def test_windows_startup_uses_native_windows_shims_and_checks_exit_codes() -> None:
    repository = Path(__file__).resolve().parents[2]
    runner = (repository / "tools" / "start-jolt.ps1").read_text(encoding="utf-8")

    assert 'Resolve-ApplicationCommand -Names @("npm.cmd")' in runner
    assert '-Arguments @("ci")' in runner
    assert "npm install" not in runner
    assert "if ($LASTEXITCODE -ne 0)" in runner
    assert 'Resolve-ApplicationCommand -Names @("uv.exe", "uv")' in runner
    assert "JOLT startup failed during stage '$stage'" in runner
    assert "The npm PowerShell shim can fail under StrictMode" in runner
