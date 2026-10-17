[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Downloads = Join-Path $HOME "Downloads"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Stage = Join-Path $env:TEMP "JOLT_OPERATOR_ACCEPTANCE_$Stamp"
$Zip = Join-Path $Downloads "JOLT_OPERATOR_ACCEPTANCE_$Stamp.zip"
New-Item -ItemType Directory -Force -Path $Stage, $Downloads | Out-Null

try {
    $Health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 10
    $Front = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -TimeoutSec 10
    if ($Front.StatusCode -ne 200) { throw "Frontend is not healthy." }

    $RepoCommit = (& git -C $RepoRoot rev-parse HEAD).Trim()
    $BackendCommit = [string]$Health.git_commit
    $Metadata = [ordered]@{
        generated_at = (Get-Date).ToString("o")
        repository_commit = $RepoCommit
        backend_health = $Health
        frontend_http_status = $Front.StatusCode
        read_only = $true
    }
    $Metadata | ConvertTo-Json -Depth 8 |
        Set-Content -Path (Join-Path $Stage "runtime.json") -Encoding UTF8

    Push-Location $BackendRoot
    try {
        uv run --no-sync python -m jolt.read_only_operator_acceptance --output-dir $Stage
        $AcceptanceCode = $LASTEXITCODE
    }
    finally { Pop-Location }

    @(
        "JOLT operator acceptance: read-only browser and API sample.",
        "No AI imports, Apply/Reject actions, browser captures or live database writes are requested.",
        "Review screenshots and JSON for personal data before sharing this ZIP.",
        "Repository commit: $RepoCommit",
        "Acceptance command exit code: $AcceptanceCode"
    ) | Set-Content -Path (Join-Path $Stage "README.txt") -Encoding UTF8

    Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Zip -Force
    Write-Host "Acceptance package: $Zip"
    if ($AcceptanceCode -ne 0) { throw "Acceptance reported failure; upload ZIP for diagnosis." }
}
finally {
    Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue
}
