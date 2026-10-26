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
    if ($null -eq $property) { return }

    $processId = [int]$property.Value
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -eq $process) { return }

    # PID values can be reused after a crash. Never stop a recorded PID without
    # checking its command line AND that it belongs to this JOLT checkout.
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if ($null -eq $processInfo) {
        Write-Warning "Skipping $DisplayName PID ${processId}: process identity unavailable."
        return
    }
    $commandLine = [string]$processInfo.CommandLine
    $isRepoProcess = $commandLine.IndexOf($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    $isExpectedRole = if ($PropertyName -eq "backend_pid") {
        $commandLine -match 'uvicorn|jolt\.main:app|uv'
    } else {
        $commandLine -match 'vite|npm|node'
    }
    if (-not ($isRepoProcess -and $isExpectedRole)) {
        Write-Warning "Skipping $DisplayName PID ${processId}: command line does not match this JOLT checkout."
        return
    }
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped $DisplayName (PID $processId)."
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
        $matchesCheckout = $commandLine.IndexOf($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
        $matchesService = if ($commandLine -match "uvicorn|jolt\\.main:app") {
            $commandLine -match 'uvicorn|jolt\.main:app|uv'
        } else {
            $commandLine -match 'vite|npm|node'
        }
        $isJolt = $matchesCheckout -and $matchesService

        if ($isJolt) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped stale $DisplayName listener (PID $processId, port $Port)."
        }
        else {
            Write-Host "Leaving unrelated process PID $processId on port $Port untouched."
        }
    }
}

$state = $null
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

# Also inspect previously selected dynamic ports. Never stop unrelated owners.
$ports = @(5173, 8000)
if ($null -ne $state) {
    foreach ($urlProperty in @("frontend_url", "backend_url")) {
        $value = $state.PSObject.Properties[$urlProperty]
        if ($null -ne $value) {
            try { $ports += ([uri]$value.Value).Port } catch {}
        }
    }
}
foreach ($port in ($ports | Sort-Object -Unique)) {
    Stop-JoltListener -Port $port -DisplayName "JOLT service"
}

Write-Host "JOLT services are stopped."
