[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://jobgether\.com/offer/')]
    [string]$OfferUrl,
    [int]$DebugPort = 9222,
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$RuntimeRoot = Join-Path $RepoRoot ".jolt"
$ChromeProfileDir = Join-Path $RuntimeRoot "chrome-jobgether-cdp"

$ChromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$ChromePath = $ChromeCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $ChromePath) {
    throw "Google Chrome was not found in the standard Windows installation paths."
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required but was not found."
}

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $ChromeProfileDir | Out-Null

$CdpEndpoint = "http://127.0.0.1:$DebugPort"

Write-Host "Starting Google Chrome for the JOLT Jobgether supervised probe..."
Write-Host "Chrome executable: $ChromePath"
Write-Host "JOLT Chrome profile: $ChromeProfileDir"
Write-Host "CDP endpoint: $CdpEndpoint"
Write-Host ""

$ChromeArgs = @(
    "--remote-debugging-port=$DebugPort",
    "--user-data-dir=$ChromeProfileDir",
    "--no-first-run",
    "--no-default-browser-check",
    $OfferUrl
)
Start-Process -FilePath $ChromePath -ArgumentList $ChromeArgs | Out-Null

$Ready = $false
for ($Attempt = 0; $Attempt -lt 40; $Attempt++) {
    try {
        $Version = Invoke-RestMethod -Uri "$CdpEndpoint/json/version" -TimeoutSec 1
        if ($Version.webSocketDebuggerUrl) {
            $Ready = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 250
    }
}
if (-not $Ready) {
    throw "Chrome did not expose the CDP endpoint at $CdpEndpoint."
}

Write-Host "Chrome is ready."
Write-Host "The probe is read-only. If Jobgether needs normal user interaction, complete it in Chrome."
Write-Host "When the offer page is visible, press Enter to inspect the rendered page."
[void](Read-Host)

Push-Location $BackendRoot
try {
    if (-not $SkipSync) {
        Write-Host "Preparing Jobgether probe runtime..."
        uv sync --all-groups
    } else {
        Write-Host "Using the existing JOLT Python environment."
    }

    uv run --no-sync python -u -m jolt.jobgether_browser_probe --cdp-endpoint $CdpEndpoint
    $ProbeExitCode = $LASTEXITCODE
    if ($ProbeExitCode -ne 0) {
        throw "Jobgether browser probe failed with exit code $ProbeExitCode."
    }
}
finally {
    Pop-Location
}
