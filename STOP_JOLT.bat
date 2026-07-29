@echo off
setlocal EnableExtensions

set "REPO=%~dp0"
set "STOP_HELPER=%REPO%tools\jolt-stop.ps1"

if not exist "%STOP_HELPER%" (
    echo ERROR: Stop helper was not found at "%STOP_HELPER%".
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%STOP_HELPER%"
set "EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %EXIT_CODE%
