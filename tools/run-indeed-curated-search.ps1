[CmdletBinding()]
param(
    [ValidateSet("app-remote", "technical-remote", "operations-remote", "systems-remote", "support-local", "systems-local")]
    [string]$Search = "app-remote",
    [string]$SearchUrl = "",
    [ValidateSet(1, 3, 7, 14)][int]$Days = 7,
    [ValidateSet("date", "relevance")][string]$Sort = "date",
    [ValidateRange(0, 100)][int]$RadiusKm = 0,
    [switch]$List,
    [ValidateRange(1, 100)][int]$MaxJobs = 15,
    [ValidateRange(1, 10)][int]$MaxPages = 1,
    [switch]$SyncDependencies
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# These are discovery hypotheses based on JOLT's active LinkedIn search portfolio.
# Indeed does not share LinkedIn's location and work-model filters.
# A keyword match or "remote" search is not proof of Spain hiring eligibility.
$Searches = [ordered]@{
    "app-remote" = @{
        Keywords = "Application Support Engineer remoto"
        Location = "España"
        Description = "Application support, Spain-wide remote discovery"
    }
    "technical-remote" = @{
        Keywords = "Technical Support Engineer remoto"
        Location = "España"
        Description = "Technical support, Spain-wide remote discovery"
    }
    "operations-remote" = @{
        Keywords = "IT Operations remoto"
        Location = "España"
        Description = "IT operations, Spain-wide remote discovery"
    }
    "systems-remote" = @{
        Keywords = "Windows System Administrator remoto"
        Location = "España"
        Description = "Windows administration, Spain-wide remote discovery"
    }
    "support-local" = @{
        Keywords = "Técnico de Soporte IT"
        Location = "Vigo, Pontevedra"
        Description = "Local support, all workplace modes"
    }
    "systems-local" = @{
        Keywords = "Administrador de Sistemas"
        Location = "Vigo, Pontevedra"
        Description = "Local administration, all workplace modes"
    }
}

if ($List) {
    foreach ($key in $Searches.Keys) {
        [pscustomobject]@{
            Search = $key
            Keywords = $Searches[$key].Keywords
            Location = $Searches[$key].Location
            Description = $Searches[$key].Description
        }
    }
    return
}

$Definition = $Searches[$Search]
$Query = [System.Uri]::EscapeDataString($Definition.Keywords)
$Location = [System.Uri]::EscapeDataString($Definition.Location)
if ($SearchUrl) {
    $Parsed = $null
    if (-not [System.Uri]::TryCreate($SearchUrl, [System.UriKind]::Absolute, [ref]$Parsed) -or
        $Parsed.Scheme -ne "https" -or
        $Parsed.Host -notin @("es.indeed.com", "www.indeed.com", "indeed.com") -or
        $Parsed.AbsolutePath -ne "/jobs") {
        throw "SearchUrl must be an HTTPS Indeed /jobs search URL."
    }
    Write-Host "Using user-selected Indeed filters from the search page URL."
} else {
    $SearchUrl = "https://es.indeed.com/jobs?q=$Query&l=$Location&fromage=$Days"
    if ($Sort -eq "date") {
        $SearchUrl += "&sort=date"
    }
    if ($RadiusKm -gt 0) {
        $SearchUrl += "&radius=$RadiusKm"
    }
}

$Runner = Join-Path $PSScriptRoot "run-indeed-chrome-capture.ps1"
if (-not (Test-Path -LiteralPath $Runner)) {
    throw "Indeed supervised capture runner not found: $Runner"
}

Write-Host "Indeed curated search: $Search"
if (-not $SearchUrl) { throw "Search URL was not generated." }
Write-Host "Preset terms: $($Definition.Keywords)"
Write-Host "Preset location: $($Definition.Location)"
Write-Host "Effective search: $SearchUrl"
Write-Host "Opening supervised Indeed capture (one search per invocation)."
Write-Host "Confirm work location and remote eligibility from verified job details."

$Arguments = @{
    SearchUrl = $SearchUrl
    MaxJobs = $MaxJobs
    MaxPages = $MaxPages
    SkipSync = -not $SyncDependencies
}
& $Runner @Arguments
if (-not $?) {
    throw "Indeed supervised capture runner failed."
}
