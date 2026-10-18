[CmdletBinding()]
param(
    [ValidateSet("all", "app-title", "app-broad", "support-title", "support-broad", "systems-title", "systems-broad")]
    [string]$Search = "all",
    [ValidateRange(1, 100)][int]$MaxJobs = 15,
    [ValidateRange(1, 10)][int]$MaxPages = 2,
    [string]$OutputDirectory = "",
    [switch]$List,
    [switch]$ContinueOnError,
    [switch]$SyncDependencies
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Independent pilot. Never edits JOLT saved searches, review decisions, or applications.
# Compare title-only vs broader terms with identical location, time range and result limits.
$Trials = [ordered]@{
    "app-title" = @{ Pair = "application-support"; Variant = "title"; Query = 'title:"Application Support"'; Location = "España" }
    "app-broad" = @{ Pair = "application-support"; Variant = "broad"; Query = '"application support" AND (SQL OR incident)'; Location = "España" }
    "support-title" = @{ Pair = "it-support"; Variant = "title"; Query = 'title:"IT Support"'; Location = "España" }
    "support-broad" = @{ Pair = "it-support"; Variant = "broad"; Query = '("IT Support" OR "Technical Support" OR "Helpdesk")'; Location = "España" }
    "systems-title" = @{ Pair = "systems"; Variant = "title"; Query = 'title:"Administrador de Sistemas"'; Location = "España" }
    "systems-broad" = @{ Pair = "systems"; Variant = "broad"; Query = '("Windows Server" OR "Microsoft 365") AND soporte'; Location = "España" }
}
if ($List) {
    foreach ($key in $Trials.Keys) {
        [pscustomobject]@{ Search = $key; Pair = $Trials[$key].Pair; Query = $Trials[$key].Query; Location = $Trials[$key].Location }
    }
    return
}

$Root = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $PSScriptRoot "run-indeed-chrome-capture.ps1"
$Analyzer = Join-Path $PSScriptRoot "analyze-indeed-search-benchmark.py"
if (-not (Test-Path -LiteralPath $Runner)) { throw "Missing Indeed capture runner: $Runner" }
if (-not (Test-Path -LiteralPath $Analyzer)) { throw "Missing Indeed benchmark analyzer: $Analyzer" }

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $HOME ("Downloads\JOLT_INDEED_AB_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$Selected = if ($Search -eq "all") { @($Trials.Keys) } else { @($Search) }
$Manifest = @()
$FirstRun = $true
foreach ($Name in $Selected) {
    $Definition = $Trials[$Name]
    $EncodedQuery = [uri]::EscapeDataString([string]$Definition.Query)
    $EncodedLocation = [uri]::EscapeDataString([string]$Definition.Location)
    $Url = "https://es.indeed.com/jobs?q=$EncodedQuery&l=$EncodedLocation&fromage=7&sort=date"
    $OutputZip = Join-Path $OutputDirectory "$Name.zip"
    $Started = (Get-Date).ToUniversalTime().ToString("o")
    $Status = "completed"
    $ErrorText = ""
    Write-Host ""
    Write-Host "=== Indeed A/B: $Name ($($Definition.Pair), $($Definition.Variant)) ==="
    Write-Host "Query: $($Definition.Query)"
    Write-Host "Location: $($Definition.Location) | $MaxJobs jobs | $MaxPages pages"
    Write-Host "Complete any Indeed/Cloudflare human verification in Chrome."
    try {
        $Arguments = @{
            SearchUrl = $Url
            MaxJobs = $MaxJobs
            MaxPages = $MaxPages
            OutputZip = $OutputZip
            SkipSync = (-not $SyncDependencies -or -not $FirstRun)
        }
        & $Runner @Arguments
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $OutputZip)) {
            throw "Capture failed or did not produce the expected ZIP."
        }
    } catch {
        $Status = "failed"
        $ErrorText = $_.Exception.Message
        Write-Warning "$Name failed: $ErrorText"
    }
    $FirstRun = $false
    $Manifest += [pscustomobject]@{
        search = $Name
        pair = $Definition.Pair
        variant = $Definition.Variant
        query = $Definition.Query
        location = $Definition.Location
        search_url = $Url
        status = $Status
        archive = if (Test-Path -LiteralPath $OutputZip) { "$Name.zip" } else { "" }
        started_at = $Started
        error = $ErrorText
    }
    $Manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputDirectory "manifest.json") -Encoding utf8
    if ($Status -eq "failed" -and -not $ContinueOnError) { break }
}
& python $Analyzer --directory $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw "Benchmark analyzer failed; raw evidence remains in $OutputDirectory." }
$Bundle = "$OutputDirectory.zip"
Compress-Archive -Path (Join-Path $OutputDirectory "*") -DestinationPath $Bundle -Force
Write-Host ""
Write-Host "A/B evidence: $Bundle"
Write-Host "Upload this ZIP for relevance and application-eligibility evaluation."
