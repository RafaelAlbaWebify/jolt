param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Require-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Required command '$Name' was not found on PATH."
    }
    return $command.Source
}

function Wait-JoltEndpoint {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][bool]$Available,
        [int]$TimeoutSeconds = 60
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $current = $false
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 2
            $current = $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
        }
        catch {
            $current = $false
        }
        if ($current -eq $Available) { return }
        Start-Sleep -Milliseconds 250
    }
    $state = if ($Available) { "available" } else { "unavailable" }
    throw "Timed out waiting for $Uri to become $state."
}

function Stop-JoltProcessTree {
    param([Parameter(Mandatory = $true)][string]$PidFile)
    if (-not (Test-Path -LiteralPath $PidFile)) { return }
    $rawPid = (Get-Content -LiteralPath $PidFile -Raw).Trim()
    $servicePid = 0
    if (-not [int]::TryParse($rawPid, [ref]$servicePid)) { return }

    try { & taskkill /PID $servicePid /T /F | Out-Null } catch { }

    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $servicePid -ErrorAction SilentlyContinue)) {
            return
        }
        Start-Sleep -Milliseconds 200
    }
    throw "Timed out waiting for service process $servicePid to exit."
}

$UvCommand = Require-Command -Name "uv.exe"
$NpmCommand = Require-Command -Name "npm.cmd"

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$BackendRoot = Join-Path $RepoRoot "backend"
$FrontendRoot = Join-Path $RepoRoot "frontend"
$Runner = Join-Path $RepoRoot "tools\jolt-full-cycle-playwright-certification-recovery.py"
foreach ($required in @($BackendRoot, $FrontendRoot, $Runner)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required JOLT path does not exist: $required"
    }
}

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) "JOLT_FULL_CYCLE_$Stamp"
$EvidenceRoot = Join-Path $WorkRoot "evidence"
$Downloads = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads"
$ZipPath = Join-Path $Downloads "JOLT_FULL_CYCLE_CERTIFICATION_$Stamp.zip"
$DatabasePath = Join-Path $WorkRoot "jolt-certification.db"
$BackendLog = Join-Path $WorkRoot "backend.log"
$FrontendLog = Join-Path $WorkRoot "frontend.log"
$BackendErrorLog = Join-Path $WorkRoot "backend-error.log"
$FrontendErrorLog = Join-Path $WorkRoot "frontend-error.log"
$BackendPid = Join-Path $WorkRoot "backend.pid"
$FrontendPid = Join-Path $WorkRoot "frontend.pid"
$CertificationLog = Join-Path $WorkRoot "certification.log"

New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
New-Item -ItemType Directory -Force -Path $Downloads | Out-Null

$DatabaseUrlPath = $DatabasePath.Replace("\", "/")
$env:JOLT_DATABASE_URL = "sqlite:///$DatabaseUrlPath"
$env:JOLT_CERT_BACKEND_PID_FILE = $BackendPid
$env:JOLT_CERT_FRONTEND_PID_FILE = $FrontendPid
$env:JOLT_CERT_BACKEND_LOG = $BackendLog
$env:JOLT_CERT_FRONTEND_LOG = $FrontendLog

try {
    Push-Location $BackendRoot
    try {
        & $UvCommand sync --all-groups
        if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }
        & $UvCommand run playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium installation failed." }
        & $UvCommand run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "Disposable database migration failed." }
    }
    finally {
        Pop-Location
    }

    Push-Location $FrontendRoot
    try {
        & $NpmCommand ci --ignore-scripts --no-fund
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
    }
    finally {
        Pop-Location
    }

    $BackendProcess = Start-Process -FilePath $UvCommand `
        -ArgumentList @("run", "uvicorn", "jolt.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $BackendRoot `
        -RedirectStandardOutput $BackendLog `
        -RedirectStandardError $BackendErrorLog `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $BackendPid -Value $BackendProcess.Id -Encoding ascii

    $FrontendProcess = Start-Process -FilePath $NpmCommand `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
        -WorkingDirectory $FrontendRoot `
        -RedirectStandardOutput $FrontendLog `
        -RedirectStandardError $FrontendErrorLog `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $FrontendPid -Value $FrontendProcess.Id -Encoding ascii

    Wait-JoltEndpoint -Uri "http://127.0.0.1:8000/api/health" -Available $true
    Wait-JoltEndpoint -Uri "http://127.0.0.1:5173" -Available $true

    Push-Location $BackendRoot
    try {
        & $UvCommand run python $Runner --output-dir $EvidenceRoot 2>&1 | Tee-Object -FilePath $CertificationLog
        if ($LASTEXITCODE -ne 0) { throw "Full-cycle certification failed." }

        $DatabaseSummaryPath = Join-Path $WorkRoot "database-summary.json"
        @'
import json
import os
import sqlite3
from pathlib import Path

url = os.environ["JOLT_DATABASE_URL"]
path = Path(url.removeprefix("sqlite:///"))
result = {"database": str(path), "tables": {}}
connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
for (table,) in connection.execute("select name from sqlite_master where type='table' order by name"):
    if table.startswith("sqlite_"):
        continue
    safe = table.replace('"', '""')
    result["tables"][table] = connection.execute(f'SELECT COUNT(*) FROM "{safe}"').fetchone()[0]
revision = connection.execute("select version_num from alembic_version").fetchone()
result["alembic_version"] = revision[0] if revision else None
connection.close()
print(json.dumps(result, indent=2))
'@ | & $UvCommand run python - | Set-Content -LiteralPath $DatabaseSummaryPath -Encoding utf8
        if ($LASTEXITCODE -ne 0) { throw "Disposable database summary failed." }
    }
    finally {
        Pop-Location
    }

    Stop-JoltProcessTree -PidFile $BackendPid
    Stop-JoltProcessTree -PidFile $FrontendPid
    Wait-JoltEndpoint -Uri "http://127.0.0.1:8000/api/health" -Available $false
    Wait-JoltEndpoint -Uri "http://127.0.0.1:5173" -Available $false
    Start-Sleep -Milliseconds 500

    if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
    Compress-Archive -Path (Join-Path $WorkRoot "*") -DestinationPath $ZipPath -CompressionLevel Optimal
    Write-Host "`nUPLOAD THIS FILE:`n$ZipPath" -ForegroundColor Green
}
finally {
    Stop-JoltProcessTree -PidFile $BackendPid
    Stop-JoltProcessTree -PidFile $FrontendPid
}