@echo off
setlocal EnableExtensions

set "REPO=%~dp0"
set "STATUS_HELPER=%REPO%tools\jolt-launcher-status.ps1"

if not exist "%STATUS_HELPER%" (
    echo ERROR: Launcher status helper was not found at "%STATUS_HELPER%".
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%STATUS_HELPER%"
set "EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %EXIT_CODE%
