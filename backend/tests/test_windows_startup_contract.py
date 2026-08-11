from pathlib import Path


def test_windows_startup_uses_native_windows_shims_and_checks_exit_codes() -> None:
    repository = Path(__file__).resolve().parents[2]
    runner = (repository / "tools" / "start-jolt.ps1").read_text(encoding="utf-8")

    assert 'Resolve-ApplicationCommand -Names @("npm.cmd")' in runner
    assert '-Arguments @("ci")' in runner
    assert "npm install" not in runner
    assert "if ($LASTEXITCODE -ne 0)" in runner
    assert 'Resolve-ApplicationCommand -Names @("uv.exe", "uv")' in runner
    assert 'Resolve-ApplicationCommand -Names @("git.exe", "git")' in runner
    assert "$gitCommitOutput = @(& $gitCommand -C $RepoRoot rev-parse HEAD)" in runner
    assert "$gitExitCode = $LASTEXITCODE" in runner
    assert "if ($gitExitCode -ne 0 -or $gitCommitOutput.Count -eq 0)" in runner
    assert 'Invoke-RestMethod -Uri "$BackendUrl/api/runtime-identity"' in runner
    assert "runtimeIdentity.loaded_git.commit_sha" in runner
    assert "Assert-FreshBackend -ExpectedCommit $expectedBackendCommit" in runner
    assert "backend_loaded_commit = $loadedBackendCommit" in runner
    assert "Refusing to use stale loaded backend code" in runner
    assert "JOLT startup failed during stage '$stage'" in runner
    assert "The npm PowerShell shim can fail under StrictMode" in runner
