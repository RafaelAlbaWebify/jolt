[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $RepoRoot ".jolt"
$LogRoot = Join-Path $RuntimeRoot "logs"
$StatePath = Join-Path $RuntimeRoot "services.json"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Staging = Join-Path $env:TEMP "JOLT_VALIDATION_$Timestamp"
$OutputZip = Join-Path $Downloads "JOLT_WINDOWS_VALIDATION_$Timestamp.zip"

New-Item -ItemType Directory -Force -Path $Staging, $Downloads | Out-Null

try {
    $results = [ordered]@{
        generated_at = (Get-Date).ToString("o")
        repository = $RepoRoot
        state_file_present = Test-Path $StatePath
        backend = [ordered]@{ status = "not_checked"; url = "http://127.0.0.1:8000/api/health" }
        frontend = [ordered]@{ status = "not_checked"; url = "http://127.0.0.1:5173" }
        commands = [ordered]@{}
    }

    foreach ($command in @("uv", "node", "npm", "git")) {
        $resolved = Get-Command $command -ErrorAction SilentlyContinue
        $results.commands[$command] = if ($null -eq $resolved) { "missing" } else { $resolved.Source }
    }

    foreach ($endpoint in @(
        @{ Name = "backend"; Url = "http://127.0.0.1:8000/api/health" },
        @{ Name = "frontend"; Url = "http://127.0.0.1:5173" }
    )) {
        try {
            $response = Invoke-WebRequest -Uri $endpoint.Url -UseBasicParsing -TimeoutSec 5
            $results[$endpoint.Name].status = "reachable"
            $results[$endpoint.Name].http_status = $response.StatusCode
            if ($endpoint.Name -eq "backend") {
                $results[$endpoint.Name].body = $response.Content
            }
        }
        catch {
            $results[$endpoint.Name].status = "unreachable"
            $results[$endpoint.Name].error = $_.Exception.Message
        }
    }

    if (Test-Path $StatePath) {
        Copy-Item $StatePath (Join-Path $Staging "services.json")
    }
    if (Test-Path $LogRoot) {
        Copy-Item $LogRoot (Join-Path $Staging "logs") -Recurse
    }

    $results | ConvertTo-Json -Depth 6 | Set-Content `
        -Path (Join-Path $Staging "validation_summary.json") `
        -Encoding UTF8

    @(
        "JOLT Windows validation",
        "Generated: $($results.generated_at)",
        "Backend: $($results.backend.status)",
        "Frontend: $($results.frontend.status)",
        "",
        "Review validation_summary.json and the logs directory for details."
    ) | Set-Content -Path (Join-Path $Staging "README.txt") -Encoding UTF8

    Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $OutputZip -Force
    Write-Host "Validation package created: $OutputZip"
}
finally {
    Remove-Item $Staging -Recurse -Force -ErrorAction SilentlyContinue
}
