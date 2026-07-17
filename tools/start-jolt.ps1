[CmdletBinding()]
param(
    [switch]$StartLinkedInCapture,
    [string]$SearchUrl = "https://www.linkedin.com/jobs/search/",
    [ValidateRange(1, 50)]
    [int]$MaxJobs = 10,
    [ValidateRange(1, 10)]
    [int]$MaxPages = 3,
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
$ExpectedBackendVersion = "0.8.0"

function Resolve-ApplicationCommand {
    param([Parameter(Mandatory)][string[]]$Names)

    foreach ($name in $Names) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -ne $command) {
            return $command.Source
        }
    }

    throw "Required application '$($Names -join "' or '")' was not found in PATH."
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory)][string]$FailureMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage Exit code: $LASTEXITCODE."
    }
}

function Wait-HttpEndpoint {
    param(
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][string]$Name,
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if ($null -ne $Process -and $Process.HasExited) {
            throw "$Name exited before becoming ready at $Url. Exit code: $($Process.ExitCode). Review logs in $LogRoot."
        }

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

function Assert-FreshBackend {
    $health = Invoke-RestMethod -Uri "$BackendUrl/api/health" -TimeoutSec 5
    if ([string]$health.version -ne $ExpectedBackendVersion) {
        throw "Unexpected JOLT backend version '$($health.version)'. Expected '$ExpectedBackendVersion'. A stale backend may still own port 8000."
    }

    $openApi = Invoke-RestMethod -Uri "$BackendUrl/openapi.json" -TimeoutSec 5
    if ($null -eq $openApi.paths.PSObject.Properties['/api/captures/linkedin/live']) {
        throw "The running backend does not expose /api/captures/linkedin/live. Refusing to start capture against a stale API."
    }
}

function Stop-ProcessSafely {
    param([System.Diagnostics.Process]$Process)
    if ($null -ne $Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
}

$stage = "resolving required applications"
$uvCommand = Resolve-ApplicationCommand -Names @("uv.exe", "uv")
$nodeCommand = Resolve-ApplicationCommand -Names @("node.exe", "node")
$npmCommand = Resolve-ApplicationCommand -Names @("npm.cmd")

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $LogRoot | Out-Null
Remove-Item (Join-Path $LogRoot "*.log") -Force -ErrorAction SilentlyContinue

& (Join-Path $PSScriptRoot "stop-jolt.ps1")

$backendProcess = $null
$frontendProcess = $null
try {
    $stage = "preparing backend dependencies"
    Write-Host "Preparing backend dependencies..."
    Push-Location $BackendRoot
    try {
        Invoke-NativeCommand -FilePath $uvCommand -Arguments @("sync", "--all-groups") `
            -FailureMessage "Backend dependencies could not be prepared."
        New-Item -ItemType Directory -Force -Path (Join-Path $BackendRoot "data") | Out-Null
        Invoke-NativeCommand -FilePath $uvCommand -Arguments @("run", "alembic", "upgrade", "head") `
            -FailureMessage "Database migrations could not be applied."
    }
    finally {
        Pop-Location
    }

    $stage = "preparing frontend dependencies"
    Write-Host "Preparing frontend dependencies..."
    Push-Location $FrontendRoot
    try {
        # Call npm.cmd explicitly. The npm PowerShell shim can fail under StrictMode
        # with an internal missing 'Statement' property on some Windows installations.
        Invoke-NativeCommand -FilePath $npmCommand -Arguments @("ci") `
            -FailureMessage "Frontend dependencies could not be prepared."
    }
    finally {
        Pop-Location
    }

    $stage = "starting backend"
    Write-Host "Starting JOLT backend..."
    $backendProcess = Start-Process -FilePath $uvCommand `
        -ArgumentList @("run", "uvicorn", "jolt.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput $BackendOutLog `
        -RedirectStandardError $BackendErrLog `
        -PassThru `
        -WindowStyle Hidden

    $stage = "starting frontend"
    Write-Host "Starting JOLT frontend..."
    $frontendProcess = Start-Process -FilePath $npmCommand `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
        -WorkingDirectory $FrontendRoot `
        -RedirectStandardOutput $FrontendOutLog `
        -RedirectStandardError $FrontendErrLog `
        -PassThru `
        -WindowStyle Hidden

    $stage = "waiting for backend readiness"
    Wait-HttpEndpoint -Url "$BackendUrl/api/health" -Name "JOLT backend" -Process $backendProcess
    Assert-FreshBackend

    $stage = "waiting for frontend readiness"
    Wait-HttpEndpoint -Url $FrontendUrl -Name "JOLT frontend" -Process $frontendProcess

    @{
        backend_pid = $backendProcess.Id
        frontend_pid = $frontendProcess.Id
        backend_url = $BackendUrl
        frontend_url = $FrontendUrl
        backend_version = $ExpectedBackendVersion
        started_at = (Get-Date).ToString("o")
    } | ConvertTo-Json | Set-Content -Path $StatePath -Encoding UTF8

    Write-Host ""
    Write-Host "JOLT is ready."
    Write-Host "Application: $FrontendUrl"
    Write-Host "Backend health: $BackendUrl/api/health"
    Write-Host "Backend version: $ExpectedBackendVersion"
    Write-Host "Logs: $LogRoot"

    if (-not $NoBrowser) {
        Start-Process $FrontendUrl
    }

    if ($StartLinkedInCapture) {
        & (Join-Path $PSScriptRoot "run-linkedin-capture.ps1") `
            -SearchUrl $SearchUrl `
            -MaxJobs $MaxJobs `
            -MaxPages $MaxPages `
            -ApiUrl $BackendUrl
    }
}
catch {
    Stop-ProcessSafely -Process $frontendProcess
    Stop-ProcessSafely -Process $backendProcess
    Remove-Item $StatePath -Force -ErrorAction SilentlyContinue
    throw "JOLT startup failed during stage '$stage'. $($_.Exception.Message)"
}
