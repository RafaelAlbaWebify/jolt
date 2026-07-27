@echo off
setlocal EnableExtensions

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0validate-windows-launchers.ps1"
exit /b %ERRORLEVEL%
