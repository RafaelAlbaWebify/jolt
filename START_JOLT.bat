@echo off
setlocal EnableExtensions

set "REPO=%~dp0"
set "BACKEND_DIR=%REPO%backend"
set "FRONTEND_DIR=%REPO%frontend"
set "BACKEND_HELPER=%REPO%START_JOLT_BACKEND.cmd"
set "FRONTEND_HELPER=%REPO%START_JOLT_FRONTEND.cmd"
set "BACKEND_URL=http://127.0.0.1:8000/api/health"
set "FRONTEND_URL=http://127.0.0.1:5173"

where uv.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: uv.exe was not found on PATH.
    echo Install uv or open JOLT from the PowerShell environment where uv is available.
    pause
    exit /b 1
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm.cmd was not found on PATH.
    echo Install Node.js or open JOLT from the environment where npm is available.
    pause
    exit /b 1
)

if not exist "%BACKEND_DIR%\pyproject.toml" (
    echo ERROR: JOLT backend was not found at "%BACKEND_DIR%".
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo ERROR: JOLT frontend was not found at "%FRONTEND_DIR%".
    pause
    exit /b 1
)

if not exist "%BACKEND_HELPER%" (
    echo ERROR: Backend launcher helper was not found at "%BACKEND_HELPER%".
    pause
    exit /b 1
)

if not exist "%FRONTEND_HELPER%" (
    echo ERROR: Frontend launcher helper was not found at "%FRONTEND_HELPER%".
    pause
    exit /b 1
)

powershell.exe -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%BACKEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } } catch {}; exit 1"
if errorlevel 1 (
    echo Starting JOLT backend...
    start "JOLT Backend" /min "%BACKEND_HELPER%"
) else (
    echo JOLT backend is already running.
)

powershell.exe -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%FRONTEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } } catch {}; exit 1"
if errorlevel 1 (
    echo Starting JOLT frontend...
    start "JOLT Frontend" /min "%FRONTEND_HELPER%"
) else (
    echo JOLT frontend is already running.
)

echo Waiting for JOLT...
powershell.exe -NoProfile -Command "$deadline = (Get-Date).AddSeconds(120); do { try { $backend = Invoke-WebRequest -Uri '%BACKEND_URL%' -UseBasicParsing -TimeoutSec 2; $frontend = Invoke-WebRequest -Uri '%FRONTEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($backend.StatusCode -lt 500 -and $frontend.StatusCode -lt 500) { exit 0 } } catch {}; Start-Sleep -Milliseconds 300 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo ERROR: JOLT did not become ready within 120 seconds.
    echo Review the JOLT Backend and JOLT Frontend windows for details.
    pause
    exit /b 1
)

echo Opening JOLT...
start "" "%FRONTEND_URL%"
exit /b 0
