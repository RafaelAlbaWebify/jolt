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

echo Starting JOLT backend without dependency sync or migrations.
echo To update dependencies or apply migrations intentionally, run UPDATE_JOLT_ENVIRONMENT.bat.
echo Backend directory: %CD%
echo Health URL: http://127.0.0.1:8000/api/health
echo Runtime identity URL: http://127.0.0.1:8000/api/runtime-identity
echo.

uv.exe run python -m uvicorn jolt.main:app --host 127.0.0.1 --port 8000
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo JOLT backend stopped with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
