[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Staging = Join-Path $env:TEMP "JOLT_REVIEW_AUDIT_$Timestamp"
$OutputZip = Join-Path $Downloads "JOLT_REVIEW_AUDIT_$Timestamp.zip"
$SummaryPath = Join-Path $Staging "audit-summary.json"
$ProvenancePath = Join-Path $Staging "audit-provenance.json"
$AuditSnapshotZip = Join-Path $env:TEMP "JOLT_AUDIT_SNAPSHOT_$Timestamp.zip"

function Invoke-TextCommand {
    param(
        [Parameter(Mandatory)]
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = $RepoRoot
    )

    Push-Location $WorkingDirectory
    try {
        $output = & $FilePath @Arguments 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
        return $output.Trim()
    }
    catch {
        return $null
    }
    finally {
        Pop-Location
    }
}

New-Item -ItemType Directory -Force -Path $Staging, $Downloads | Out-Null

try {
    & (Join-Path $PSScriptRoot "start-jolt.ps1") -NoBrowser

    Push-Location $BackendRoot
    try {
        uv sync --all-groups
        if ($LASTEXITCODE -ne 0) { throw "Backend dependencies could not be prepared." }

        uv run playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium could not be installed." }

        $reviewAuditExitCode = 0
        uv run python -m jolt.review_audit --output-dir $Staging
        $reviewAuditExitCode = $LASTEXITCODE

        $captureAuditExitCode = 0
        uv run python -m jolt.capture_evidence_audit_cli --output-dir $Staging
        $captureAuditExitCode = $LASTEXITCODE

        $visualJourneyExitCode = 0
        uv run python -m jolt.playwright_visual_journey --output-dir $Staging
        $visualJourneyExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    $health = $null
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 15
    }
    catch {
        $health = [ordered]@{ error = $_.Exception.Message }
    }

    Remove-Item -LiteralPath $AuditSnapshotZip -Force -ErrorAction SilentlyContinue
    & (Join-Path $PSScriptRoot "backup-jolt.ps1") -OutputPath $AuditSnapshotZip

    Push-Location $BackendRoot
    try {
        $snapshotManifestJson = uv run python -m jolt.backup verify --backup $AuditSnapshotZip
        if ($LASTEXITCODE -ne 0) {
            throw "Audit database snapshot verification failed."
        }
    }
    finally {
        Pop-Location
    }

    $snapshotManifest = $snapshotManifestJson | ConvertFrom-Json
    if (
        [string]::IsNullOrWhiteSpace([string]$snapshotManifest.database_sha256) -or
        [int64]$snapshotManifest.database_size -lt 1 -or
        [string]::IsNullOrWhiteSpace([string]$snapshotManifest.alembic_revision)
    ) {
        throw "Audit database snapshot manifest is incomplete."
    }

    $databaseFiles = @(
        [ordered]@{
            relative_path = "backend\data\jolt.db"
            evidence_type = "consistent_sqlite_backup_snapshot"
            sha256 = [string]$snapshotManifest.database_sha256
            size_bytes = [int64]$snapshotManifest.database_size
            alembic_revision = [string]$snapshotManifest.alembic_revision
            source_file_read_directly = $false
            snapshot_archive_included = $false
        }
    )

    $gitStatus = Invoke-TextCommand -FilePath "git" -Arguments @("status", "--porcelain")
    $provenance = [ordered]@{
        generated_utc = (Get-Date).ToUniversalTime().ToString("o")
        repository = [ordered]@{
            commit = Invoke-TextCommand -FilePath "git" -Arguments @("rev-parse", "HEAD")
            branch = Invoke-TextCommand -FilePath "git" -Arguments @("branch", "--show-current")
            dirty = -not [string]::IsNullOrWhiteSpace($gitStatus)
            changed_paths = @(
                if (-not [string]::IsNullOrWhiteSpace($gitStatus)) {
                    $gitStatus -split "`r?`n"
                }
            )
        }
        application = [ordered]@{
            health = $health
            alembic_revision = [string]$snapshotManifest.alembic_revision
        }
        runtime = [ordered]@{
            operating_system = [System.Environment]::OSVersion.VersionString
            powershell = $PSVersionTable.PSVersion.ToString()
            git = Invoke-TextCommand -FilePath "git" -Arguments @("--version")
            uv = Invoke-TextCommand -FilePath "uv" -Arguments @("--version")
            python = Invoke-TextCommand -FilePath "uv" -Arguments @("run", "python", "--version") -WorkingDirectory $BackendRoot
            node = Invoke-TextCommand -FilePath "node" -Arguments @("--version")
            npm = Invoke-TextCommand -FilePath "npm.cmd" -Arguments @("--version")
        }
        databases = $databaseFiles
        privacy = [ordered]@{
            database_contents_included = $false
            absolute_user_paths_included = $false
            raw_capture_payloads_included = $false
        }
    }
    $provenance | ConvertTo-Json -Depth 8 | Set-Content -Path $ProvenancePath -Encoding UTF8

    if (Test-Path (Join-Path $RepoRoot ".jolt\logs")) {
        Copy-Item (Join-Path $RepoRoot ".jolt\logs") (Join-Path $Staging "service-logs") -Recurse
    }

    @(
        "JOLT automated review, capture evidence, and visual journey audit",
        "Generated: $((Get-Date).ToString('o'))",
        "",
        "Review audit-summary.json, capture-audit-summary.json, capture-details.json, playwright-journey.json, audit-provenance.json, opportunities.json, readiness-histories.json, and screenshots\.",
        "The visual journey records reviewer-like scrolling, expandable-panel inspection, accessible-control discovery, browser console messages, page errors, and named screenshots.",
        "Database contents, raw capture payloads, and absolute user paths are not included.",
        "No readiness recalculation, application, capture, or recruiter action was performed."
    ) | Set-Content -Path (Join-Path $Staging "README.txt") -Encoding UTF8

    Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $OutputZip -Force
    Write-Host "Review audit package created: $OutputZip"

    if (
        $reviewAuditExitCode -ne 0 -or
        $captureAuditExitCode -ne 0 -or
        $visualJourneyExitCode -ne 0
    ) {
        throw "The audit found one or more errors. Review the ZIP created in Downloads."
    }
}
finally {
    & (Join-Path $PSScriptRoot "stop-jolt.ps1") -ErrorAction SilentlyContinue
    Remove-Item $Staging -Recurse -Force -ErrorAction SilentlyContinue
}
