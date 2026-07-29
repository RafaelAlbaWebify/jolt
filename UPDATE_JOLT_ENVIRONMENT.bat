@echo off
setlocal EnableExtensions

set "REPO=%~dp0"
set "BACKEND_DIR=%REPO%backend"
set "FRONTEND_DIR=%REPO%frontend"

where uv.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: uv.exe was not found on PATH.
    pause
    exit /b 1
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm.cmd was not found on PATH.
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

echo This script intentionally mutates the local JOLT environment.
echo It may install/update dependencies and apply database migrations.
echo Use START_JOLT.bat for normal start-only launches.
echo.

cd /d "%BACKEND_DIR%"
if errorlevel 1 (
    echo ERROR: Could not enter backend directory: "%BACKEND_DIR%"
    pause
    exit /b 1
)

echo Synchronizing JOLT backend dependencies...
uv.exe sync
if errorlevel 1 (
    echo ERROR: Backend dependency synchronization failed.
    pause
    exit /b 1
)

echo Applying JOLT database migrations...
uv.exe run alembic upgrade head
if errorlevel 1 (
    echo ERROR: Database migration failed.
    pause
    exit /b 1
)

cd /d "%FRONTEND_DIR%"
if errorlevel 1 (
    echo ERROR: Could not enter frontend directory: "%FRONTEND_DIR%".
    pause
    exit /b 1
)

echo Installing/updating frontend dependencies...
npm.cmd install
if errorlevel 1 (
    echo ERROR: Frontend dependency installation failed.
    pause
    exit /b 1
)

echo.
echo JOLT environment update completed successfully.
pause
exit /b 0
