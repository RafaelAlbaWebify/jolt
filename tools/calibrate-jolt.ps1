[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Staging = Join-Path $env:TEMP "JOLT_CALIBRATION_$Timestamp"
$OutputZip = Join-Path $Downloads "JOLT_CALIBRATION_$Timestamp.zip"

New-Item -ItemType Directory -Force -Path $Downloads, $Staging | Out-Null

try {
    & (Join-Path $PSScriptRoot "start-jolt.ps1") -NoBrowser

    Push-Location $BackendRoot
    try {
        uv run python -m jolt.workbench_playwright_audit `
            --api-url "http://127.0.0.1:8000" `
            --app-url "http://127.0.0.1:5173" `
            --output-dir $Staging
        if ($LASTEXITCODE -ne 0) {
            throw "The Playwright calibration audit reported errors."
        }
    }
    finally {
        Pop-Location
    }

    Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $OutputZip -Force
    Write-Host "Automated JOLT calibration package: $OutputZip"
}
finally {
    & (Join-Path $PSScriptRoot "stop-jolt.ps1") -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Staging -Recurse -Force -ErrorAction SilentlyContinue
}
