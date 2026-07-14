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

function Get-RepositoryRelativePath {
    param([Parameter(Mandatory)][string]$Path)

    $repoUri = [System.Uri]::new(($RepoRoot.TrimEnd('\') + '\'))
    $pathUri = [System.Uri]::new($Path)
    return [System.Uri]::UnescapeDataString($repoUri.MakeRelativeUri($pathUri).ToString()).Replace('/', '\')
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

        $auditExitCode = 0
        uv run python -m jolt.review_audit --output-dir $Staging
        $auditExitCode = $LASTEXITCODE
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

    $databaseFiles = @(
        Get-ChildItem -Path (Join-Path $RepoRoot ".jolt") -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -in @(".db", ".sqlite", ".sqlite3") } |
            ForEach-Object {
                $hash = Get-FileHash -Path $_.FullName -Algorithm SHA256
                [ordered]@{
                    relative_path = Get-RepositoryRelativePath -Path $_.FullName
                    sha256 = $hash.Hash.ToLowerInvariant()
                    size_bytes = $_.Length
                    last_write_utc = $_.LastWriteTimeUtc.ToString("o")
                }
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
            alembic_revision = Invoke-TextCommand -FilePath "uv" -Arguments @("run", "alembic", "current") -WorkingDirectory $BackendRoot
        }
        runtime = [ordered]@{
            operating_system = [System.Environment]::OSVersion.VersionString
            powershell = $PSVersionTable.PSVersion.ToString()
            git = Invoke-TextCommand -FilePath "git" -Arguments @("--version")
            uv = Invoke-TextCommand -FilePath "uv" -Arguments @("--version")
            python = Invoke-TextCommand -FilePath "uv" -Arguments @("run", "python", "--version") -WorkingDirectory $BackendRoot
            node = Invoke-TextCommand -FilePath "node" -Arguments @("--version")
            npm = Invoke-TextCommand -FilePath "npm" -Arguments @("--version")
        }
        databases = $databaseFiles
        privacy = [ordered]@{
            database_contents_included = $false
            absolute_user_paths_included = $false
        }
    }
    $provenance | ConvertTo-Json -Depth 8 | Set-Content -Path $ProvenancePath -Encoding UTF8

    if (Test-Path (Join-Path $RepoRoot ".jolt\logs")) {
        Copy-Item (Join-Path $RepoRoot ".jolt\logs") (Join-Path $Staging "service-logs") -Recurse
    }

    @(
        "JOLT automated review audit",
        "Generated: $((Get-Date).ToString('o'))",
        "",
        "Review audit-summary.json, audit-provenance.json, opportunities.json, readiness-histories.json, workbench-full.png, and workbench-readiness-history.png.",
        "The provenance file records the exact commit, repository state, migration revision, runtime versions, and SHA-256 hashes of local database files.",
        "Database contents and absolute user paths are not included.",
        "The screenshots capture the local workbench and readiness-history panel.",
        "No readiness recalculation, application, or recruiter action was performed."
    ) | Set-Content -Path (Join-Path $Staging "README.txt") -Encoding UTF8

    Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $OutputZip -Force
    Write-Host "Review audit package created: $OutputZip"

    if ($auditExitCode -ne 0) {
        throw "The audit found one or more errors. Review the ZIP created in Downloads."
    }
}
finally {
    Remove-Item $Staging -Recurse -Force -ErrorAction SilentlyContinue
}
