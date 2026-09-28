param(
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [int]$MaxJobs = 40,
    [int]$MaxPages = 4,
    [switch]$ReverseOrder
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

function Get-CanonicalKey([string]$Url) {
    $uri = [System.Uri]$Url
    $pairs = @{}
    foreach ($part in $uri.Query.TrimStart("?").Split("&", [System.StringSplitOptions]::RemoveEmptyEntries)) {
        $bits = $part.Split("=", 2)
        $key = [System.Uri]::UnescapeDataString($bits[0]).ToLowerInvariant()
        $value = if ($bits.Count -gt 1) { [System.Uri]::UnescapeDataString($bits[1]).Replace("+", " ") } else { "" }
        if ($key -notin @("currentjobid", "trackingid", "refid", "origin", "refresh", "start")) {
            $pairs[$key] = $value
        }
    }
    ($pairs.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join "&"
}

function Test-ExperimentOwnedSearch([object]$Search) {
    $label = [string]$Search.label
    $notes = [string]$Search.notes
    return (
        ($label -like "EXP *" -or $label -like "EXP2 *") -and
        $notes -like "Controlled LinkedIn search experiment*"
    )
}

function New-LinkedInSearchUrl(
    [string]$Keywords,
    [string]$GeoId,
    [bool]$RemoteOnly
) {
    $encodedKeywords = [System.Uri]::EscapeDataString($Keywords).Replace("%20", "+")
    $workType = if ($RemoteOnly) { "&f_WT=2" } else { "" }
    "https://www.linkedin.com/jobs/search/?f_TPR=r604800$workType&geoId=$GeoId&keywords=$encodedKeywords&sortBy=DD"
}

$null = Invoke-JoltJson "$ApiUrl/api/health"

$definitions = @(
    # Group S: same geo/sort, different support families.
    @{ label = "EXP B1 - Application Support newest EU"; keywords = "Application Support"; geo = "91000000"; group = "support" },
    @{ label = "EXP A1 - Technical Support broad EU"; keywords = "Technical Support Engineer"; geo = "91000000"; group = "support" },
    @{ label = "EXP2 S3 - SaaS Support EU"; keywords = "SaaS Support"; geo = "91000000"; group = "support" },
    @{ label = "EXP2 S4 - Infrastructure Support EU"; keywords = "Infrastructure Support"; geo = "91000000"; group = "support" },
    @{ label = "EXP2 S5 - Cloud Support EU"; keywords = "Cloud Support"; geo = "91000000"; group = "support" },

    # Group D: distinct occupational families, same geo/sort.
    @{ label = "EXP A3 - System Administrator broad EU"; keywords = "System Administrator"; geo = "91000000"; group = "distinct" },
    @{ label = "EXP2 D2 - IT Operations EU"; keywords = "IT Operations"; geo = "91000000"; group = "distinct" },
    @{ label = "EXP2 D3 - Infrastructure Operations EU"; keywords = "Infrastructure Operations"; geo = "91000000"; group = "distinct" },
    @{ label = "EXP2 D4 - Production Support EU"; keywords = "Production Support"; geo = "91000000"; group = "distinct" },

    # Group G: identical occupation, different geography.
    @{ label = "EXP2 G1 - Application Support Spain"; keywords = "Application Support"; geo = "105646813"; group = "geo" },
    @{ label = "EXP2 G2 - Application Support UK"; keywords = "Application Support"; geo = "101165590"; group = "geo" },
    @{ label = "EXP2 G3 - Application Support Worldwide"; keywords = "Application Support"; geo = "92000000"; group = "geo" }
)

if ($ReverseOrder) {
    [array]::Reverse($definitions)
}

$existing = @(Invoke-JoltJson "$ApiUrl/api/linkedin-searches")
$ids = @()

foreach ($definition in $definitions) {
    $url = New-LinkedInSearchUrl $definition.keywords $definition.geo $true
    $key = Get-CanonicalKey $url
    $payload = @{
        label = $definition.label
        search_url = $url
        notes = "Controlled LinkedIn search experiment v2 ($($definition.group)); not production portfolio."
        enabled = $true
        max_jobs = $MaxJobs
        max_pages = $MaxPages
    }

    # Only experiment-owned searches may be reused. If production already owns
    # the same canonical criteria, fail closed instead of mutating that search.
    $canonicalMatches = @(
        $existing |
            Where-Object { (Get-CanonicalKey ([string]$_.search_url)) -eq $key }
    )
    $experimentMatches = @(
        $canonicalMatches |
            Where-Object { Test-ExperimentOwnedSearch $_ }
    )

    if ($experimentMatches.Count -gt 1) {
        throw "Multiple experiment-owned saved searches use the same canonical criteria: $url"
    }

    if ($experimentMatches.Count -eq 1) {
        $match = $experimentMatches[0]
        $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches/$($match.id)" "POST" $payload
    } elseif ($canonicalMatches.Count -gt 0) {
        $owner = $canonicalMatches[0]
        throw (
            "Refusing to reuse canonical criteria owned by a non-experiment saved search. " +
            "ID=$($owner.id) LABEL='$($owner.label)' URL='$($owner.search_url)'"
        )
    } else {
        $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches" "POST" $payload
        $existing += $saved
    }
    $ids += $saved.id
}

$batch = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches" "POST" @{ saved_search_ids = $ids }
$batchId = $batch.id

Write-Host "Experiment v2 batch: $batchId"
Write-Host "Searches: $($ids.Count) | max jobs/search: $MaxJobs | max pages/search: $MaxPages | reverse=$($ReverseOrder.IsPresent)"

$null = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches/$batchId/start" "POST"

do {
    Start-Sleep -Seconds 5
    $status = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches/$batchId"
    Write-Host ("Status: {0} | completed {1}/{2} | captured {3}" -f $status.status, $status.completed_search_count, $status.selected_search_count, $status.captured_count)
} while ($status.status -in @("queued", "scheduled", "running"))

foreach ($id in $ids) {
    $search = Invoke-JoltJson "$ApiUrl/api/linkedin-searches/$id"
    if (-not (Test-ExperimentOwnedSearch $search)) {
        throw "Refusing to retire non-experiment saved search ID=$id LABEL='$($search.label)'"
    }
    $null = Invoke-JoltJson "$ApiUrl/api/linkedin-searches/$id" "POST" @{
        label = $search.label
        search_url = $search.search_url
        notes = $search.notes
        enabled = $false
        max_jobs = [int]$search.max_jobs
        max_pages = [int]$search.max_pages
    }
}

Write-Host ""
Write-Host "Final status: $($status.status)"
Write-Host "Batch ID: $batchId"
Write-Host "Experiment v2 searches retired after the run."
Write-Host "Analyze with:"
Write-Host "uv run --project backend python tools/analyze-linkedin-search-experiment.py --batch-id $batchId"
