param(
    [string]$OutputRoot = "$HOME\Downloads"
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Out = Join-Path $OutputRoot "JOLT_LIVE_UI_AUDIT_$Stamp"
$Zip = "$Out.zip"

$health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 10
$null = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -UseBasicParsing -TimeoutSec 10

New-Item -ItemType Directory -Force -Path $Out | Out-Null

Push-Location (Join-Path $Repo "backend")
try {
    uv run python ../tools/jolt-live-ui-playwright-audit.py --output-dir $Out
}
finally {
    Pop-Location
}

Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $Zip -Force
Write-Host ""
Write-Host "JOLT live UI audit complete."
Write-Host "Evidence directory: $Out"
Write-Host "ZIP: $Zip"
Write-Host "Upload this ZIP to the JOLT chat for section-by-section UX analysis."
