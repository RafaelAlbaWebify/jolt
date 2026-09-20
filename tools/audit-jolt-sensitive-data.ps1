[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$GitIgnorePath = Join-Path $RepoRoot ".gitignore"
$HomeDownloads = Join-Path $HOME "Downloads"

$Targets = @(
    [pscustomobject]@{
        name = "Primary SQLite data"
        path = (Join-Path $RepoRoot "backend\data")
        classification = "high"
    },
    [pscustomobject]@{
        name = "Local LinkedIn browser profile"
        path = (Join-Path $RepoRoot ".jolt\browser-profile")
        classification = "critical"
    },
    [pscustomobject]@{
        name = "LinkedIn command-center browser profile"
        path = (Join-Path $RepoRoot "backend\data\playwright\linkedin-command-center")
        classification = "critical"
    },
    [pscustomobject]@{
        name = "Acceptance artifacts"
        path = (Join-Path $HomeDownloads "JOLT_ACCEPTANCE")
        classification = "high"
    },
    [pscustomobject]@{
        name = "LinkedIn profile capture artifacts"
        path = (Join-Path $HomeDownloads "JOLT_LINKEDIN_CAPTURES")
        classification = "high"
    }
)

function Get-PathSummary {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return [pscustomobject]@{
            exists = $false
            file_count = 0
            size_bytes = 0
        }
    }

    $item = Get-Item -LiteralPath $Path
    if (-not $item.PSIsContainer) {
        return [pscustomobject]@{
            exists = $true
            file_count = 1
            size_bytes = [int64]$item.Length
        }
    }

    $files = @(Get-ChildItem -LiteralPath $Path -File -Recurse -Force -ErrorAction SilentlyContinue)
    $size = [int64]0
    foreach ($file in $files) {
        $size += [int64]$file.Length
    }

    return [pscustomobject]@{
        exists = $true
        file_count = $files.Count
        size_bytes = $size
    }
}

$ignoreText = if (Test-Path -LiteralPath $GitIgnorePath) {
    Get-Content -LiteralPath $GitIgnorePath -Raw
} else {
    ""
}

$requiredIgnoreRules = @(".jolt/", "data/", "backend/data/")
$ignoreChecks = foreach ($rule in $requiredIgnoreRules) {
    [pscustomobject]@{
        rule = $rule
        present = $ignoreText -split "\r?\n" -contains $rule
    }
}

$storage = foreach ($target in $Targets) {
    $summary = Get-PathSummary -Path $target.path
    [pscustomobject]@{
        name = $target.name
        classification = $target.classification
        path = $target.path
        exists = $summary.exists
        file_count = $summary.file_count
        size_bytes = $summary.size_bytes
    }
}

$downloadPatterns = @(
    "JOLT_LINKEDIN_CAPTURE_*.json",
    "JOLT_LINKEDIN_CAPTURE_*.zip",
    "JOLT_AI_WORK_PACKAGE*.json",
    "JOLT_AI_REVIEW_INPUT*.json",
    "JOLT_AI_REVIEW_INPUT*.zip"
)

$portableExports = @()
if (Test-Path -LiteralPath $HomeDownloads) {
    foreach ($pattern in $downloadPatterns) {
        foreach ($file in @(Get-ChildItem -LiteralPath $HomeDownloads -File -Filter $pattern -ErrorAction SilentlyContinue)) {
            $portableExports += [pscustomobject]@{
                name = $file.Name
                path = $file.FullName
                size_bytes = [int64]$file.Length
            }
        }
    }
}

$result = [ordered]@{
    audit_type = "jolt_sensitive_data_inventory"
    performed_at = (Get-Date).ToString("o")
    repo_root = $RepoRoot
    storage = $storage
    portable_exports = $portableExports
    gitignore = $ignoreChecks
    passed = -not ($ignoreChecks | Where-Object { -not $_.present })
    note = "Read-only inventory. No file contents were inspected and no files were modified or deleted."
}

$result | ConvertTo-Json -Depth 6
if (-not $result.passed) {
    throw "One or more required sensitive-data Git-ignore rules are missing."
}
