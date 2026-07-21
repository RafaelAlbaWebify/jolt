[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Downloads = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE "Downloads"))
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$PackageName = "JOLT_OPPORTUNITY_EXPERIENCE_$Timestamp"
$Staging = [IO.Path]::GetFullPath((Join-Path $Downloads $PackageName))
$OutputZip = [IO.Path]::GetFullPath((Join-Path $Downloads "$PackageName.zip"))
$Succeeded = $false

if ([IO.Path]::GetDirectoryName($Staging) -ne $Downloads) {
    throw "Unsafe audit staging path: $Staging"
}
if ([IO.Path]::GetDirectoryName($OutputZip) -ne $Downloads) {
    throw "Unsafe audit ZIP path: $OutputZip"
}
if ([IO.Path]::GetFileName($Staging) -notlike "JOLT_OPPORTUNITY_EXPERIENCE_*") {
    throw "Unexpected audit staging directory name: $Staging"
}

Write-Host "[opportunity-audit] Repository: $RepoRoot"
Write-Host "[opportunity-audit] Evidence directory: $Staging"
Write-Host "[opportunity-audit] Final ZIP: $OutputZip"

New-Item -ItemType Directory -Force -Path $Staging, $Downloads | Out-Null

try {
    Write-Host "[opportunity-audit] Starting JOLT without opening another browser window."
    & (Join-Path $PSScriptRoot "start-jolt.ps1") -NoBrowser

    Push-Location $BackendRoot
    try {
        $env:PYTHONUNBUFFERED = "1"
        Write-Host "[opportunity-audit] Running search, sort, inspector, keyboard, and visual checks."
        & uv run python -u -m jolt.opportunity_experience_audit --output-dir $Staging
        if ($LASTEXITCODE -ne 0) {
            throw "Opportunity experience audit failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }

    @(
        "JOLT opportunity experience audit",
        "Generated: $((Get-Date).ToString('o'))",
        "Viewport: 1440x1000",
        "",
        "Review opportunity-experience-audit.json and screenshots.",
        "The journey validates default queue layout, search, title sorting, inspector content,",
        "horizontal overflow, inspector dimensions, page errors, and Escape-key close behavior."
    ) | Set-Content -Path (Join-Path $Staging "README.txt") -Encoding UTF8

    $AuditJson = Join-Path $Staging "opportunity-experience-audit.json"
    if (-not (Test-Path -LiteralPath $AuditJson -PathType Leaf)) {
        throw "Audit summary was not created: $AuditJson"
    }

    $Screenshots = @(Get-ChildItem -LiteralPath (Join-Path $Staging "screenshots") -Filter "*.png" -File)
    if ($Screenshots.Count -ne 4) {
        throw "Expected exactly four opportunity experience screenshots, found $($Screenshots.Count)."
    }

    Write-Host "[opportunity-audit] Packaging only the validated audit directory."
    Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $OutputZip -Force
    if (-not (Test-Path -LiteralPath $OutputZip -PathType Leaf)) {
        throw "Audit ZIP was not created: $OutputZip"
    }

    $Succeeded = $true
    Write-Host "[opportunity-audit] Opportunity experience audit created: $OutputZip"
}
finally {
    Write-Host "[opportunity-audit] Stopping JOLT services."
    & (Join-Path $PSScriptRoot "stop-jolt.ps1") -ErrorAction SilentlyContinue

    if ($Succeeded) {
        Remove-Item -LiteralPath $Staging -Recurse -Force -ErrorAction SilentlyContinue
    }
    elseif (Test-Path -LiteralPath $Staging) {
        Write-Warning "Audit did not complete. Partial evidence was preserved at: $Staging"
    }
}
