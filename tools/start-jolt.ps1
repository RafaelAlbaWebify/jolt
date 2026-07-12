[CmdletBinding()]
param(
    [switch]$StartLinkedInCapture,
    [string]$SearchUrl = "https://www.linkedin.com/jobs/search/",
    [ValidateRange(1, 50)]
    [int]$MaxJobs = 10,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$FrontendRoot = Join-Path $RepoRoot "frontend"
$RuntimeRoot = Join-Path $RepoRoot ".jolt"
$LogRoot = Join-Path $RuntimeRoot "logs"
$StatePath = Join-Path $RuntimeRoot "services.json"
$BackendOutLog = Join-Path $LogRoot "backend.out.log"
$BackendErrLog = Join-Path $LogRoot "backend.err.log"
$FrontendOutLog = Join-Path $LogRoot "frontend.out.log"
$FrontendErrLog = Join-Path $LogRoot "frontend.err.log"
$BackendUrl = "http://127.0.0.1:8000"
$FrontendUrl = "http://127.0.0.1:5173"

function Assert-Command {
    param([Parameter(Mandatory)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

function Wait-HttpEndpoint {
    param(
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][string]$Name,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 750
        }
    } while ((Get-Date) -lt $deadline)

    throw "$Name did not become ready at $Url within $TimeoutSeconds seconds. Review logs in $LogRoot."
}

function Stop-ProcessSafely {
    param([System.Diagnostics.Process]$Process)
    if ($null -ne $Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
}

Assert-Command -Name "uv"
Assert-Command -Name "node"
Assert-Command -Name "npm"

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $LogRoot | Out-Null
Remove-Item (Join-Path $LogRoot "*.log") -Force -ErrorAction SilentlyContinue

if (Test-Path $StatePath) {
    & (Join-Path $PSScriptRoot "stop-jolt.ps1")
}

Write-Host "Preparing backend dependencies..."
Push-Location $BackendRoot
try {
    uv sync --all-groups
    New-Item -ItemType Directory -Force -Path (Join-Path $BackendRoot "data") | Out-Null
    uv run alembic upgrade head
}
finally {
    Pop-Location
}

Write-Host "Preparing frontend dependencies..."
Push-Location $FrontendRoot
try {
    npm install
}
finally {
    Pop-Location
}

$backendProcess = $null
$frontendProcess = $null
try {
    Write-Host "Starting JOLT backend..."
    $backendProcess = Start-Process -FilePath "uv" `
        -ArgumentList @("run", "uvicorn", "jolt.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput $BackendOutLog `
        -RedirectStandardError $BackendErrLog `
        -PassThru `
        -WindowStyle Hidden

    Write-Host "Starting JOLT frontend..."
    $frontendProcess = Start-Process -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
        -WorkingDirectory $FrontendRoot `
        -RedirectStandardOutput $FrontendOutLog `
        -RedirectStandardError $FrontendErrLog `
        -PassThru `
        -WindowStyle Hidden

    Wait-HttpEndpoint -Url "$BackendUrl/api/health" -Name "JOLT backend"
    Wait-HttpEndpoint -Url $FrontendUrl -Name "JOLT frontend"

    @{
        backend_pid = $backendProcess.Id
        frontend_pid = $frontendProcess.Id
        backend_url = $BackendUrl
        frontend_url = $FrontendUrl
        started_at = (Get-Date).ToString("o")
    } | ConvertTo-Json | Set-Content -Path $StatePath -Encoding UTF8

    Write-Host ""
    Write-Host "JOLT is ready."
    Write-Host "Application: $FrontendUrl"
    Write-Host "Backend health: $BackendUrl/api/health"
    Write-Host "Logs: $LogRoot"
    Write-Host "Stop command: .\tools\stop-jolt.ps1"

    if (-not $NoBrowser) {
        Start-Process $FrontendUrl
    }

    if ($StartLinkedInCapture) {
        & (Join-Path $PSScriptRoot "run-linkedin-capture.ps1") `
            -SearchUrl $SearchUrl `
            -MaxJobs $MaxJobs `
            -ApiUrl $BackendUrl
    }
}
catch {
    Stop-ProcessSafely -Process $frontendProcess
    Stop-ProcessSafely -Process $backendProcess
    Remove-Item $StatePath -Force -ErrorAction SilentlyContinue
    throw
}
