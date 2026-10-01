[CmdletBinding()]
param(
    [string]$SearchUrl = "https://es.indeed.com/jobs",
    [ValidateRange(1, 10)]
    [int]$MaxJobs = 5,
    [string]$ApiUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$RuntimeRoot = Join-Path $RepoRoot ".jolt"
$ProfileDir = Join-Path $RuntimeRoot "browser-profile-indeed"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputZip = Join-Path $Downloads "JOLT_INDEED_CAPTURE_$Timestamp.zip"

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $ProfileDir, $Downloads | Out-Null

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required but was not found."
}

Push-Location $BackendRoot
try {
    Write-Host "Preparing the JOLT backend environment..."
    uv sync --all-groups

    Write-Host "Ensuring Playwright Chromium is installed..."
    uv run playwright install chromium

    Write-Host ""
    Write-Host "Starting bounded supervised Indeed capture POC."
    Write-Host "Browser profile: $ProfileDir"
    Write-Host "Maximum jobs this run: $MaxJobs"
    Write-Host "No auto-apply, CAPTCHA solving, or parallel browsing is performed."
    Write-Host ""

    uv run python -m jolt.indeed_capture `
        --search-url $SearchUrl `
        --api-url $ApiUrl `
        --profile-dir $ProfileDir `
        --output-zip $OutputZip `
        --max-jobs $MaxJobs

    if (-not (Test-Path $OutputZip)) {
        throw "Indeed capture completed without creating the expected ZIP."
    }

    Write-Host ""
    Write-Host "Capture complete: $OutputZip"
}
finally {
    Pop-Location
}
