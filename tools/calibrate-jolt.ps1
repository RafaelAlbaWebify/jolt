[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Staging = Join-Path $env:TEMP "JOLT_CALIBRATION_$Timestamp"
$OutputZip = Join-Path $Downloads "JOLT_CALIBRATION_$Timestamp.zip"
$SummaryPath = Join-Path $Staging "playwright-calibration-summary.json"
$SemanticSummaryPath = Join-Path $Staging "semantic-calibration-summary.json"

New-Item -ItemType Directory -Force -Path $Downloads, $Staging | Out-Null

$auditExitCode = 0
$auditFailure = $null
try {
    & (Join-Path $PSScriptRoot "start-jolt.ps1") -NoBrowser

    Push-Location $BackendRoot
    try {
        uv run python -m jolt.workbench_playwright_audit `
            --api-url "http://127.0.0.1:8000" `
            --app-url "http://127.0.0.1:5173" `
            --output-dir $Staging
        $auditExitCode = $LASTEXITCODE

        uv run python -m jolt.calibration_semantics `
            --api-url "http://127.0.0.1:8000" `
            --output $SemanticSummaryPath
        if ($LASTEXITCODE -ne 0 -and $auditExitCode -lt 2) {
            $auditExitCode = 2
        }
    }
    catch {
        $auditExitCode = 2
        $auditFailure = $_.Exception.Message
        [ordered]@{
            generated_at = (Get-Date).ToUniversalTime().ToString("o")
            result = "runner_failed"
            findings = @(
                [ordered]@{
                    severity = "error"
                    message = "Calibration runner failed before a complete summary was produced: $auditFailure"
                }
            )
        } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
    }

    $summary = $null
    if (Test-Path -LiteralPath $SummaryPath -PathType Leaf) {
        $summary = Get-Content -LiteralPath $SummaryPath -Raw | ConvertFrom-Json
        if ($null -ne $summary.findings) {
            foreach ($finding in @($summary.findings)) {
                $severity = [string]$finding.severity
                $message = [string]$finding.message
                Write-Host "[$severity] $message"
            }
        }
    }
    elseif ($auditExitCode -ne 0) {
        [ordered]@{
            generated_at = (Get-Date).ToUniversalTime().ToString("o")
            result = "runner_failed"
            findings = @(
                [ordered]@{
                    severity = "error"
                    message = "The Playwright calibration audit exited with code $auditExitCode without writing a summary."
                }
            )
        } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
    }

    $semanticFindingCount = 0
    if (Test-Path -LiteralPath $SemanticSummaryPath -PathType Leaf) {
        $semanticSummary = Get-Content -LiteralPath $SemanticSummaryPath -Raw | ConvertFrom-Json
        $semanticFindingCount = [int]$semanticSummary.finding_count
        foreach ($finding in @($semanticSummary.findings)) {
            Write-Host "[review] $([string]$finding.message)"
        }
    }

    Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $OutputZip -Force

    if ($auditExitCode -eq 0 -and $semanticFindingCount -eq 0) {
        Write-Host "Automated JOLT calibration passed: $OutputZip"
    }
    elseif ($auditExitCode -le 1) {
        Write-Warning "Automated JOLT calibration completed with review findings."
        Write-Host "Evidence package: $OutputZip"
        $global:LASTEXITCODE = 1
    }
    else {
        Write-Error "Automated JOLT calibration could not complete. Evidence package: $OutputZip" -ErrorAction Continue
        $global:LASTEXITCODE = 2
    }
}
finally {
    & (Join-Path $PSScriptRoot "stop-jolt.ps1") -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Staging -Recurse -Force -ErrorAction SilentlyContinue
}
