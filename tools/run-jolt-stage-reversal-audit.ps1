[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$AuditRoot = Join-Path $RepoRoot ".jolt\stage-reversal-audits\$Timestamp"
$Downloads = Join-Path $HOME "Downloads"
$ZipPath = Join-Path $Downloads "JOLT_STAGE_REVERSAL_AUDIT_$Timestamp.zip"

New-Item -ItemType Directory -Force -Path $AuditRoot | Out-Null
New-Item -ItemType Directory -Force -Path $Downloads | Out-Null

$health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 5
$frontend = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -UseBasicParsing -TimeoutSec 5

Write-Host "JOLT backend version: $($health.version)"
Write-Host "JOLT frontend status: $($frontend.StatusCode)"
Write-Warning "This supervised audit creates one clearly named local application fixture."
Write-Host "Running stage reversal, closure, reopening, and board persistence audit..."

Push-Location $BackendRoot
try {
    & uv run python (Join-Path $RepoRoot "tools\jolt-stage-reversal-audit.py") $AuditRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Playwright audit failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

Compress-Archive -Path (Join-Path $AuditRoot "*") -DestinationPath $ZipPath -Force

Write-Host ""
Write-Host "Audit completed."
Write-Host "ZIP: $ZipPath"
