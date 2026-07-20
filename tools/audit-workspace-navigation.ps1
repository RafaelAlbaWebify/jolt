[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Downloads = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE "Downloads"))
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$PackageName = "JOLT_WORKSPACE_NAVIGATION_$Timestamp"
$Staging = [IO.Path]::GetFullPath((Join-Path $Downloads $PackageName))
$OutputZip = [IO.Path]::GetFullPath((Join-Path $Downloads "$PackageName.zip"))
$Succeeded = $false

if ([IO.Path]::GetDirectoryName($Staging) -ne $Downloads) {
    throw "Unsafe audit staging path: $Staging"
}
if ([IO.Path]::GetDirectoryName($OutputZip) -ne $Downloads) {
    throw "Unsafe audit ZIP path: $OutputZip"
}
if ([IO.Path]::GetFileName($Staging) -notlike "JOLT_WORKSPACE_NAVIGATION_*") {
    throw "Unexpected audit staging directory name: $Staging"
}

Write-Host "[workspace-audit] Repository: $RepoRoot"
Write-Host "[workspace-audit] Evidence directory: $Staging"
Write-Host "[workspace-audit] Final ZIP: $OutputZip"

New-Item -ItemType Directory -Force -Path $Staging, $Downloads | Out-Null

try {
    Write-Host "[workspace-audit] Starting JOLT without opening another browser window."
    & (Join-Path $PSScriptRoot "start-jolt.ps1") -NoBrowser

    Push-Location $BackendRoot
    try {
        $env:PYTHONUNBUFFERED = "1"
        Write-Host "[workspace-audit] Running populated workspace audit."
        & uv run python -u -m jolt.workspace_navigation_audit --output-dir $Staging
        if ($LASTEXITCODE -ne 0) {
            throw "Workspace navigation audit failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }

    @(
        "JOLT workspace navigation audit",
        "Generated: $((Get-Date).ToString('o'))",
        "Viewport: 1440x1000",
        "",
        "Review workspace-navigation-audit.json and workspace-screenshots.",
        "The package records visible button counts and bounded scroll positions per workspace view."
    ) | Set-Content -Path (Join-Path $Staging "README.txt") -Encoding UTF8

    $AuditJson = Join-Path $Staging "workspace-navigation-audit.json"
    if (-not (Test-Path -LiteralPath $AuditJson -PathType Leaf)) {
        throw "Audit summary was not created: $AuditJson"
    }

    $Screenshots = @(Get-ChildItem -LiteralPath (Join-Path $Staging "workspace-screenshots") -Filter "*.png" -File)
    if ($Screenshots.Count -ne 3) {
        throw "Expected exactly three workspace screenshots, found $($Screenshots.Count)."
    }

    Write-Host "[workspace-audit] Packaging only the validated audit directory."
    $PackageContents = Join-Path $Staging "*"
    Compress-Archive -Path $PackageContents -DestinationPath $OutputZip -Force
    if (-not (Test-Path -LiteralPath $OutputZip -PathType Leaf)) {
        throw "Audit ZIP was not created: $OutputZip"
    }

    $Succeeded = $true
    Write-Host "[workspace-audit] Workspace navigation audit created: $OutputZip"
}
finally {
    Write-Host "[workspace-audit] Stopping JOLT services."
    & (Join-Path $PSScriptRoot "stop-jolt.ps1") -ErrorAction SilentlyContinue

    if ($Succeeded) {
        Remove-Item -LiteralPath $Staging -Recurse -Force -ErrorAction SilentlyContinue
    }
    elseif (Test-Path -LiteralPath $Staging) {
        Write-Warning "Audit did not complete. Partial evidence was preserved at: $Staging"
    }
}
