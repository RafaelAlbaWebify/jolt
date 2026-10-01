[CmdletBinding()]
param(
    [string]$SearchUrl = "https://es.indeed.com/jobs?q=IT+Support",
    [ValidateRange(1, 10)]
    [int]$MaxJobs = 5,
    [int]$DebugPort = 9222,
    [string]$ApiUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$RuntimeRoot = Join-Path $RepoRoot ".jolt"
$ChromeProfileDir = Join-Path $RuntimeRoot "chrome-indeed-cdp"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutputZip = Join-Path $Downloads "JOLT_INDEED_CHROME_CAPTURE_$Timestamp.zip"

$ChromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$ChromePath = $ChromeCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $ChromePath) {
    throw "Google Chrome was not found in the standard Windows installation paths."
}

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $ChromeProfileDir, $Downloads | Out-Null

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required but was not found."
}

$CdpEndpoint = "http://127.0.0.1:$DebugPort"

Write-Host "Starting Google Chrome for the JOLT Indeed CDP capture POC..."
Write-Host "Chrome executable: $ChromePath"
Write-Host "JOLT Chrome profile: $ChromeProfileDir"
Write-Host "CDP endpoint: $CdpEndpoint"
Write-Host ""

$ChromeArgs = @(
    "--remote-debugging-port=$DebugPort",
    "--user-data-dir=$ChromeProfileDir",
    "--no-first-run",
    "--no-default-browser-check",
    $SearchUrl
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
Write-Host "Use that Chrome window normally. If Indeed asks for verification, complete it manually."
Write-Host "JOLT will begin automatically as soon as visible Indeed job results are detected."
Write-Host ""

Push-Location $BackendRoot
try {
    uv sync --all-groups
    uv run python -m jolt.indeed_chrome_attach `
        --cdp-endpoint $CdpEndpoint `
        --api-url $ApiUrl `
        --output-zip $OutputZip `
        --max-jobs $MaxJobs

    if (-not (Test-Path $OutputZip)) {
        throw "Indeed Chrome-attached capture completed without creating the expected ZIP."
    }

    Write-Host ""
    Write-Host "Capture complete: $OutputZip"
}
finally {
    Pop-Location
}
