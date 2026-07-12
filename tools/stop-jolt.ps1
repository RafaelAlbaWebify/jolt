[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $RepoRoot ".jolt"
$StatePath = Join-Path $RuntimeRoot "services.json"

function Stop-RecordedProcess {
    param(
        [Parameter(Mandatory)][object]$State,
        [Parameter(Mandatory)][string]$PropertyName,
        [Parameter(Mandatory)][string]$DisplayName
    )

    $property = $State.PSObject.Properties[$PropertyName]
    if ($null -eq $property) {
        return
    }

    $processId = [int]$property.Value
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -ne $process) {
        Stop-Process -Id $processId -Force
        Write-Host "Stopped $DisplayName (PID $processId)."
    }
}

if (-not (Test-Path $StatePath)) {
    Write-Host "No recorded JOLT services are running."
    return
}

try {
    $state = Get-Content -Path $StatePath -Raw | ConvertFrom-Json
    Stop-RecordedProcess -State $state -PropertyName "frontend_pid" -DisplayName "JOLT frontend"
    Stop-RecordedProcess -State $state -PropertyName "backend_pid" -DisplayName "JOLT backend"
}
finally {
    Remove-Item $StatePath -Force -ErrorAction SilentlyContinue
}

Write-Host "JOLT services are stopped."
