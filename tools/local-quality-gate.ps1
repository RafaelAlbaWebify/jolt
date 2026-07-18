[CmdletBinding()]
param(
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $env:TEMP "JOLT_LOCAL_QUALITY_$Timestamp.txt"
}

$PreviousProfilePath = $env:JOLT_PROFILE_PATH
$TestProfilePath = Join-Path $env:TEMP "jolt-no-private-profile-for-tests.json"
Remove-Item -LiteralPath $TestProfilePath -Force -ErrorAction SilentlyContinue
$env:JOLT_PROFILE_PATH = $TestProfilePath

$results = [ordered]@{}

function Invoke-GateCommand {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][scriptblock]$Command
    )

    Write-Host "Running $Name..."
    & $Command
    if ($LASTEXITCODE -ne 0) {
        $results[$Name] = "failed"
        throw "$Name failed."
    }
    $results[$Name] = "passed"
}

try {
    Push-Location $BackendRoot
    try {
        Invoke-GateCommand -Name "ruff_check" -Command { uv run ruff check src tests }
        Invoke-GateCommand -Name "ruff_format" -Command { uv run ruff format --check src tests }
        Invoke-GateCommand -Name "pyright" -Command { uv run pyright }
        Invoke-GateCommand -Name "pytest" -Command { uv run pytest }
    }
    finally {
        Pop-Location
    }

    $summary = [ordered]@{
        generated_utc = (Get-Date).ToUniversalTime().ToString("o")
        repository = [ordered]@{
            branch = (& git -C $RepoRoot branch --show-current | Out-String).Trim()
            commit = (& git -C $RepoRoot rev-parse HEAD | Out-String).Trim()
            clean = [string]::IsNullOrWhiteSpace((& git -C $RepoRoot status --porcelain | Out-String))
        }
        checks = $results
        private_profile_isolated = $true
        result = "passed"
    }
    $summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
    Write-Host "JOLT local quality gate passed: $OutputPath"
}
finally {
    if ($null -eq $PreviousProfilePath) {
        Remove-Item Env:JOLT_PROFILE_PATH -ErrorAction SilentlyContinue
    }
    else {
        $env:JOLT_PROFILE_PATH = $PreviousProfilePath
    }
}
