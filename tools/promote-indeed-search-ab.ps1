[CmdletBinding()]
param(
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [switch]$Apply,
    [switch]$IncludeBroad,
    [ValidateRange(1,100)][int]$MaxJobs = 30,
    [ValidateRange(1,10)][int]$MaxPages = 3
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# These title queries returned 9 and 8 verified listings respectively in the
# October 18 A/B benchmark. The wider query returned 15, but had more noise.
# Adds saved searches; never edits/deletes pre-existing user searches.
$Selected = @(
    @{ Label = "Indeed | Application Support (title)"; Query = 'title:"Application Support"'; Source = "app-title" }
    @{ Label = "Indeed | IT Support (title)"; Query = 'title:"IT Support"'; Source = "support-title" }
)
if ($IncludeBroad) {
    $Selected += @{
        Label = "Indeed | IT Support (broad pilot)"
        Query = '("IT Support" OR "Technical Support" OR "Helpdesk")'
        Source = "support-broad"
    }
}

$Existing = @(Invoke-RestMethod -Uri "$ApiUrl/api/discovery-searches?source=indeed" -Method Get -TimeoutSec 10)
$Created = @()
$Skipped = @()
foreach ($Trial in $Selected) {
    $Encoded = [uri]::EscapeDataString($Trial.Query)
    $Location = [uri]::EscapeDataString("España")
    $SearchUrl = "https://es.indeed.com/jobs?q=$Encoded&l=$Location&fromage=7&sort=date"
    $match = @($Existing | Where-Object {
        $_.definition.search_url -eq $SearchUrl -or $_.label -eq $Trial.Label
    })
    if ($match.Count -gt 0) {
        Write-Host "EXISTS: $($Trial.Label) (no changes)"
        $Skipped += $Trial.Label
        continue
    }
    $Payload = @{
        source = "indeed"
        label = $Trial.Label
        definition = @{ search_url = $SearchUrl; max_pages = $MaxPages }
        max_jobs = $MaxJobs
        enabled = $true
        notes = "Promoted from 2026-10-18 Indeed A/B pilot ($($Trial.Source)). Location and remote eligibility must be checked from full job text."
    }
    if (-not $Apply) {
        Write-Host "DRY RUN: would add $($Trial.Label)"
        Write-Host "  $SearchUrl"
        continue
    }
    $Entry = Invoke-RestMethod -Uri "$ApiUrl/api/discovery-searches" -Method Post -ContentType "application/json" -Body ($Payload | ConvertTo-Json -Depth 8) -TimeoutSec 20
    Write-Host "CREATED: $($Entry.label) / $($Entry.id)"
    $Existing += $Entry
    $Created += $Entry.label
}
Write-Host "Summary: created=$($Created.Count), existing=$($Skipped.Count)."
if (-not $Apply) { Write-Host "To create the missing searches, rerun with -Apply." }
