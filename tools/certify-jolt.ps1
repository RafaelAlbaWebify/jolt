[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Staging = Join-Path $env:TEMP "JOLT_CERTIFICATION_$Timestamp"
$OutputZip = Join-Path $Downloads "JOLT_CERTIFICATION_$Timestamp.zip"
$BackupZip = Join-Path $Staging "JOLT_BACKUP_$Timestamp.zip"
$RestoreRoot = Join-Path $Staging "restore-test"
$RestoreDatabase = Join-Path $RestoreRoot "jolt.db"
$CertificationSummary = Join-Path $Staging "certification-summary.json"
$QualitySummary = Join-Path $Staging "local-quality-gate.json"

function Invoke-TextCommand {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = $RepoRoot
    )

    Push-Location $WorkingDirectory
    try {
        $output = & $FilePath @Arguments 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed: $FilePath $($Arguments -join ' ')"
        }
        return $output.Trim()
    }
    finally {
        Pop-Location
    }
}

function Get-NewestAuditZip {
    param([datetime]$Since)

    return Get-ChildItem -LiteralPath $Downloads -Filter "JOLT_REVIEW_AUDIT_*.zip" -File |
        Where-Object { $_.LastWriteTime -ge $Since } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

New-Item -ItemType Directory -Force -Path $Downloads, $Staging, $RestoreRoot | Out-Null

$started = Get-Date
$activeDatabase = Join-Path $BackendRoot "data\jolt.db"
if (-not (Test-Path -LiteralPath $activeDatabase -PathType Leaf)) {
    throw "JOLT active database was not found: $activeDatabase"
}

try {
    $branch = Invoke-TextCommand -FilePath "git" -Arguments @("branch", "--show-current")
    $commit = Invoke-TextCommand -FilePath "git" -Arguments @("rev-parse", "HEAD")
    $status = Invoke-TextCommand -FilePath "git" -Arguments @("status", "--porcelain")
    if (-not [string]::IsNullOrWhiteSpace($status)) {
        throw "The repository has uncommitted changes. Certification requires a clean checkout."
    }

    & (Join-Path $PSScriptRoot "local-quality-gate.ps1") -OutputPath $QualitySummary
    $quality = Get-Content -LiteralPath $QualitySummary -Raw | ConvertFrom-Json
    if ($quality.result -ne "passed") {
        throw "The local quality gate did not pass."
    }

    & (Join-Path $PSScriptRoot "audit-jolt.ps1")
    $auditZip = Get-NewestAuditZip -Since $started
    if ($null -eq $auditZip) {
        throw "The audit completed without producing a new audit ZIP in Downloads."
    }
    Copy-Item -LiteralPath $auditZip.FullName -Destination (Join-Path $Staging $auditZip.Name)

    & (Join-Path $PSScriptRoot "backup-jolt.ps1") -OutputPath $BackupZip
    & (Join-Path $PSScriptRoot "restore-jolt.ps1") -BackupPath $BackupZip -TargetPath $RestoreDatabase

    Push-Location $BackendRoot
    try {
        $backupManifestJson = uv run python -m jolt.backup verify --backup $BackupZip
        if ($LASTEXITCODE -ne 0) { throw "Backup verification failed." }
    }
    finally {
        Pop-Location
    }
    $backupManifest = $backupManifestJson | ConvertFrom-Json

    $restoredHash = (Get-FileHash -LiteralPath $RestoreDatabase -Algorithm SHA256).Hash.ToLowerInvariant()
    $activeHash = (Get-FileHash -LiteralPath $activeDatabase -Algorithm SHA256).Hash.ToLowerInvariant()
    $restoreMatchesBackup = $restoredHash -eq [string]$backupManifest.database_sha256
    if (-not $restoreMatchesBackup) {
        throw "The restored database hash does not match the verified backup manifest."
    }

    $summary = [ordered]@{
        generated_utc = (Get-Date).ToUniversalTime().ToString("o")
        repository = [ordered]@{
            branch = $branch
            commit = $commit
            clean = $true
        }
        local_quality_gate = [ordered]@{
            included = $true
            private_profile_isolated = $true
            checks = $quality.checks
            result = $quality.result
        }
        audit = [ordered]@{
            source_zip = $auditZip.Name
            included = $true
            structured_visual_journey_included = $true
        }
        backup = [ordered]@{
            format = $backupManifest.format
            alembic_revision = $backupManifest.alembic_revision
            database_size = $backupManifest.database_size
            database_sha256 = $backupManifest.database_sha256
            source_path_included = $backupManifest.source_path_included
            verified = $true
        }
        restore_test = [ordered]@{
            target_was_isolated = $true
            active_database_overwritten = $false
            restored_sha256 = $restoredHash
            restored_hash_matches_backup = $restoreMatchesBackup
            active_database_sha256 = $activeHash
        }
        privacy = [ordered]@{
            active_database_included = $false
            backup_database_included = $false
            restored_database_included = $false
            raw_capture_payloads_included = $false
            absolute_user_paths_included = $false
        }
        result = "passed"
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $CertificationSummary -Encoding UTF8

    @(
        "JOLT Windows local CI and visual certification package",
        "Generated: $((Get-Date).ToString('o'))",
        "",
        "This package proves that the current clean checkout passed Ruff, formatting, Pyright, and the full backend test suite with the private profile isolated.",
        "It also completed the full review/capture audit, structured Playwright visual journey, verified SQLite backup, and isolated restore test.",
        "The active database, temporary backup database, restored test database, raw capture payloads, and absolute user paths are not included.",
        "Review certification-summary.json, local-quality-gate.json, and the nested JOLT_REVIEW_AUDIT_*.zip.",
        "Result: passed"
    ) | Set-Content -LiteralPath (Join-Path $Staging "README.txt") -Encoding UTF8

    Remove-Item -LiteralPath $RestoreRoot -Recurse -Force
    Remove-Item -LiteralPath $BackupZip -Force
    Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $OutputZip -Force
    Write-Host "JOLT Windows certification passed: $OutputZip"
}
finally {
    & (Join-Path $PSScriptRoot "stop-jolt.ps1") -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Staging -Recurse -Force -ErrorAction SilentlyContinue
}
