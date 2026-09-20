[CmdletBinding()]
param(
    [string]$SearchUrl = "https://www.linkedin.com/jobs/search/?keywords=IT%20Support"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$ProfileDir = Join-Path $RepoRoot ".jolt\browser-profile"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Output = Join-Path $Downloads "JOLT_LINKEDIN_FAILURE_RECOVERY_$Stamp.json"

& (Join-Path $PSScriptRoot "stop-jolt.ps1")
New-Item -ItemType Directory -Force -Path $ProfileDir, $Downloads | Out-Null

Push-Location $BackendRoot
try {
    uv run playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium could not be prepared." }

    uv run python -m jolt.linkedin_failure_acceptance `
        --profile-dir $ProfileDir `
        --search-url $SearchUrl `
        --output $Output

    if ($LASTEXITCODE -ne 0) {
        throw "LinkedIn failure/recovery acceptance failed. Evidence was written to $Output"
    }
}
finally {
    Pop-Location
}

Write-Host "LinkedIn failure/recovery acceptance passed: $Output"
