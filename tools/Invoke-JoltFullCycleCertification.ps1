[CmdletBinding()]
param(
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
Set-StrictMode -Version Latest

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepositoryRoot "backend"
$FrontendRoot = Join-Path $RepositoryRoot "frontend"

if (-not $OutputDirectory) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputDirectory = Join-Path `
        $RepositoryRoot `
        "artifacts\local-full-cycle-certification\$stamp"
}

$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$databaseToken = [Guid]::NewGuid().ToString("N")
$databasePath = Join-Path `
    ([IO.Path]::GetTempPath()) `
    "jolt-full-cycle-certification-$databaseToken.db"
$databasePath = [IO.Path]::GetFullPath($databasePath)
$databaseUrl = "sqlite:///$($databasePath.Replace('\', '/'))"

$backendPidFile = Join-Path $OutputDirectory "backend.pid"
$frontendPidFile = Join-Path $OutputDirectory "frontend.pid"
$backendLog = Join-Path $OutputDirectory "backend.log"
$backendErrorLog = Join-Path $OutputDirectory "backend-error.log"
$frontendLog = Join-Path $OutputDirectory "frontend.log"
$frontendErrorLog = Join-Path $OutputDirectory "frontend-error.log"
$evidenceDirectory = Join-Path $OutputDirectory "evidence"

$managedEnvironmentNames = @(
    "JOLT_DATABASE_URL",
    "JOLT_CERT_BACKEND_PID_FILE",
    "JOLT_CERT_FRONTEND_PID_FILE",
    "JOLT_CERT_BACKEND_LOG",
    "JOLT_CERT_FRONTEND_LOG"
)

$previousEnvironment = @{}
foreach ($name in $managedEnvironmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable(
        $name,
        "Process"
    )
}

function Test-TcpPortInUse {
    param([Parameter(Mandatory)][int]$Port)

    $client = [Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        if (-not $task.Wait(350)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-HttpEndpoint {
    param(
        [Parameter(Mandatory)][string]$Url,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest `
                -Uri $Url `
                -UseBasicParsing `
                -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 400
        }
    }

    throw "Timed out waiting for $Url"
}

function Stop-ProcessTreeFromPidFile {
    param([Parameter(Mandatory)][string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return
    }

    $text = (Get-Content $PidFile -Raw).Trim()
    $processId = 0
    if (-not [int]::TryParse($text, [ref]$processId)) {
        return
    }

    & taskkill.exe /PID $processId /T /F 2>$null | Out-Null
}

try {
    if (Test-TcpPortInUse -Port 8000) {
        throw (
            "Port 8000 is already in use. Stop the normal JOLT backend before " +
            "running certification. The certification runner will not reuse it."
        )
    }
    if (Test-TcpPortInUse -Port 5173) {
        throw (
            "Port 5173 is already in use. Stop the normal JOLT frontend before " +
            "running certification."
        )
    }

    [Environment]::SetEnvironmentVariable(
        "JOLT_DATABASE_URL",
        $databaseUrl,
        "Process"
    )
    [Environment]::SetEnvironmentVariable(
        "JOLT_CERT_BACKEND_PID_FILE",
        $backendPidFile,
        "Process"
    )
    [Environment]::SetEnvironmentVariable(
        "JOLT_CERT_FRONTEND_PID_FILE",
        $frontendPidFile,
        "Process"
    )
    [Environment]::SetEnvironmentVariable(
        "JOLT_CERT_BACKEND_LOG",
        $backendLog,
        "Process"
    )
    [Environment]::SetEnvironmentVariable(
        "JOLT_CERT_FRONTEND_LOG",
        $frontendLog,
        "Process"
    )

    Remove-Item `
        "$databasePath", `
        "$databasePath-wal", `
        "$databasePath-shm" `
        -Force `
        -ErrorAction SilentlyContinue

    Push-Location $BackendRoot
    try {
        uv run alembic upgrade head
    }
    finally {
        Pop-Location
    }

    $backend = Start-Process `
        -FilePath "uv.exe" `
        -ArgumentList @(
            "run",
            "uvicorn",
            "jolt.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000"
        ) `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput $backendLog `
        -RedirectStandardError $backendErrorLog `
        -PassThru `
        -NoNewWindow

    Set-Content -Path $backendPidFile -Value $backend.Id -NoNewline

    $frontend = Start-Process `
        -FilePath "npm.cmd" `
        -ArgumentList @(
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1"
        ) `
        -WorkingDirectory $FrontendRoot `
        -RedirectStandardOutput $frontendLog `
        -RedirectStandardError $frontendErrorLog `
        -PassThru `
        -NoNewWindow

    Set-Content -Path $frontendPidFile -Value $frontend.Id -NoNewline

    Wait-HttpEndpoint -Url "http://127.0.0.1:8000/api/health"
    Wait-HttpEndpoint -Url "http://127.0.0.1:5173"

    $identity = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8000/api/runtime-identity" `
        -TimeoutSec 10

    if (
        -not $identity.database.database_path.ToLowerInvariant().Contains(
            "jolt-full-cycle-certification"
        )
    ) {
        throw (
            "Isolation verification failed before certification. Backend uses: " +
            $identity.database.database_path
        )
    }

    Push-Location $BackendRoot
    try {
        uv run python `
            ..\tools\jolt-full-cycle-playwright-certification-recovery.py `
            --output-dir $evidenceDirectory
    }
    finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "Certification completed using disposable database:"
    Write-Host $databasePath
    Write-Host "Evidence:"
    Write-Host $OutputDirectory
}
finally {
    Stop-ProcessTreeFromPidFile -PidFile $frontendPidFile
    Stop-ProcessTreeFromPidFile -PidFile $backendPidFile

    Start-Sleep -Milliseconds 500

    Remove-Item `
        "$databasePath", `
        "$databasePath-wal", `
        "$databasePath-shm" `
        -Force `
        -ErrorAction SilentlyContinue

    foreach ($name in $managedEnvironmentNames) {
        [Environment]::SetEnvironmentVariable(
            $name,
            $previousEnvironment[$name],
            "Process"
        )
    }
}
