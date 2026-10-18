[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Maintain the legacy operator entrypoint but delegate to the only shutdown
# implementation that validates PID/port ownership against this checkout.
& (Join-Path $PSScriptRoot "stop-jolt.ps1")
