[CmdletBinding()]
param(
    [string]$SearchUrl = "https://jobgether.com/talent/matches",
    [ValidateRange(1, 5)][int]$MaxJobs = 5,
    [int]$DebugPort = 9222,
    [switch]$SkipSync,
    [switch]$StageObservations,
    [switch]$CommitObservations
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$ChromeProfileDir = Join-Path $RepoRoot ".jolt\chrome-jobgether-cdp"
$Downloads = Join-Path $HOME "Downloads"
$Output = Join-Path $Downloads ("JOLT_JOBGETHER_BATCH_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
$Endpoint = "http://127.0.0.1:$DebugPort"
$Parsed = [uri]$SearchUrl
if ($Parsed.Scheme -ne "https" -or $Parsed.Host -notin @("jobgether.com", "www.jobgether.com")) {
    throw "SearchUrl must be an HTTPS Jobgether page."
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv is required." }
$ChromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$ChromePath = $ChromeCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $ChromePath) { throw "Google Chrome not found." }
New-Item -ItemType Directory -Force -Path $ChromeProfileDir, $Downloads | Out-Null
$Ready = $false
try {
    $Health = Invoke-RestMethod -Uri "$Endpoint/json/version" -TimeoutSec 2
    $Ready = [bool]$Health.webSocketDebuggerUrl
} catch { }
if (-not $Ready) {
    Start-Process -FilePath $ChromePath -ArgumentList @(
        "--remote-debugging-port=$DebugPort",
        "--user-data-dir=$ChromeProfileDir",
        "--no-first-run",
        "--no-default-browser-check",
        $SearchUrl
    ) | Out-Null
    for ($Attempt = 0; $Attempt -lt 40; $Attempt++) {
        try {
            $Health = Invoke-RestMethod -Uri "$Endpoint/json/version" -TimeoutSec 1
            if ($Health.webSocketDebuggerUrl) { $Ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 250
    }
}
if (-not $Ready) { throw "Chrome CDP endpoint unavailable: $Endpoint" }
# Always open the requested listing inside the supervised Chrome profile.
# An already running CDP endpoint does not imply that this tab exists.
Start-Process -FilePath $ChromePath -ArgumentList @(
    "--remote-debugging-port=$DebugPort",
    "--user-data-dir=$ChromeProfileDir",
    $SearchUrl
) | Out-Null
Write-Host "Open the Jobgether search results in the supervised Chrome window."
Write-Host "Complete any normal login or verification manually; do not bypass portal blocks."
[void](Read-Host "When results are visible, press Enter")
Push-Location $BackendRoot
try {
    if (-not $SkipSync) {
        uv sync --all-groups
        if ($LASTEXITCODE -ne 0) { throw "uv sync failed." }
    }
    uv run --no-sync python -u -m jolt.jobgether_batch_capture --cdp-endpoint $Endpoint --limit $MaxJobs --search-url $SearchUrl --output $Output
    if ($LASTEXITCODE -ne 0) { throw "Capture incomplete; inspect output: $Output" }
    Write-Host "Capture summary: $Output"
    if ($CommitObservations -and -not $StageObservations) { throw "-CommitObservations requires -StageObservations." }
    if ($StageObservations) {
        $Args = @("run", "--no-sync", "python", "-m", "jolt.jobgether_supervised_stage", "--input", $Output)
        if ($CommitObservations) { $Args += "--commit" }
        & uv @Args
        if ($LASTEXITCODE -ne 0) { throw "Jobgether observation staging failed." }
    }
} finally { Pop-Location }
