param(
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [int]$MaxJobs = 20,
    [int]$MaxPages = 2
)

$ErrorActionPreference = "Stop"

function Invoke-JoltJson(
    [string]$Uri,
    [string]$Method = "GET",
    [object]$Body = $null
) {
    $params = @{ Uri = $Uri; Method = $Method; UseBasicParsing = $true }
    if ($null -ne $Body) {
        $params["ContentType"] = "application/json"
        $params["Body"] = ($Body | ConvertTo-Json -Depth 12)
    }
    $response = Invoke-WebRequest @params
    if ([string]::IsNullOrWhiteSpace($response.Content)) { return $null }
    $response.Content | ConvertFrom-Json
}

function New-LinkedInSearchUrl(
    [string]$Keywords,
    [string]$GeoId,
    [bool]$RemoteOnly,
    [string]$SortBy
) {
    $encodedKeywords = [System.Uri]::EscapeDataString($Keywords).Replace("%20", "+")
    $workType = if ($RemoteOnly) { "&f_WT=2" } else { "" }
    "https://www.linkedin.com/jobs/search/?f_TPR=r604800$workType&geoId=$GeoId&keywords=$encodedKeywords&sortBy=$SortBy"
}

$null = Invoke-JoltJson "$ApiUrl/api/health"

$definitions = @(
    @{ label = "EXP A1 - Technical Support broad EU"; keywords = "Technical Support Engineer"; geo = "91000000"; sort = "DD" },
    @{ label = "EXP A2 - Technical Support exact EU"; keywords = '" + String.fromCharCode(34) + "Technical Support Engineer" + String.fromCharCode(34) + "'; geo = "91000000"; sort = "DD" },
    @{ label = "EXP A3 - System Administrator broad EU"; keywords = "System Administrator"; geo = "91000000"; sort = "DD" },
    @{ label = "EXP A4 - System Administrator exact EU"; keywords = '" + String.fromCharCode(34) + "System Administrator" + String.fromCharCode(34) + "'; geo = "91000000"; sort = "DD" },
    @{ label = "EXP B1 - Application Support newest EU"; keywords = "Application Support"; geo = "91000000"; sort = "DD" },
    @{ label = "EXP B2 - Application Support relevance EU"; keywords = "Application Support"; geo = "91000000"; sort = "R" },
    @{ label = "EXP C1 - Application Support contractor global"; keywords = '" + String.fromCharCode(34) + "Application Support" + String.fromCharCode(34) + " contractor'; geo = "92000000"; sort = "DD" },
    @{ label = "EXP C2 - IT Operations contractor global"; keywords = '" + String.fromCharCode(34) + "IT Operations" + String.fromCharCode(34) + " contractor'; geo = "92000000"; sort = "DD" },
    @{ label = "EXP C3 - Technical Support CET global"; keywords = '" + String.fromCharCode(34) + "Technical Support" + String.fromCharCode(34) + " CET'; geo = "92000000"; sort = "DD" },
    @{ label = "EXP C4 - Technical Support EMEA global"; keywords = '" + String.fromCharCode(34) + "Technical Support" + String.fromCharCode(34) + " EMEA'; geo = "92000000"; sort = "DD" }
)

$existing = @(Invoke-JoltJson "$ApiUrl/api/linkedin-searches")
$ids = @()

foreach ($definition in $definitions) {
    $url = New-LinkedInSearchUrl $definition.keywords $definition.geo $true $definition.sort
    $payload = @{
        label = $definition.label
        search_url = $url
        notes = "Controlled LinkedIn search-behaviour experiment; not production portfolio."
        enabled = $true
        max_jobs = $MaxJobs
        max_pages = $MaxPages
    }
    $match = $existing | Where-Object { $_.label -eq $definition.label } | Select-Object -First 1
    if ($null -eq $match) {
        $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches" "POST" $payload
        $existing += $saved
    } else {
        $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches/$($match.id)" "POST" $payload
    }
    $ids += $saved.id
}

$batch = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches" "POST" @{ saved_search_ids = $ids }
$batchId = $batch.id

Write-Host "Experiment batch: $batchId"
Write-Host "Searches: $($ids.Count) | max jobs/search: $MaxJobs | max pages/search: $MaxPages"

$null = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches/$batchId/start" "POST"

do {
    Start-Sleep -Seconds 5
    $status = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches/$batchId"
    Write-Host ("Status: {0} | completed {1}/{2} | captured {3}" -f $status.status, $status.completed_search_count, $status.selected_search_count, $status.captured_count)
} while ($status.status -in @("queued", "scheduled", "running"))

Write-Host ""
Write-Host "Final status: $($status.status)"
Write-Host "Batch ID: $batchId"
Write-Host "Analyze with:"
Write-Host "uv run --project backend python tools/analyze-linkedin-search-experiment.py --batch-id $batchId"
