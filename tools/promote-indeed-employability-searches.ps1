[CmdletBinding()]
param(
    [string]$ApiUrl = "http://127.0.0.1:8018",
    [switch]$Apply,
    [ValidateRange(1,100)][int]$MaxJobs = 20,
    [ValidateRange(1,10)][int]$MaxPages = 5
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Explicitly bounded, opt-in creation of saved searches. Does not launch capture.
# Existing definitions/human decisions/applications are never modified.
$Entries = @(
    @{ Family = "it"; Label = "Application Support Analyst"; Query = "Application Support Analyst"; Evidence = "pilot-tested" }
    @{ Family = "it"; Label = "IT Specialist"; Query = "IT Specialist"; Evidence = "pilot-tested" }
    @{ Family = "it"; Label = "Technical Support Engineer"; Query = "Technical Support Engineer"; Evidence = "pilot-tested" }
    @{ Family = "it"; Label = "IT Operations Analyst"; Query = "IT Operations Analyst"; Evidence = "pilot-tested" }
    @{ Family = "it"; Label = "Service Desk"; Query = "Service Desk"; Evidence = "hypothesis" }
    @{ Family = "it"; Label = "IT Support"; Query = "IT Support"; Evidence = "pilot-tested" }
    @{ Family = "bridge"; Label = "MES Support"; Query = "MES Support"; Evidence = "pilot-tested" }
    @{ Family = "bridge"; Label = "Manufacturing IT"; Query = "Manufacturing IT"; Evidence = "pilot-tested" }
    @{ Family = "transferable"; Label = "Auxiliar administrativo"; Query = "auxiliar administrativo"; Evidence = "untested" }
    @{ Family = "transferable"; Label = "Back Office"; Query = "back office"; Evidence = "untested" }
    @{ Family = "transferable"; Label = "Atención al cliente"; Query = "atención al cliente"; Evidence = "untested" }
    @{ Family = "transferable"; Label = "Teleoperador"; Query = "teleoperador"; Evidence = "untested" }
    @{ Family = "transferable"; Label = "Customer Service"; Query = "customer service"; Evidence = "untested" }
    @{ Family = "transferable"; Label = "Administrativo logística"; Query = "administrativo logística"; Evidence = "untested" }
    @{ Family = "transferable"; Label = "Gestión pedidos"; Query = "gestión de pedidos"; Evidence = "untested" }
    @{ Family = "transferable"; Label = "Data Entry"; Query = "data entry"; Evidence = "untested" }
    @{ Family = "transferable"; Label = "Soporte comercial"; Query = "soporte comercial"; Evidence = "untested" }
    @{ Family = "transferable"; Label = "Recepcionista"; Query = "recepcionista"; Evidence = "untested" }
)
$Current = @(Invoke-RestMethod -Uri "$ApiUrl/api/discovery-searches?source=indeed" -TimeoutSec 10)
$Created = 0
$Skipped = 0
foreach ($Item in $Entries) {
    $Encoded = [uri]::EscapeDataString($Item.Query)
    $Url = "https://es.indeed.com/jobs?q=$Encoded&l=Espa%C3%B1a&sort=date"
    $Label = "Indeed | $($Item.Family) | $($Item.Label)"
    $Matches = @($Current | Where-Object { $_.definition.search_url -eq $Url -or $_.label -eq $Label })
    if ($Matches.Count -gt 0) {
        Write-Host "EXISTS: $Label"
        $Skipped++
        continue
    }
    Write-Host "PROPOSED [$($Item.Evidence)]: $Label"
    Write-Host "  $Url"
    if (-not $Apply) { continue }
    $Body = @{
        source = "indeed"
        label = $Label
        definition = @{ search_url = $Url; max_pages = $MaxPages }
        max_jobs = $MaxJobs
        enabled = $false
        notes = "2026-10-25 search portfolio; $($Item.Evidence). Disabled by default pending operator selection; verify actual job requirements and remote location."
    } | ConvertTo-Json -Depth 8
    $Saved = Invoke-RestMethod -Uri "$ApiUrl/api/discovery-searches" -Method Post -ContentType "application/json" -Body $Body -TimeoutSec 20
    $Current += $Saved
    $Created++
}
Write-Host "Summary: new=$Created already_existing=$Skipped proposed=$($Entries.Count)"
if (-not $Apply) { Write-Host "DRY RUN ONLY. Use -Apply for explicit creation (disabled by default)." }
