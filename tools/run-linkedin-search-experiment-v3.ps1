param(
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [int]$MaxJobs = 20,
    [int]$MaxPages = 3
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
        ($label -like "EXP *" -or $label -like "EXP2 *" -or $label -like "EXP3 *") -and
        $notes -like "Controlled LinkedIn search experiment*"
    )
}

function New-LinkedInSearchUrl([string]$Keywords) {
    $encodedKeywords = [System.Uri]::EscapeDataString($Keywords).Replace("%20", "+")
    "https://www.linkedin.com/jobs/search/?f_TPR=r604800&f_WT=2&geoId=91000000&keywords=$encodedKeywords&sortBy=DD"
}

$null = Invoke-JoltJson "$ApiUrl/api/health"

# Each pair isolates one variable: the production query's EMEA suffix.
# Odd positions are the current production criteria; even positions are
# otherwise-identical comparators without EMEA.
$definitions = @(
    @{ label = "Application Support Engineer - EU Remote"; keywords = "Application Support Engineer EMEA"; owner = "production"; pair = "application-support" },
    @{ label = "EXP3 A2 - Application Support Engineer EU no EMEA"; keywords = "Application Support Engineer"; owner = "experiment"; pair = "application-support" },

    @{ label = "SaaS Support Engineer - EU Remote"; keywords = "SaaS Support Engineer EMEA"; owner = "production"; pair = "saas-support" },
    @{ label = "EXP3 B2 - SaaS Support Engineer EU no EMEA"; keywords = "SaaS Support Engineer"; owner = "experiment"; pair = "saas-support" },

    @{ label = "Microsoft 365 Support Engineer - EU Remote"; keywords = "Microsoft 365 Support Engineer EMEA"; owner = "production"; pair = "m365-support" },
    @{ label = "EXP3 C2 - Microsoft 365 Support Engineer EU no EMEA"; keywords = "Microsoft 365 Support Engineer"; owner = "experiment"; pair = "m365-support" },

    @{ label = "Intune Engineer - EU Remote"; keywords = "Intune Endpoint Engineer EMEA"; owner = "production"; pair = "intune-endpoint" },
    @{ label = "EXP3 D2 - Intune Endpoint Engineer EU no EMEA"; keywords = "Intune Endpoint Engineer"; owner = "experiment"; pair = "intune-endpoint" }
)

$existing = @(Invoke-JoltJson "$ApiUrl/api/linkedin-searches")
$ids = @()
$experimentIds = @()

foreach ($definition in $definitions) {
    $url = New-LinkedInSearchUrl $definition.keywords
    $key = Get-CanonicalKey $url
    $matches = @(
        $existing |
            Where-Object { (Get-CanonicalKey ([string]$_.search_url)) -eq $key }
    )

    if ($definition.owner -eq "production") {
        if ($matches.Count -ne 1) {
            throw "Expected exactly one production saved search for '$($definition.label)', found $($matches.Count). URL=$url"
        }

        $saved = $matches[0]
        if (Test-ExperimentOwnedSearch $saved) {
            throw "Expected production ownership but canonical criteria belong to experiment search '$($saved.label)'."
        }
        if (-not [bool]$saved.enabled) {
            throw "Production saved search is disabled: $($saved.label)"
        }

        Write-Host "READ-ONLY production: $($saved.label)"
        $ids += $saved.id
        continue
    }

    $experimentMatches = @($matches | Where-Object { Test-ExperimentOwnedSearch $_ })
    $productionMatches = @($matches | Where-Object { -not (Test-ExperimentOwnedSearch $_) })

    if ($experimentMatches.Count -gt 1 -or $productionMatches.Count -gt 1) {
        throw "Ambiguous canonical ownership for comparator URL: $url"
    }

    if ($productionMatches.Count -eq 1) {
        $saved = $productionMatches[0]
        if (-not [bool]$saved.enabled) {
            throw "Comparator criteria are owned by a disabled production search: $($saved.label)"
        }
        Write-Host "READ-ONLY comparator already in production: $($saved.label)"
    } elseif ($experimentMatches.Count -eq 1) {
        $match = $experimentMatches[0]
        $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches/$($match.id)" "POST" @{
            label = $definition.label
            search_url = $url
            notes = "Controlled LinkedIn search experiment v3 ($($definition.pair)); not production portfolio."
            enabled = $true
            max_jobs = $MaxJobs
            max_pages = $MaxPages
        }
        $experimentIds += $saved.id
    } else {
        $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches" "POST" @{
            label = $definition.label
            search_url = $url
            notes = "Controlled LinkedIn search experiment v3 ($($definition.pair)); not production portfolio."
            enabled = $true
            max_jobs = $MaxJobs
            max_pages = $MaxPages
        }
        $existing += $saved
        $experimentIds += $saved.id
    }

    $ids += $saved.id
}

$batch = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches" "POST" @{
    saved_search_ids = $ids
    max_jobs_override = $MaxJobs
    max_pages_override = $MaxPages
}
$batchId = $batch.id

Write-Host ""
Write-Host "Experiment v3 batch: $batchId"
Write-Host "Searches: $($ids.Count) | batch override: $MaxJobs jobs / $MaxPages pages per search"

$null = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches/$batchId/start" "POST"

do {
    Start-Sleep -Seconds 5
    $status = Invoke-JoltJson "$ApiUrl/api/linkedin-discovery-batches/$batchId"
    Write-Host ("Status: {0} | completed {1}/{2} | captured {3}" -f $status.status, $status.completed_search_count, $status.selected_search_count, $status.captured_count)
} while ($status.status -in @("queued", "scheduled", "running"))

foreach ($id in $experimentIds) {
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
Write-Host "Only EXP3-owned comparator searches were retired. Production searches were never modified."
Write-Host "Analyze with:"
Write-Host "uv run --project backend python tools/analyze-linkedin-search-experiment.py --batch-id $batchId"
