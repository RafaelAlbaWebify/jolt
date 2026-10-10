[CmdletBinding()]
param(
    [switch]$FullTests
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$Repo = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Repo "backend"
$Frontend = Join-Path $Repo "frontend"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required for backend preflight."
}
Push-Location $Backend
try {
    uv run --no-sync ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff lint failed." }
    uv run --no-sync ruff format --check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff formatting failed." }
    if ($FullTests) {
        uv run --no-sync pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }
    }
} finally {
    Pop-Location
}
if ($FullTests) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm is required for frontend preflight."
    }
    Push-Location $Frontend
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    } finally {
        Pop-Location
    }
}
Write-Host "Local JOLT preflight passed."
