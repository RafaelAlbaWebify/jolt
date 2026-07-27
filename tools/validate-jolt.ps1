[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot "backend"
$RuntimeRoot = Join-Path $RepoRoot ".jolt"
$LogRoot = Join-Path $RuntimeRoot "logs"
$StatePath = Join-Path $RuntimeRoot "services.json"
$DatabasePath = Join-Path $BackendRoot "data\jolt.db"
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Staging = Join-Path $env:TEMP "JOLT_VALIDATION_$Timestamp"
$OutputZip = Join-Path $Downloads "JOLT_WINDOWS_VALIDATION_$Timestamp.zip"

function Invoke-CapturedCommand {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter()][string[]]$ArgumentList = @(),
        [Parameter()][string]$WorkingDirectory = $RepoRoot
    )

    Push-Location $WorkingDirectory
    try {
        $output = & $FilePath @ArgumentList 2>&1 | Out-String
        return [ordered]@{
            exit_code = $LASTEXITCODE
            output = $output.Trim()
        }
    }
    catch {
        return [ordered]@{
            exit_code = -1
            output = $_.Exception.Message
        }
    }
    finally {
        Pop-Location
    }
}

function Get-EndpointResult {
    param(
        [Parameter(Mandatory)][string]$Url,
        [switch]$IncludeBody
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        $result = [ordered]@{
            status = "reachable"
            http_status = $response.StatusCode
            url = $Url
        }
        if ($IncludeBody) {
            $result.body = $response.Content
        }
        return $result
    }
    catch {
        return [ordered]@{
            status = "unreachable"
            url = $Url
            error = $_.Exception.Message
        }
    }
}

New-Item -ItemType Directory -Force -Path $Staging, $Downloads | Out-Null

try {
    $gitHead = Invoke-CapturedCommand -FilePath "git" -ArgumentList @("rev-parse", "HEAD")
    $gitBranch = Invoke-CapturedCommand -FilePath "git" -ArgumentList @("branch", "--show-current")
    $gitStatus = Invoke-CapturedCommand -FilePath "git" -ArgumentList @("status", "--porcelain=v1", "--branch")
    $gitRemote = Invoke-CapturedCommand -FilePath "git" -ArgumentList @("remote", "get-url", "origin")
    $alembicCurrent = Invoke-CapturedCommand -FilePath "uv" -ArgumentList @("run", "alembic", "current") -WorkingDirectory $BackendRoot
    $alembicHeads = Invoke-CapturedCommand -FilePath "uv" -ArgumentList @("run", "alembic", "heads") -WorkingDirectory $BackendRoot

    $results = [ordered]@{
        generated_at = (Get-Date).ToString("o")
        computer_name = $env:COMPUTERNAME
        windows_user = $env:USERNAME
        repository = $RepoRoot
        git = [ordered]@{
            head = $gitHead
            branch = $gitBranch
            status = $gitStatus
            origin = $gitRemote
            clean_worktree = ($gitStatus.exit_code -eq 0 -and (($gitStatus.output -split "`r?`n").Count -le 1))
        }
        migrations = [ordered]@{
            current = $alembicCurrent
            heads = $alembicHeads
            at_head = (
                $alembicCurrent.exit_code -eq 0 -and
                $alembicHeads.exit_code -eq 0 -and
                $alembicCurrent.output -match [regex]::Escape(($alembicHeads.output -split "\s+")[0])
            )
        }
        state_file_present = Test-Path $StatePath
        backend = Get-EndpointResult -Url "http://127.0.0.1:8000/api/health" -IncludeBody
        frontend = Get-EndpointResult -Url "http://127.0.0.1:5173"
        commands = [ordered]@{}
        recorded_processes = [ordered]@{}
        database = [ordered]@{
            path = $DatabasePath
            present = Test-Path $DatabasePath
        }
    }

    foreach ($command in @("uv", "node", "npm", "git")) {
        $resolved = Get-Command $command -ErrorAction SilentlyContinue
        $results.commands[$command] = if ($null -eq $resolved) { "missing" } else { $resolved.Source }
    }

    if (Test-Path $DatabasePath) {
        $database = Get-Item $DatabasePath
        $results.database.size_bytes = $database.Length
        $results.database.last_write_time = $database.LastWriteTime.ToString("o")
        $results.database.sha256 = (Get-FileHash -Path $DatabasePath -Algorithm SHA256).Hash
    }

    if (Test-Path $StatePath) {
        Copy-Item $StatePath (Join-Path $Staging "services.json")
        $state = Get-Content -Path $StatePath -Raw | ConvertFrom-Json
        foreach ($service in @(
            @{ Name = "backend"; Property = "backend_pid" },
            @{ Name = "frontend"; Property = "frontend_pid" }
        )) {
            $property = $state.PSObject.Properties[$service.Property]
            if ($null -eq $property) {
                $results.recorded_processes[$service.Name] = [ordered]@{ recorded = $false }
                continue
            }
            $processId = [int]$property.Value
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            $results.recorded_processes[$service.Name] = [ordered]@{
                recorded = $true
                pid = $processId
                running = $null -ne $process
                process_name = if ($null -eq $process) { $null } else { $process.ProcessName }
            }
        }
    }

    if (Test-Path $LogRoot) {
        Copy-Item $LogRoot (Join-Path $Staging "logs") -Recurse
    }

    $results | ConvertTo-Json -Depth 8 | Set-Content `
        -Path (Join-Path $Staging "validation_summary.json") `
        -Encoding UTF8

    @(
        "JOLT Windows release certification",
        "Generated: $($results.generated_at)",
        "Git head: $($results.git.head.output)",
        "Git branch: $($results.git.branch.output)",
        "Clean worktree: $($results.git.clean_worktree)",
        "Migrations at head: $($results.migrations.at_head)",
        "Backend: $($results.backend.status)",
        "Frontend: $($results.frontend.status)",
        "Database present: $($results.database.present)",
        "",
        "Before sharing this package, review validation_summary.json and logs for private data.",
        "For supervised LinkedIn validation, also include the separate JOLT_LINKEDIN_CAPTURE_<timestamp>.zip package."
    ) | Set-Content -Path (Join-Path $Staging "README.txt") -Encoding UTF8

    @(
        "Manual browser certification checklist",
        "",
        "[ ] JOLT opens at http://127.0.0.1:5173 without a blank screen.",
        "[ ] Existing opportunities and applications survive restart.",
        "[ ] Contact and document edits survive reload and appear in Timeline.",
        "[ ] A bounded supervised LinkedIn capture (MaxJobs 3) completes.",
        "[ ] Capture history shows accepted/rejected counts and inspection details.",
        "[ ] No rejected LinkedIn item is ingested as an opportunity.",
        "[ ] Stop and restart preserve the database and restore healthy services.",
        "",
        "Record PASS/FAIL and any notes below before uploading the ZIP."
    ) | Set-Content -Path (Join-Path $Staging "MANUAL_CHECKLIST.txt") -Encoding UTF8

    Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $OutputZip -Force
    Write-Host "Validation package created: $OutputZip"
}
finally {
    Remove-Item $Staging -Recurse -Force -ErrorAction SilentlyContinue
}
