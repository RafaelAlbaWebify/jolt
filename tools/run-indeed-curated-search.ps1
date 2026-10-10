[CmdletBinding()]
param(
    [ValidateSet("app-remote", "technical-remote", "operations-remote", "systems-remote", "support-local", "systems-local")]
    [string]$Search = "app-remote",
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
        Keywords = ""application support" OR "production support" OR "soporte de aplicaciones""
        Location = "España"
        Description = "Application support, Spain-wide remote discovery"
    }
    "technical-remote" = @{
        Keywords = ""technical support engineer" OR "IT support engineer" OR "service desk""
        Location = "España"
        Description = "Technical support, Spain-wide remote discovery"
    }
    "operations-remote" = @{
        Keywords = ""IT operations" OR "infrastructure operations" OR "IT operations analyst""
        Location = "España"
        Description = "IT operations, Spain-wide remote discovery"
    }
    "systems-remote" = @{
        Keywords = ""Windows Server" OR "Microsoft Intune" OR "Microsoft 365 administrator""
        Location = "España"
        Description = "Windows administration, Spain-wide remote discovery"
    }
    "support-local" = @{
        Keywords = ""soporte informático" OR "técnico de sistemas" OR "help desk""
        Location = "Vigo, Pontevedra"
        Description = "Local support, all workplace modes"
    }
    "systems-local" = @{
        Keywords = ""administrador de sistemas" OR "system administrator" OR "técnico de sistemas""
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
$SearchUrl = "https://es.indeed.com/jobs?q=$Query&l=$Location&fromage=7&sort=date"

$Runner = Join-Path $PSScriptRoot "run-indeed-chrome-capture.ps1"
if (-not (Test-Path -LiteralPath $Runner)) {
    throw "Indeed supervised capture runner not found: $Runner"
}

Write-Host "Indeed curated search: $Search"
Write-Host "Terms: $($Definition.Keywords)"
Write-Host "Location: $($Definition.Location)"
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
