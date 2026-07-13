[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Staging = Join-Path $env:TEMP "JOLT_REVIEW_AUDIT_$Timestamp"
$OutputZip = Join-Path $Downloads "JOLT_REVIEW_AUDIT_$Timestamp.zip"
$SummaryPath = Join-Path $Staging "audit-summary.json"

New-Item -ItemType Directory -Force -Path $Staging, $Downloads | Out-Null

try {
    & (Join-Path $PSScriptRoot "start-jolt.ps1") -NoBrowser

    Push-Location $BackendRoot
    try {
        uv sync --all-groups
        if ($LASTEXITCODE -ne 0) { throw "Backend dependencies could not be prepared." }

        uv run playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium could not be installed." }

        $auditExitCode = 0
        uv run python -m jolt.review_audit --output-dir $Staging
        $auditExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if (Test-Path (Join-Path $RepoRoot ".jolt\logs")) {
        Copy-Item (Join-Path $RepoRoot ".jolt\logs") (Join-Path $Staging "service-logs") -Recurse
    }

    @(
        "JOLT automated review audit",
        "Generated: $((Get-Date).ToString('o'))",
        "",
        "Review audit-summary.json, opportunities.json, and workbench-full.png.",
        "The screenshot captures the complete local workbench.",
        "No application or recruiter action was performed."
    ) | Set-Content -Path (Join-Path $Staging "README.txt") -Encoding UTF8

    Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $OutputZip -Force
    Write-Host "Review audit package created: $OutputZip"

    if ($auditExitCode -ne 0) {
        throw "The audit found one or more errors. Review the ZIP created in Downloads."
    }
}
finally {
    Remove-Item $Staging -Recurse -Force -ErrorAction SilentlyContinue
}
