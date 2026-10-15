[CmdletBinding()]
param(
    [ValidateSet("Open", "Capture")]
    [string]$Mode = "Open",
    [string]$SearchUrl = "https://www.infojobs.net/ofertas-trabajo/support-it",
    [ValidateRange(1, 5)]
    [int]$Limit = 3,
    [int]$DebugPort = 9223
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$parsed = [uri]$SearchUrl
if ($parsed.Scheme -ne "https" -or $parsed.Host -notin @("www.infojobs.net", "infojobs.net") -or
    -not $parsed.AbsolutePath.StartsWith("/ofertas-trabajo/")) {
    throw "Expected an HTTPS InfoJobs search results URL."
}

$root = Split-Path -Parent $PSScriptRoot
$profile = Join-Path $root ".jolt\chrome-infojobs-cdp"
$endpoint = "http://127.0.0.1:$DebugPort"
$chrome = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $chrome) { throw "Google Chrome was not found." }

function Test-Cdp {
    try {
        $version = Invoke-RestMethod -Uri "$endpoint/json/version" -TimeoutSec 2
        return [bool]$version.webSocketDebuggerUrl
    } catch {
        return $false
    }
}

if (-not (Test-Cdp)) {
    New-Item -ItemType Directory -Path $profile -Force | Out-Null
    Start-Process -FilePath $chrome -ArgumentList @(
        "--remote-debugging-port=$DebugPort",
        "--remote-debugging-address=127.0.0.1",
        "--user-data-dir=`"$profile`"",
        "--no-first-run",
        $SearchUrl
    ) | Out-Null
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if (Test-Cdp) { $ready = $true; break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw "Isolated Chrome CDP did not start on $endpoint" }
    Write-Host "Isolated JOLT Chrome launched on port $DebugPort."
} else {
    Write-Host "Existing isolated JOLT Chrome session detected on port $DebugPort."
}

Write-Host "Use ONLY that isolated Chrome window for InfoJobs."
Write-Host "Search URL: $SearchUrl"
if ($Mode -eq "Open") {
    Write-Host "Browser ready. No capture or database writes performed."
    return
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required for capture."
}

[void](Read-Host "Make sure the requested results page is visible in isolated Chrome, then press Enter")
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$output = Join-Path $HOME "Downloads\JOLT_INFOJOBS_CAPTURE_$stamp.json"
$backend = Join-Path $root "backend"
& uv run --project $backend python -m jolt.infojobs_supervised_capture `
    --cdp-endpoint $endpoint `
    --search-url $SearchUrl `
    --limit $Limit `
    --output $output
$exitCode = $LASTEXITCODE
Write-Host "Read-only capture report: $output"
Write-Host "Capture exit code: $exitCode"
if ($exitCode -ne 0) {
    Write-Warning "No new reliable offer evidence captured. Review the JSON diagnostic; database was not changed."
}
