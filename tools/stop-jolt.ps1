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
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped $DisplayName (PID $processId)."
    }
}

function Stop-JoltListener {
    param(
        [Parameter(Mandatory)][int]$Port,
        [Parameter(Mandatory)][string]$DisplayName
    )

    $connections = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $processId = [int]$connection.OwningProcess
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        if ($null -eq $processInfo) {
            continue
        }

        $commandLine = [string]$processInfo.CommandLine
        $isJolt = $commandLine -match [regex]::Escape($RepoRoot) -or
            ($Port -eq 8000 -and $commandLine -match "uvicorn.+jolt\.main:app") -or
            ($Port -eq 5173 -and $commandLine -match "vite.+127\.0\.0\.1")

        if ($isJolt) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped stale $DisplayName listener (PID $processId, port $Port)."
        }
        else {
            throw "Port $Port is occupied by a non-JOLT process (PID $processId). Stop it manually before starting JOLT."
        }
    }
}

if (Test-Path $StatePath) {
    try {
        $state = Get-Content -Path $StatePath -Raw | ConvertFrom-Json
        Stop-RecordedProcess -State $state -PropertyName "frontend_pid" -DisplayName "JOLT frontend"
        Stop-RecordedProcess -State $state -PropertyName "backend_pid" -DisplayName "JOLT backend"
    }
    finally {
        Remove-Item $StatePath -Force -ErrorAction SilentlyContinue
    }
}

Stop-JoltListener -Port 5173 -DisplayName "JOLT frontend"
Stop-JoltListener -Port 8000 -DisplayName "JOLT backend"

Write-Host "JOLT services are stopped."
