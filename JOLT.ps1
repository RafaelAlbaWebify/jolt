[CmdletBinding()]
param(
    [ValidateSet("start", "stop", "validate", "capture", "audit")]
    [string]$Action = "start",
    [string]$RepoPath = "",
    [string]$SearchUrl = "https://www.linkedin.com/jobs/search/",
    [ValidateRange(1, 50)]
    [int]$MaxJobs = 10,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-JoltRepository {
    param([string]$ExplicitPath)

    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($ExplicitPath) { $candidates.Add($ExplicitPath) }
    if ($env:JOLT_REPO_PATH) { $candidates.Add($env:JOLT_REPO_PATH) }
    $candidates.Add((Split-Path -Parent $PSCommandPath))
    $candidates.Add((Join-Path $env:USERPROFILE "Documents\GitHub\jolt"))
    $candidates.Add((Join-Path $env:USERPROFILE "GitHub\jolt"))
    $candidates.Add((Join-Path $env:USERPROFILE "Desktop\jolt"))

    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        $resolved = Resolve-Path -LiteralPath $candidate -ErrorAction SilentlyContinue
        if ($null -eq $resolved) { continue }
        $root = $resolved.Path
        if ((Test-Path (Join-Path $root "backend")) -and
            (Test-Path (Join-Path $root "frontend")) -and
            (Test-Path (Join-Path $root "tools"))) {
            return $root
        }
    }

    throw "JOLT repository not found. Set JOLT_REPO_PATH or run with -RepoPath 'C:\path\to\jolt'."
}

$root = Resolve-JoltRepository -ExplicitPath $RepoPath
$tools = Join-Path $root "tools"

switch ($Action) {
    "start" {
        & (Join-Path $tools "start-jolt.ps1") -NoBrowser:$NoBrowser
    }
    "stop" {
        & (Join-Path $tools "stop-jolt.ps1")
    }
    "validate" {
        & (Join-Path $tools "validate-jolt.ps1")
    }
    "capture" {
        & (Join-Path $tools "start-jolt.ps1") `
            -StartLinkedInCapture `
            -SearchUrl $SearchUrl `
            -MaxJobs $MaxJobs `
            -NoBrowser:$NoBrowser
    }
    "audit" {
        & (Join-Path $tools "audit-jolt.ps1")
    }
}
