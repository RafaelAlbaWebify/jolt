[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Staging = Join-Path $env:TEMP "JOLT_WORKSPACE_NAVIGATION_$Timestamp"
$OutputZip = Join-Path $Downloads "JOLT_WORKSPACE_NAVIGATION_$Timestamp.zip"

New-Item -ItemType Directory -Force -Path $Staging, $Downloads | Out-Null

try {
    & (Join-Path $PSScriptRoot "start-jolt.ps1") -NoBrowser

    Push-Location $BackendRoot
    try {
        uv run playwright install chromium
        if ($LASTEXITCODE -ne 0) {
            throw "Playwright Chromium could not be installed."
        }

        uv run python -m jolt.workspace_navigation_audit --output-dir $Staging
        if ($LASTEXITCODE -ne 0) {
            throw "Workspace navigation audit failed."
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

    Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $OutputZip -Force
    Write-Host "Workspace navigation audit created: $OutputZip"
}
finally {
    & (Join-Path $PSScriptRoot "stop-jolt.ps1") -ErrorAction SilentlyContinue
    Remove-Item $Staging -Recurse -Force -ErrorAction SilentlyContinue
}
