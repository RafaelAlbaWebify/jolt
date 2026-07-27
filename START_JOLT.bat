@echo off
setlocal EnableExtensions

set "REPO=%~dp0"
set "BACKEND_DIR=%REPO%backend"
set "FRONTEND_DIR=%REPO%frontend"
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

powershell.exe -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%BACKEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } } catch {}; exit 1"
if errorlevel 1 (
    echo Starting JOLT backend...
    start "JOLT Backend" /min cmd.exe /k "cd /d ""%BACKEND_DIR%"" ^&^& uv.exe run uvicorn jolt.main:app --host 127.0.0.1 --port 8000"
) else (
    echo JOLT backend is already running.
)

powershell.exe -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%FRONTEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } } catch {}; exit 1"
if errorlevel 1 (
    echo Starting JOLT frontend...
    start "JOLT Frontend" /min cmd.exe /k "cd /d ""%FRONTEND_DIR%"" ^&^& npm.cmd run dev -- --host 127.0.0.1"
) else (
    echo JOLT frontend is already running.
)

echo Waiting for JOLT...
powershell.exe -NoProfile -Command "$deadline = (Get-Date).AddSeconds(60); do { try { $backend = Invoke-WebRequest -Uri '%BACKEND_URL%' -UseBasicParsing -TimeoutSec 2; $frontend = Invoke-WebRequest -Uri '%FRONTEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($backend.StatusCode -lt 500 -and $frontend.StatusCode -lt 500) { exit 0 } } catch {}; Start-Sleep -Milliseconds 300 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo ERROR: JOLT did not become ready within 60 seconds.
    echo Review the JOLT Backend and JOLT Frontend windows for details.
    pause
    exit /b 1
)

echo Opening JOLT...
start "" "%FRONTEND_URL%"
exit /b 0
