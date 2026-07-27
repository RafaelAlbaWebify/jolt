@echo off
setlocal EnableExtensions

set "REPO=%~dp0"
set "BACKEND_DIR=%REPO%backend"

cd /d "%BACKEND_DIR%"
if errorlevel 1 (
    echo ERROR: Could not enter backend directory: "%BACKEND_DIR%"
    pause
    exit /b 1
)

echo Synchronizing JOLT backend...
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

echo Starting JOLT backend...
uv.exe run python -m uvicorn jolt.main:app --host 127.0.0.1 --port 8000
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo JOLT backend stopped with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
