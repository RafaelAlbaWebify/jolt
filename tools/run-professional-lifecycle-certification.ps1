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

$UvCommand = Require-Command -Name "uv.exe"
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$BackendRoot = Join-Path $RepoRoot "backend"
if (-not (Test-Path -LiteralPath $BackendRoot)) {
    throw "Backend directory does not exist: $BackendRoot"
}

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) "JOLT_PROFESSIONAL_LIFECYCLE_$Stamp"
$EvidenceRoot = Join-Path $WorkRoot "evidence"
$Downloads = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads"
$ZipPath = Join-Path $Downloads "JOLT_PROFESSIONAL_LIFECYCLE_CERTIFICATION_$Stamp.zip"
$DatabasePath = Join-Path $WorkRoot "jolt-professional-lifecycle.db"
$TranscriptPath = Join-Path $EvidenceRoot "certification-transcript.txt"
$PytestLogPath = Join-Path $EvidenceRoot "pytest-output.txt"
$JunitPath = Join-Path $EvidenceRoot "pytest-junit.xml"
$DatabaseSummaryPath = Join-Path $EvidenceRoot "database-summary.json"
$SummaryPath = Join-Path $EvidenceRoot "certification-summary.json"

New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
New-Item -ItemType Directory -Force -Path $Downloads | Out-Null

$DatabaseUrlPath = $DatabasePath.Replace("\", "/")
$env:JOLT_DATABASE_URL = "sqlite:///$DatabaseUrlPath"
$result = "failed"
$errorMessage = ""
$tests = @(
    "tests/test_professional_capture_stale_recovery.py",
    "tests/test_professional_capture_artifact_staging.py",
    "tests/test_professional_intelligence_retention.py",
    "tests/test_professional_capture_progress_cancellation.py",
    "tests/test_professional_intelligence_supervised_capture.py",
    "tests/test_schema_authority.py"
)

Start-Transcript -LiteralPath $TranscriptPath -Force | Out-Null
try {
    Push-Location $BackendRoot
    try {
        & $UvCommand sync --all-groups
        if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }

        & $UvCommand run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "Disposable database migration failed." }

        @'
import json
import os
import sqlite3
from pathlib import Path

url = os.environ["JOLT_DATABASE_URL"]
path = Path(url.removeprefix("sqlite:///"))
connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
columns = [
    row[1]
    for row in connection.execute("PRAGMA table_info(professional_capture_runs)").fetchall()
]
required = {
    "source_progress_json",
    "completed_source_count",
    "current_source_id",
    "cancel_requested",
    "progress_updated_at",
}
missing = sorted(required.difference(columns))
result = {
    "database": str(path),
    "alembic_version": revision[0] if revision else None,
    "professional_capture_run_columns": columns,
    "required_progress_columns": sorted(required),
    "missing_progress_columns": missing,
}
print(json.dumps(result, indent=2))
if result["alembic_version"] != "20260727_0016" or missing:
    raise SystemExit(1)
connection.close()
'@ | & $UvCommand run python - | Set-Content -LiteralPath $DatabaseSummaryPath -Encoding utf8
        if ($LASTEXITCODE -ne 0) { throw "Disposable schema verification failed." }

        & $UvCommand run pytest -q @tests --junitxml=$JunitPath 2>&1 |
            Tee-Object -FilePath $PytestLogPath
        if ($LASTEXITCODE -ne 0) { throw "Professional lifecycle tests failed." }

        $result = "passed"
    }
    finally {
        Pop-Location
    }
}
catch {
    $errorMessage = $_.Exception.Message
    Write-Error $errorMessage
}
finally {
    $summary = [ordered]@{
        result = $result
        completed_at = (Get-Date).ToUniversalTime().ToString("o")
        repository_root = $RepoRoot
        disposable_database = $DatabasePath
        expected_alembic_revision = "20260727_0016"
        live_linkedin_access = $false
        production_database_used = $false
        focused_tests = $tests
        error = $errorMessage
    }
    $summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $SummaryPath -Encoding utf8
    Stop-Transcript | Out-Null

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive -Path (Join-Path $EvidenceRoot "*") -DestinationPath $ZipPath -CompressionLevel Optimal
}

if ($result -ne "passed") {
    throw "Professional lifecycle certification failed. Evidence: $ZipPath"
}

Write-Host "`nUPLOAD THIS FILE:`n$ZipPath" -ForegroundColor Green
