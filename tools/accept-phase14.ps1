[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Database = Join-Path $BackendRoot "data\jolt.db"
$Downloads = Join-Path $HOME "Downloads"
if (-not (Test-Path -LiteralPath $Database -PathType Leaf)) {
    throw "JOLT database not found: $Database"
}
New-Item -ItemType Directory -Path $Downloads -Force | Out-Null
Write-Host "Testing a safe backup and an isolated database copy. The live JOLT database will NOT be upgraded or changed."
Push-Location $BackendRoot
try {
    uv run python -m jolt.phase14_acceptance --database $Database --output $Downloads
    if ($LASTEXITCODE -ne 0) { throw "Phase 1.4 isolated acceptance failed (exit code $LASTEXITCODE)." }
}
finally {
    Pop-Location
}
Write-Host "Upload this report: $Downloads\JOLT_PHASE_1_4_ACCEPTANCE.json"
