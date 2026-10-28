# Market Insights only; read-only database and bounded child process.
[CmdletBinding()]
param(
    [string]$Output = "$HOME/Downloads/JOLT_MARKET_PROFILE.zip",
    [ValidateRange(5,300)][int]$TimeoutSeconds = 90
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $root "backend")
try {
    & uv run --no-sync python ../tools/jolt_market_bottleneck.py --db data/jolt.db --output $Output --timeout $TimeoutSeconds
    if ($LASTEXITCODE -ne 0) { throw "Market diagnosis failed: $LASTEXITCODE" }
}
finally { Pop-Location }
