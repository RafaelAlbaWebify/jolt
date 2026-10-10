[CmdletBinding()]
param(
    [ValidateRange(1, 100)][int]$MaxJobs = 30,
    [ValidateRange(1, 10)][int]$MaxPages = 5,
    [string]$OutputDirectory = "",
    [switch]$ContinueOnError
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $PSScriptRoot "run-indeed-curated-search.ps1"
$Analyzer = Join-Path $PSScriptRoot "analyze-indeed-search-benchmark.py"
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $env:USERPROFILE ("Downloads\JOLT_INDEED_BENCHMARK_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$Order = @(
    "app-remote", "technical-remote", "support-local",
    "systems-local", "operations-remote", "systems-remote"
)
$Manifest = @()
foreach ($Name in $Order) {
    $Started = Get-Date
    Write-Host "=== Indeed benchmark: $Name ==="
    $Before = @(Get-ChildItem -LiteralPath (Join-Path $env:USERPROFILE "Downloads") -Filter "JOLT_INDEED_CHROME_CAPTURE_*.zip" -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    $Message = ""
    $Status = "completed"
    try {
        & $Runner -Search $Name -MaxJobs $MaxJobs -MaxPages $MaxPages
        if (-not $?) { throw "Search runner failed." }
    } catch {
        $Status = "failed"
        $Message = $_.Exception.Message
        Write-Warning "$Name failed: $Message"
    }
    $After = @(Get-ChildItem -LiteralPath (Join-Path $env:USERPROFILE "Downloads") -Filter "JOLT_INDEED_CHROME_CAPTURE_*.zip" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
    $NewZip = $After | Where-Object { $_.FullName -notin $Before -and $_.LastWriteTime -ge $Started.AddSeconds(-3) } | Select-Object -First 1
    $TargetName = ""
    if ($null -ne $NewZip) {
        $TargetName = "$Name.zip"
        Copy-Item -LiteralPath $NewZip.FullName -Destination (Join-Path $OutputDirectory $TargetName) -Force
    } elseif ($Status -eq "completed") {
        $Status = "failed"
        $Message = "Capture produced no new ZIP."
    }
    $Manifest += [pscustomobject]@{
        search = $Name; status = $Status; archive = $TargetName
        started_at = $Started.ToString("o"); error = $Message
    }
    $Manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutputDirectory "manifest.json") -Encoding utf8
    if ($Status -eq "failed" -and -not $ContinueOnError) {
        Write-Warning "Stopping on failure. Completed runs remain in $OutputDirectory"
        break
    }
}
& python $Analyzer --directory $OutputDirectory
if ($LASTEXITCODE -ne 0) {
    throw "Benchmark analysis failed; capture ZIPs are retained in $OutputDirectory"
}
$Archive = "$OutputDirectory.zip"
Compress-Archive -Path (Join-Path $OutputDirectory "*") -DestinationPath $Archive -Force
Write-Host "Benchmark bundle: $Archive"
