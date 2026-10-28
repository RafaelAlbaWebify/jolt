# Delivery A operator acceptance: read-only, no installation or schema changes.
# Run from the JOLT checkout: pwsh -NoProfile -File tools/accept-delivery-a.ps1
[CmdletBinding()]
param(
    [string]$Database = "backend/data/jolt.db",
    [string]$Output = "$HOME/Downloads/JOLT_A_ACCEPTANCE.zip"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    if (-not (Test-Path -LiteralPath $Database -PathType Leaf)) {
        throw "Database not found: $Database"
    }
    if (-not (Test-Path -LiteralPath "tools/jolt_operator_report.py" -PathType Leaf)) {
        throw "Operator diagnostic script is missing"
    }
    $before = (Get-Item -LiteralPath $Database).Length
    $started = [System.Diagnostics.Stopwatch]::StartNew()
    & python tools/jolt_operator_report.py $Database --output $Output
    if ($LASTEXITCODE -ne 0) { throw "Operator diagnostic returned exit code $LASTEXITCODE" }
    $started.Stop()
    $after = (Get-Item -LiteralPath $Database).Length
    if ($after -ne $before) { throw "Database size changed during read-only acceptance" }
    if (-not (Test-Path -LiteralPath $Output -PathType Leaf)) {
        throw "Diagnostic ZIP was not created"
    }
    Write-Host ("Delivery A diagnostic: {0}" -f (Resolve-Path -LiteralPath $Output))
    Write-Host ("Elapsed seconds: {0:N2}" -f $started.Elapsed.TotalSeconds)
    Write-Host "API/browser and cross-store recovery are NOT certified by this command."
}
finally {
    Pop-Location
}
