[CmdletBinding()]
param(
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [switch]$Apply,
    [ValidateSet("indeed","linkedin")][string]$Portal = "indeed"
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Bilingual candidate audit. DRY RUN by default. -Apply only adds searches
# disabled; it does not delete, change, or run the active production portfolio.
$Pairs = @(
    @("IT","Application Support ES","soporte de aplicaciones","Spain"),
    @("IT","IT Specialist ES","técnico informático","Local"),
    @("IT","Technical Support ES","ingeniero de soporte técnico","Spain"),
    @("IT","Service Desk ES","mesa de ayuda","Local"),
    @("IT","IT Support ES","soporte informático","Local"),
    @("IT","IT Operations ES","operaciones IT","Spain"),
    @("IT","MES Support ES","soporte MES","Spain"),
    @("IT","Manufacturing IT ES","informática industrial","Local"),
    @("Transferable","Administrative Assistant EN","administrative assistant","Local"),
    @("Transferable","Back Office ES","administrativo back office","Local"),
    @("Transferable","Customer Support EN","customer support","Local"),
    @("Transferable","Call Center EN","call center agent","Local"),
    @("Transferable","Logistics Administrator EN","logistics administrator","Local"),
    @("Transferable","Data Entry ES","entrada de datos","Spain"),
    @("Transferable","Customer Service ES","servicio al cliente","Spain"),
    @("Transferable","Receptionist EN","receptionist","Local")
)
if ($Portal -eq "indeed") {
    $Uri = "$ApiUrl/api/discovery-searches?source=indeed"
} else {
    $Uri = "$ApiUrl/api/linkedin-searches"
}
$Existing = @(Invoke-RestMethod $Uri -TimeoutSec 15 | ForEach-Object { $_ })
$Added = 0
foreach ($Row in $Pairs) {
    $Family,$Name,$Keyword,$Scope = $Row
    $Location = if ($Scope -eq "Local") {"Vigo, Pontevedra"} else {"España"}
    $Encoded = [uri]::EscapeDataString($Keyword)
    if ($Portal -eq "indeed") {
        $Url = "https://es.indeed.com/jobs?q=$Encoded&l=$([uri]::EscapeDataString($Location))"
        if ($Scope -eq "Local") { $Url += "&radius=30" }
        $Url += "&sort=date"
        $Label = "Indeed | Bilingual test | $Family | $Name"
        $Found = @($Existing | Where-Object { $_.definition.search_url -eq $Url })
    } else {
        $GeoId = if ($Scope -eq "Local") {"90009802"} else {"105646813"}
        $Url = "https://www.linkedin.com/jobs/search/?keywords=$Encoded&geoId=$GeoId&f_TPR=r604800&sortBy=DD"
        if ($Scope -ne "Local") { $Url += "&f_WT=2" }
        $Label = "EXP BILINGUAL | $Family | $Name"
        $Found = @($Existing | Where-Object { $_.search_url -eq $Url })
    }
    if ($Found.Count -gt 0) { Write-Host "EXISTS: $Label"; continue }
    Write-Host "CANDIDATE: $Label : $Url"
    if (-not $Apply) { continue }
    if ($Portal -eq "indeed") {
        $Payload = @{
            source = "indeed"; label = $Label; enabled = $false; max_jobs = 10
            definition = @{ search_url = $Url; max_pages = 3 }
            notes = "Bilingual pilot candidate. Disabled; not approved production portfolio."
        }
        $Endpoint = "$ApiUrl/api/discovery-searches"
    } else {
        $Payload = @{
            label = $Label; search_url = $Url; enabled = $false; max_jobs = 10
            max_pages = 3; notes = "Bilingual pilot candidate. Disabled; not approved production portfolio."
        }
        $Endpoint = "$ApiUrl/api/linkedin-searches"
    }
    $Saved = Invoke-RestMethod -Uri $Endpoint -Method Post -ContentType "application/json" -Body ($Payload | ConvertTo-Json -Depth 8) -TimeoutSec 20
    $Existing += $Saved
    $Added++
}
Write-Host "Bilingual candidates total=$($Pairs.Count); created=$Added; portal=$Portal"
if (-not $Apply) { Write-Host "DRY RUN: no changes. -Apply saves disabled candidates." }
