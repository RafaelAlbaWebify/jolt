[CmdletBinding()]
param(
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [ValidateRange(1, 100)][int]$MaxJobs = 25,
    [ValidateRange(1, 10)][int]$MaxPages = 3,
    [int]$PollSeconds = 2
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$EvidencePath = Join-Path $Downloads "JOLT_LINKEDIN_PORTFOLIO_ACCEPTANCE_$Stamp.json"
$ExchangePath = Join-Path $Downloads "JOLT_LINKEDIN_PORTFOLIO_AI_EXCHANGE_$Stamp.json"

$Defs = @(
  @{ label = "Acceptance - LinkedIn IT Support"; search_url = "https://www.linkedin.com/jobs/search/?f_TPR=r604800&f_WT=2&geoId=91000000&keywords=IT%20Support&sortBy=DD" },
  @{ label = "Acceptance - LinkedIn Application Support Engineer"; search_url = "https://www.linkedin.com/jobs/search/?f_TPR=r604800&f_WT=2&geoId=91000000&keywords=Application%20Support%20Engineer&sortBy=DD" }
)

function Invoke-JoltJson([string]$Uri, [string]$Method = "GET", [object]$Body = $null) {
    if ($null -eq $Body) {
        Invoke-RestMethod -Uri $Uri -Method $Method
        return
    }
    Invoke-RestMethod -Uri $Uri -Method $Method -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

function Get-Key([string]$Url) {
    $uri = [System.Uri]$Url
    $pairs = @()
    foreach ($part in $uri.Query.TrimStart("?").Split("&", [System.StringSplitOptions]::RemoveEmptyEntries)) {
        $kv = $part.Split("=", 2)
        $name = [System.Uri]::UnescapeDataString($kv[0]).ToLowerInvariant()
        if ($name -in @("currentjobid","trackingid","refid","origin","refresh","start")) { continue }
        $value = if ($kv.Count -gt 1) { [System.Uri]::UnescapeDataString($kv[1].Replace("+", " ")) } else { "" }
        $pairs += "$name=$value"
    }
    return (($pairs | Sort-Object) -join "&").ToLowerInvariant()
}

try { Invoke-RestMethod -Uri "$ApiUrl/api/health" -Method GET | Out-Null } catch { throw "JOLT API is not reachable. Start it with .\tools\start-jolt.ps1" }
$existing = @(Invoke-JoltJson "$ApiUrl/api/linkedin-searches")
foreach ($item in $existing) {
    if ($null -eq $item.PSObject.Properties["search_url"]) {
        throw "Saved-search API returned an unexpected object without search_url."
    }
}
$selected = @()
foreach ($def in $Defs) {
    $key = Get-Key $def.search_url
    $match = $existing | Where-Object { (Get-Key ([string]$_.search_url)) -eq $key } | Select-Object -First 1
    $body = @{ label=$def.label; search_url=$def.search_url; notes="R-025 Phase 5 real multi-search acceptance."; enabled=$true; max_jobs=$MaxJobs; max_pages=$MaxPages }
    if ($null -eq $match) { $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches" "POST" $body }
    else { $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches/$($match.id)" "POST" $body }
    $selected += $saved
}

$batch = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches" "POST" @{ saved_search_ids=@($selected.id) }
$batch = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches/$($batch.id)/start" "POST"
Write-Host "Batch started: $($batch.id). Keep the visible Chromium window open; authenticate there if LinkedIn asks."
$terminal = @("completed","completed_with_failures","failed")
do {
    Start-Sleep -Seconds $PollSeconds
    $batch = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches/$($batch.id)"
    $progress = ($batch.searches | ForEach-Object { "$($_.position):$($_.status) $($_.captured_count)/$($_.verified_count)" }) -join " | "
    Write-Host "$($batch.status) | $progress"
} while ($batch.status -notin $terminal)

$passed = ($batch.status -eq "completed" -and $batch.completed_search_count -eq 2 -and $batch.failed_search_count -eq 0 -and @($batch.searches | Where-Object { -not $_.capture_run_id }).Count -eq 0)
$report = [ordered]@{ acceptance_type="jolt_linkedin_search_portfolio_real_acceptance"; performed_at=(Get-Date).ToString("o"); repository_head=(git -C $RepoRoot rev-parse HEAD).Trim(); batch_id=$batch.id; batch_status=$batch.status; selected_search_count=$batch.selected_search_count; completed_search_count=$batch.completed_search_count; failed_search_count=$batch.failed_search_count; captured_count=$batch.captured_count; verified_count=$batch.verified_count; new_posting_count=$batch.new_posting_count; duplicate_count=$batch.duplicate_count; searches=@($batch.searches); passed=$passed }
$report | ConvertTo-Json -Depth 12 | Set-Content -Path $EvidencePath -Encoding UTF8
if (-not $passed) { throw "Real multi-search acceptance failed. Evidence: $EvidencePath" }
Invoke-WebRequest -Uri "$ApiUrl/api/linkedin-discovery-batches/$($batch.id)/ai-review-exchange" -OutFile $ExchangePath
$exchange = Get-Content -Raw $ExchangePath | ConvertFrom-Json
$report.review_exchange_path = $ExchangePath
$report.review_counts = $exchange.counts
$report | ConvertTo-Json -Depth 12 | Set-Content -Path $EvidencePath -Encoding UTF8
Write-Host "PASS: $EvidencePath"
Write-Host "AI review exchange: $ExchangePath"
Write-Host "BatchId: $($batch.id)"
