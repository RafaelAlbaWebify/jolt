[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$Headed,
    [switch]$KeepServicesRunning
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Wait-ForUrl {
    param(
        [Parameter(Mandatory)] [string]$Url,
        [int]$Attempts = 90
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            if ($attempt -eq $Attempts) {
                throw "Service did not become ready at $Url. Last error: $($_.Exception.Message)"
            }
        }
        Start-Sleep -Seconds 1
    }
}

$RepositoryRoot = (Resolve-Path $RepositoryRoot).Path
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outputRoot = Join-Path $RepositoryRoot "artifacts\windows-certification\$timestamp"
$viewportOutput = Join-Path $outputRoot 'viewport-fit'
$fullCycleOutput = Join-Path $outputRoot 'full-cycle'
$certificationDataRoot = Join-Path $outputRoot 'data'
$certificationDatabasePath = Join-Path $certificationDataRoot 'jolt-certification.db'
New-Item -ItemType Directory -Path $viewportOutput -Force | Out-Null
New-Item -ItemType Directory -Path $fullCycleOutput -Force | Out-Null
New-Item -ItemType Directory -Path $certificationDataRoot -Force | Out-Null

$startScript = Join-Path $RepositoryRoot 'tools\start-jolt.ps1'
$stopScript = Join-Path $RepositoryRoot 'tools\stop-jolt.ps1'
$serviceStatePath = Join-Path $RepositoryRoot '.jolt\services.json'
if (-not (Test-Path $startScript)) { throw "Missing $startScript" }
if (-not (Test-Path $stopScript)) { throw "Missing $stopScript" }

$certificationEnvironmentNames = @(
    'JOLT_DATABASE_URL',
    'JOLT_CERT_BACKEND_PID_FILE',
    'JOLT_CERT_FRONTEND_PID_FILE',
    'JOLT_CERT_BACKEND_LOG',
    'JOLT_CERT_FRONTEND_LOG'
)
$originalEnvironment = @{}
foreach ($name in $certificationEnvironmentNames) {
    $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$originalLocation = Get-Location
$startedHere = $false
try {
    Set-Location $RepositoryRoot

    # Certification must never reuse the user's normal services or database. A fresh
    # database makes repeated Windows runs deterministic and directly comparable to CI.
    & $stopScript
    Remove-Item -LiteralPath $certificationDatabasePath -Force -ErrorAction SilentlyContinue
    $sqlitePath = $certificationDatabasePath.Replace('\', '/')
    [Environment]::SetEnvironmentVariable('JOLT_DATABASE_URL', "sqlite:///$sqlitePath", 'Process')

    & $startScript -NoBrowser
    $startedHere = $true

    Wait-ForUrl -Url 'http://127.0.0.1:8000/api/health'
    Wait-ForUrl -Url 'http://127.0.0.1:5173'

    if (-not (Test-Path $serviceStatePath)) {
        throw "Windows certification requires JOLT service state at $serviceStatePath."
    }
    $serviceState = Get-Content -LiteralPath $serviceStatePath -Raw | ConvertFrom-Json
    if (-not $serviceState.backend_pid -or -not $serviceState.frontend_pid) {
        throw "JOLT service state does not contain backend_pid and frontend_pid."
    }

    $backendPidFile = Join-Path $fullCycleOutput 'backend.pid'
    $frontendPidFile = Join-Path $fullCycleOutput 'frontend.pid'
    $backendRestartLog = Join-Path $fullCycleOutput 'backend-restart.log'
    $frontendRestartLog = Join-Path $fullCycleOutput 'frontend-restart.log'
    [string]$serviceState.backend_pid | Set-Content -LiteralPath $backendPidFile -Encoding ascii
    [string]$serviceState.frontend_pid | Set-Content -LiteralPath $frontendPidFile -Encoding ascii
    [Environment]::SetEnvironmentVariable('JOLT_CERT_BACKEND_PID_FILE', $backendPidFile, 'Process')
    [Environment]::SetEnvironmentVariable('JOLT_CERT_FRONTEND_PID_FILE', $frontendPidFile, 'Process')
    [Environment]::SetEnvironmentVariable('JOLT_CERT_BACKEND_LOG', $backendRestartLog, 'Process')
    [Environment]::SetEnvironmentVariable('JOLT_CERT_FRONTEND_LOG', $frontendRestartLog, 'Process')

    Push-Location (Join-Path $RepositoryRoot 'backend')
    try {
        uv sync --all-groups
        uv run playwright install chromium

        $viewportArgs = @(
            'run', 'python', '..\tools\jolt-viewport-fit-playwright-audit.py',
            '--output-dir', $viewportOutput
        )
        if ($Headed) { $viewportArgs += '--headed' }
        & uv @viewportArgs
        if ($LASTEXITCODE -ne 0) { throw "Viewport fit certification failed with exit code $LASTEXITCODE." }

        & uv run python '..\tools\jolt-full-cycle-playwright-certification-recovery.py' '--output-dir' $fullCycleOutput
        if ($LASTEXITCODE -ne 0) { throw "Full-cycle certification failed with exit code $LASTEXITCODE." }
    }
    finally {
        Pop-Location
    }

    $summary = [ordered]@{
        result = 'passed'
        certified_at = (Get-Date).ToString('o')
        repository_root = $RepositoryRoot
        git_head = (git rev-parse HEAD).Trim()
        viewport = '1680x945'
        isolated_database = $certificationDatabasePath
        services_started_by_certification = $startedHere
        viewport_evidence = $viewportOutput
        full_cycle_evidence = $fullCycleOutput
    }
    $summary | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $outputRoot 'windows-certification-summary.json') -Encoding UTF8
    Write-Host "JOLT Windows certification passed. Evidence: $outputRoot" -ForegroundColor Green
}
finally {
    Set-Location $originalLocation
    if ($startedHere -and -not $KeepServicesRunning) {
        & $stopScript
    }
    foreach ($name in $certificationEnvironmentNames) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process')
    }
}
