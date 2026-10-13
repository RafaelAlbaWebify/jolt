[CmdletBinding()]
param(
    [string]$SearchUrl = "https://www.infojobs.net/ofertas-trabajo/support-it",
    [int]$DebugPort = 9223,
    [switch]$SkipSync
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$Parsed = [uri]$SearchUrl
if ($Parsed.Scheme -ne "https" -or $Parsed.Host -notin @("www.infojobs.net", "infojobs.net")) {
    throw "Expected an HTTPS InfoJobs URL."
}
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Profile = Join-Path $Root ".jolt\chrome-infojobs-cdp"
$Endpoint = "http://127.0.0.1:$DebugPort"
$Candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$Chrome = $Candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $Chrome) { throw "Chrome executable not found." }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv is required." }
New-Item -ItemType Directory -Force -Path $Profile | Out-Null
Start-Process -FilePath $Chrome -ArgumentList @(
    "--remote-debugging-port=$DebugPort",
    "--user-data-dir=$Profile",
    "--no-first-run",
    $SearchUrl
) | Out-Null
$Ready = $false
for ($Attempt = 0; $Attempt -lt 40; $Attempt++) {
    try {
        $Response = Invoke-RestMethod -Uri "$Endpoint/json/version" -TimeoutSec 1
        if ($Response.webSocketDebuggerUrl) { $Ready = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 250
}
if (-not $Ready) { throw "Chrome CDP unavailable: $Endpoint" }
Write-Host "Inspect InfoJobs in Chrome. Complete normal manual login if necessary."
Write-Host "This is an access diagnostic, not a job capture. Do not bypass access restrictions."
[void](Read-Host "When the page is visible, press Enter")
Push-Location $Backend
try {
    if (-not $SkipSync) {
        uv sync --all-groups
        if ($LASTEXITCODE -ne 0) { throw "uv sync failed." }
    }
    uv run --no-sync python -m jolt.infojobs_browser_probe --cdp-endpoint $Endpoint
    if ($LASTEXITCODE -ne 0) { throw "InfoJobs access not yet certified; see diagnostics above." }
} finally { Pop-Location }
