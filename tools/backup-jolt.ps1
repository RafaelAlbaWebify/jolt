[CmdletBinding()]
param(
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$DatabasePath = Join-Path $BackendRoot "data\jolt.db"
if (-not (Test-Path -LiteralPath $DatabasePath -PathType Leaf)) {
    throw "JOLT database not found: $DatabasePath"
}

if (-not $OutputPath) {
    $downloads = Join-Path $env:USERPROFILE "Downloads"
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputPath = Join-Path $downloads "JOLT_BACKUP_$stamp.zip"
}
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)

Push-Location $BackendRoot
try {
    uv run python -m jolt.backup create --database $DatabasePath --output $OutputPath
    uv run python -m jolt.backup verify --backup $OutputPath | Out-Null
}
finally {
    Pop-Location
}

Write-Host "Verified JOLT backup: $OutputPath"
