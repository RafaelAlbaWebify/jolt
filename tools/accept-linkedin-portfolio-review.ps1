[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BatchId,
    [Parameter(Mandatory = $true)][string]$ReviewFile,
    [string]$ApiUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$EvidencePath = Join-Path $Downloads "JOLT_LINKEDIN_PORTFOLIO_REVIEW_ACCEPTANCE_$Stamp.json"
if (-not (Test-Path $ReviewFile)) { throw "Review JSON was not found: $ReviewFile" }
function Get-Batch { return Invoke-RestMethod -Uri "$ApiUrl/api/linkedin-discovery-batches/$BatchId" -Method GET }
$payload = Get-Content -Raw $ReviewFile
$import = Invoke-RestMethod -Uri "$ApiUrl/api/linkedin-discovery-batches/$BatchId/ai-review-import" -Method POST -ContentType "application/json" -Body $payload
$before = Get-Batch
& (Join-Path $PSScriptRoot "stop-jolt.ps1")
& (Join-Path $PSScriptRoot "start-jolt.ps1")
$deadline = (Get-Date).AddMinutes(2)
$ready = $false
do { Start-Sleep -Seconds 2; try { Invoke-RestMethod -Uri "$ApiUrl/health" -Method GET | Out-Null; $ready = $true } catch { $ready = $false } } while (-not $ready -and (Get-Date) -lt $deadline)
if (-not $ready) { throw "JOLT did not become healthy after restart." }
$after = Get-Batch
if ($after.id -ne $before.id -or $after.status -ne $before.status) { throw "Discovery batch state did not persist across restart." }
$report = [ordered]@{ acceptance_type="jolt_linkedin_search_portfolio_review_restart_acceptance"; performed_at=(Get-Date).ToString("o"); repository_head=(git -C $RepoRoot rev-parse HEAD).Trim(); batch_id=$BatchId; review_file=(Resolve-Path $ReviewFile).Path; import=$import; batch_status_before_restart=$before.status; batch_status_after_restart=$after.status; batch_persisted=$true; passed=$true }
$report | ConvertTo-Json -Depth 10 | Set-Content -Path $EvidencePath -Encoding UTF8
Write-Host "PASS: consolidated AI review imported and persisted across restart."
Write-Host "Evidence: $EvidencePath"
