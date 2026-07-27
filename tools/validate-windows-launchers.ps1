$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$launcher = Get-Content -LiteralPath (Join-Path $RepoRoot "START_JOLT.bat") -Raw
$backend = Get-Content -LiteralPath (Join-Path $RepoRoot "START_JOLT_BACKEND.cmd") -Raw
$frontend = Get-Content -LiteralPath (Join-Path $RepoRoot "START_JOLT_FRONTEND.cmd") -Raw

$forbidden = @(
    'cmd.exe /k',
    'cd /d ""',
    '^&^&'
)
foreach ($pattern in $forbidden) {
    if ($launcher.Contains($pattern)) {
        throw "START_JOLT.bat still contains fragile nested command syntax: $pattern"
    }
}

$requiredLauncher = @(
    'START_JOLT_BACKEND.cmd',
    'START_JOLT_FRONTEND.cmd',
    'start "JOLT Backend" /min "%BACKEND_HELPER%"',
    'start "JOLT Frontend" /min "%FRONTEND_HELPER%"'
)
foreach ($pattern in $requiredLauncher) {
    if (-not $launcher.Contains($pattern)) {
        throw "START_JOLT.bat is missing required helper invocation: $pattern"
    }
}

$requiredBackend = @(
    'uv.exe sync',
    'uv.exe run alembic upgrade head',
    'uv.exe run python -m uvicorn jolt.main:app'
)
foreach ($pattern in $requiredBackend) {
    if (-not $backend.Contains($pattern)) {
        throw "START_JOLT_BACKEND.cmd is missing required command: $pattern"
    }
}

if (-not $frontend.Contains('npm.cmd run dev -- --host 127.0.0.1')) {
    throw "START_JOLT_FRONTEND.cmd is missing the Vite startup command."
}

Write-Host "Windows launcher contracts passed."
