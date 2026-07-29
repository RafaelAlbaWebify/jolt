@echo off
setlocal EnableExtensions

set "REPO=%~dp0"
set "BACKEND_DIR=%REPO%backend"
set "FRONTEND_DIR=%REPO%frontend"
set "BACKEND_HELPER=%REPO%START_JOLT_BACKEND.cmd"
set "FRONTEND_HELPER=%REPO%START_JOLT_FRONTEND.cmd"
set "STATUS_HELPER=%REPO%tools\jolt-launcher-status.ps1"
set "BACKEND_URL=http://127.0.0.1:8000/api/health"
set "FRONTEND_URL=http://127.0.0.1:5173"
set "RUNTIME_IDENTITY_URL=http://127.0.0.1:8000/api/runtime-identity"

where powershell.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: powershell.exe was not found on PATH.
    pause
    exit /b 1
)

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

if not exist "%STATUS_HELPER%" (
    echo ERROR: Launcher status helper was not found at "%STATUS_HELPER%".
    pause
    exit /b 1
)

echo Checking current JOLT port owners and health...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%STATUS_HELPER%"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri '%BACKEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; $owner = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($owner) { exit 2 }; exit 1"
if errorlevel 2 (
    echo ERROR: Port 8000 is occupied, but JOLT backend health is not OK.
    echo Run STOP_JOLT.bat, then run START_JOLT.bat again.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%STATUS_HELPER%"
    pause
    exit /b 1
) else if errorlevel 1 (
    echo Starting JOLT backend...
    start "JOLT Backend" /min "%BACKEND_HELPER%"
) else (
    echo JOLT backend is already healthy.
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri '%FRONTEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } } catch {}; $owner = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($owner) { exit 2 }; exit 1"
if errorlevel 2 (
    echo ERROR: Port 5173 is occupied, but JOLT frontend is not reachable.
    echo Run STOP_JOLT.bat, then run START_JOLT.bat again.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%STATUS_HELPER%"
    pause
    exit /b 1
) else if errorlevel 1 (
    echo Starting JOLT frontend...
    start "JOLT Frontend" /min "%FRONTEND_HELPER%"
) else (
    echo JOLT frontend is already reachable.
)

echo Waiting for JOLT health checks...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$deadline = (Get-Date).AddSeconds(120); do { try { $backend = Invoke-WebRequest -Uri '%BACKEND_URL%' -UseBasicParsing -TimeoutSec 2; $frontend = Invoke-WebRequest -Uri '%FRONTEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($backend.StatusCode -eq 200 -and $frontend.StatusCode -ge 200 -and $frontend.StatusCode -lt 500) { exit 0 } } catch {}; Start-Sleep -Milliseconds 300 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo ERROR: JOLT did not become ready within 120 seconds.
    echo Current launcher status:
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%STATUS_HELPER%"
    echo Review the JOLT Backend and JOLT Frontend windows for details.
    pause
    exit /b 1
)

echo JOLT is ready.
echo Backend health: %BACKEND_URL%
echo Runtime identity: %RUNTIME_IDENTITY_URL%
echo Frontend: %FRONTEND_URL%
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%STATUS_HELPER%"

echo Opening JOLT...
start "" "%FRONTEND_URL%"
exit /b 0
