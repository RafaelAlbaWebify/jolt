[CmdletBinding()]
param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$SkipDependencies,
    [switch]$Quick
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$FrontendRoot = Join-Path $RepoRoot "frontend"
$startedAt = Get-Date
$results = [System.Collections.Generic.List[object]]::new()

function Invoke-Gate {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Directory,
        [Parameter(Mandatory)][string]$Command,
        [Parameter(Mandatory)][string[]]$Arguments
    )
    Write-Host ("[JOLT PREFLIGHT] {0}" -f $Name)
    Push-Location -LiteralPath $Directory
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        & $Command @Arguments
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 1 }
    }
    catch {
        Write-Warning ("{0}: {1}" -f $Name, $_.Exception.Message)
        $code = 1
    }
    finally {
        $watch.Stop()
        Pop-Location
    }
    $results.Add([pscustomobject]@{
        gate = $Name
        exit_code = [int]$code
        seconds = [math]::Round($watch.Elapsed.TotalSeconds, 2)
    })
    if ($code -ne 0) { Write-Warning ("FAIL: {0} (exit {1})" -f $Name, $code) }
}

Push-Location -LiteralPath $RepoRoot
try {
    $top = (& git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $top) { throw "This script must run inside the JOLT Git repository." }
    $head = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Unable to determine Git HEAD." }
    $branch = (& git branch --show-current).Trim()
}
finally { Pop-Location }

if (-not $SkipBackend) {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv is required for backend preflight." }
    if (-not $SkipDependencies) { Invoke-Gate "backend dependency sync" $BackendRoot "uv" @("sync", "--all-groups") }
    Invoke-Gate "Ruff lint" $BackendRoot "uv" @("run", "--no-sync", "ruff", "check", ".")
    Invoke-Gate "Ruff format" $BackendRoot "uv" @("run", "--no-sync", "ruff", "format", "--check", ".")
    Invoke-Gate "Pyright" $BackendRoot "uv" @("run", "--no-sync", "pyright")
    if ($Quick) {
        Write-Warning "Quick mode skips full pytest; NOT sufficient to open or merge a PR."
    }
    else { Invoke-Gate "pytest" $BackendRoot "uv" @("run", "--no-sync", "pytest") }
}
if (-not $SkipFrontend) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm is required for frontend preflight." }
    if (-not $SkipDependencies) { Invoke-Gate "frontend dependency install" $FrontendRoot "npm" @("ci", "--ignore-scripts", "--no-fund") }
    Invoke-Gate "frontend audit" $FrontendRoot "npm" @("audit", "--audit-level=high")
    Invoke-Gate "frontend tests" $FrontendRoot "npm" @("test")
    Invoke-Gate "frontend build" $FrontendRoot "npm" @("run", "build")
}

$failed = @($results | Where-Object { $_.exit_code -ne 0 })
$summary = [ordered]@{
    contract = "jolt-development-preflight-v1"
    generated_at = (Get-Date).ToString("o")
    git_head = $head
    git_branch = $branch
    quick = [bool]$Quick
    skip_backend = [bool]$SkipBackend
    skip_frontend = [bool]$SkipFrontend
    skip_dependencies = [bool]$SkipDependencies
    full_pr_gate = (-not $Quick -and -not $SkipBackend -and -not $SkipFrontend -and -not $SkipDependencies)
    elapsed_seconds = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 2)
    results = @($results)
    pass = ($failed.Count -eq 0)
}
$summary | ConvertTo-Json -Depth 6
if ($failed.Count -gt 0) { exit 1 }
if ($summary.full_pr_gate) {
    Write-Host "Local preflight passed. Exact-head branch and PR GitHub CI are still mandatory."
}
else {
    Write-Warning "Partial preflight passed; full checks and exact-head GitHub CI remain required."
}
