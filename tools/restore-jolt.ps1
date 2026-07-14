[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$BackupPath,
    [Parameter(Mandatory)][string]$TargetPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$ActiveDatabase = [System.IO.Path]::GetFullPath((Join-Path $BackendRoot "data\jolt.db"))
$BackupPath = [System.IO.Path]::GetFullPath($BackupPath)
$TargetPath = [System.IO.Path]::GetFullPath($TargetPath)

if ($TargetPath -eq $ActiveDatabase) {
    throw "Refusing to overwrite the active JOLT database. Restore to a separate path first."
}
if (Test-Path -LiteralPath $TargetPath) {
    throw "Restore target already exists: $TargetPath"
}

Push-Location $BackendRoot
try {
    uv run python -m jolt.backup verify --backup $BackupPath | Out-Null
    uv run python -m jolt.backup restore --backup $BackupPath --target $TargetPath
}
finally {
    Pop-Location
}

Write-Host "Verified JOLT restore created at: $TargetPath"
Write-Host "The active JOLT database was not changed."
