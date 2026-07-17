[CmdletBinding()]
param(
    [string]$SearchUrl = "https://www.linkedin.com/jobs/search/",
    [ValidateRange(1, 50)]
    [int]$MaxJobs = 10,
    [ValidateRange(1, 10)]
    [int]$MaxPages = 3,
    [string]$ApiUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$RuntimeRoot = Join-Path $RepoRoot ".jolt"
$ProfileDir = Join-Path $RuntimeRoot "browser-profile"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputZip = Join-Path $Downloads "JOLT_LINKEDIN_CAPTURE_$Timestamp.zip"

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $ProfileDir, $Downloads | Out-Null

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required but was not found. Install uv, then run this command again."
}

Push-Location $BackendRoot
try {
    Write-Host "Preparing the JOLT backend environment..."
    uv sync --all-groups

    Write-Host "Ensuring Playwright Chromium is installed..."
    uv run playwright install chromium

    Write-Host ""
    Write-Host "Starting supervised LinkedIn capture."
    Write-Host "The browser profile stays local at: $ProfileDir"
    Write-Host "Credentials are entered only in the browser and are never requested by this script."
    Write-Host "Capture is bounded to $MaxJobs total listings across at most $MaxPages page(s)."
    Write-Host "Unsupported cards are recorded and skipped instead of aborting the run."
    Write-Host ""

    uv run python -m jolt.windows_console_capture `
        --search-url $SearchUrl `
        --api-url $ApiUrl `
        --profile-dir $ProfileDir `
        --output-zip $OutputZip `
        --max-jobs $MaxJobs `
        --max-pages $MaxPages

    if (-not (Test-Path $OutputZip)) {
        throw "The capture command completed without creating the expected ZIP."
    }

    Write-Host ""
    Write-Host "Capture complete: $OutputZip"
}
finally {
    Pop-Location
}
