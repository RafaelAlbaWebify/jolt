param(
    [string]$ApiUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Invoke-JoltJson(
    [string]$Uri,
    [string]$Method = "GET",
    [object]$Body = $null
) {
    $params = @{
        Uri = $Uri
        Method = $Method
        UseBasicParsing = $true
    }
    if ($null -ne $Body) {
        $params["ContentType"] = "application/json"
        $params["Body"] = ($Body | ConvertTo-Json -Depth 8)
    }

    $response = Invoke-WebRequest @params
    if ([string]::IsNullOrWhiteSpace($response.Content)) {
        return $null
    }
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

    ($pairs.GetEnumerator() |
        Sort-Object Name |
        ForEach-Object { "$($_.Name)=$($_.Value)" }) -join "&"
}

$health = Invoke-JoltJson "$ApiUrl/api/health"
if ($null -eq $health) {
    throw "JOLT API is not reachable at $ApiUrl."
}

$portfolio = @(
    @{
        label = "Application Support Engineer - EU Remote"
        keywords = "Application Support Engineer"
    },
    @{
        label = "Technical Support Engineer - EU Remote"
        keywords = "Technical Support Engineer"
    },
    @{
        label = "Production Support Engineer - EU Remote"
        keywords = "Production Support Engineer"
    },
    @{
        label = "IT Operations Engineer - EU Remote"
        keywords = "IT Operations Engineer"
    },
    @{
        label = "Microsoft 365 Support Engineer - EU Remote"
        keywords = "Microsoft 365 Support Engineer"
    },
    @{
        label = "Intune Engineer - EU Remote"
        keywords = "Intune Engineer"
    },
    @{
        label = "System Administrator - EU Remote"
        keywords = "System Administrator"
    }
)

$existingResponse = Invoke-JoltJson "$ApiUrl/api/linkedin-searches"
$existing = @()
if ($null -ne $existingResponse) {
    $existing = @($existingResponse)
}

$desiredKeys = @{}
$results = @()

foreach ($definition in $portfolio) {
    $encodedKeywords = [System.Uri]::EscapeDataString($definition.keywords).Replace("%20", "+")
    $url = "https://www.linkedin.com/jobs/search/?f_TPR=r604800&f_WT=2&geoId=91000000&keywords=$encodedKeywords&sortBy=DD"
    $key = Get-CanonicalKey $url
    $desiredKeys[$key] = $true

    $payload = @{
        label = $definition.label
        search_url = $url
        notes = "Core production search - EU remote - past week - newest first."
        enabled = $true
        max_jobs = 25
        max_pages = 3
    }

    $match = $existing |
        Where-Object { (Get-CanonicalKey ([string]$_.search_url)) -eq $key } |
        Select-Object -First 1

    if ($null -eq $match) {
        $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches" "POST" $payload
        $results += [pscustomobject]@{
            action = "created"
            label = $saved.label
            id = $saved.id
        }
        $existing += $saved
        continue
    }

    $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches/$($match.id)" "POST" $payload
    $results += [pscustomobject]@{
        action = "updated"
        label = $saved.label
        id = $saved.id
    }
}

foreach ($search in $existing) {
    if ($search.label -notlike "Acceptance - LinkedIn*") {
        continue
    }

    $key = Get-CanonicalKey ([string]$search.search_url)
    if ($desiredKeys.ContainsKey($key)) {
        continue
    }

    $payload = @{
        label = $search.label
        search_url = $search.search_url
        notes = "Legacy acceptance search retained for discovery history; disabled after production portfolio setup."
        enabled = $false
        max_jobs = [int]$search.max_jobs
        max_pages = [int]$search.max_pages
    }
    $saved = Invoke-JoltJson "$ApiUrl/api/linkedin-searches/$($search.id)" "POST" $payload
    $results += [pscustomobject]@{
        action = "disabled"
        label = $saved.label
        id = $saved.id
    }
}

$finalResponse = Invoke-JoltJson "$ApiUrl/api/linkedin-searches"
$final = @($finalResponse)
$core = @(
    $final |
        Where-Object { $_.enabled -eq $true } |
        Where-Object { $desiredKeys.ContainsKey((Get-CanonicalKey ([string]$_.search_url))) }
)

if ($core.Count -ne 7) {
    throw "Portfolio verification failed: expected 7 enabled core searches, found $($core.Count)."
}

Write-Host ""
Write-Host "JOLT real LinkedIn portfolio configured." -ForegroundColor Green
$results | Format-Table -AutoSize
Write-Host ""
Write-Host "Enabled core searches: $($core.Count)/7"
$core |
    Sort-Object label |
    Select-Object label, max_jobs, max_pages |
    Format-Table -AutoSize
