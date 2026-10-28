# Read-only runtime acceptance and benchmarking; never starts/stops JOLT.
[CmdletBinding()]
param(
    [string]$Output = "$HOME/Downloads/JOLT_RUNTIME_ACCEPTANCE.zip",
    [ValidateRange(1,10)][int]$Samples = 3
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    if (-not (Test-Path ".jolt/services.json" -PathType Leaf)) {
        throw "JOLT services.json missing. Start JOLT normally first, then rerun."
    }
    & python tools/jolt_runtime_probe.py --root $root --output $Output --samples $Samples
    if ($LASTEXITCODE -ne 0) { throw "Runtime probe failed with exit $LASTEXITCODE" }
    Get-Item -LiteralPath $Output | Select-Object FullName, Length, LastWriteTime
}
finally {
    Pop-Location
}
