@echo off
setlocal EnableExtensions

set "REPO=%~dp0"
set "FRONTEND_DIR=%REPO%frontend"

cd /d "%FRONTEND_DIR%"
if errorlevel 1 (
    echo ERROR: Could not enter frontend directory: "%FRONTEND_DIR%"
    pause
    exit /b 1
)

echo Starting JOLT frontend...
npm.cmd run dev -- --host 127.0.0.1
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo JOLT frontend stopped with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
