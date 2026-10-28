# Direct performance profiling; no backend HTTP or log file required.
[CmdletBinding()]
param(
    [string]$Database = "backend/data/jolt.db",
    [string]$Output = "$HOME/Downloads/JOLT_DIRECT_PROFILE.zip",
    [ValidateRange(10,300)][int]$TimeoutSeconds = 90
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    if (!(Test-Path -LiteralPath $Database -PathType Leaf)) {
        throw "Database not found: $Database"
    }
    Push-Location "backend"
    try {
        & uv run --no-sync python ../tools/jolt_direct_profile.py --db "../$Database" --output $Output --timeout $TimeoutSeconds
        if ($LASTEXITCODE -ne 0) { throw "Direct profiler exited with code $LASTEXITCODE" }
    }
    finally { Pop-Location }
}
finally { Pop-Location }
