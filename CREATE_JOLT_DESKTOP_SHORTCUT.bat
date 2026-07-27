@echo off
setlocal EnableExtensions

set "JOLT_LAUNCHER=%~dp0START_JOLT.bat"
set "JOLT_WORKDIR=%~dp0"

if not exist "%JOLT_LAUNCHER%" (
    echo ERROR: START_JOLT.bat was not found at "%JOLT_LAUNCHER%".
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$desktop = [Environment]::GetFolderPath('Desktop'); $shortcutPath = Join-Path $desktop 'JOLT.lnk'; $shell = New-Object -ComObject WScript.Shell; $shortcut = $shell.CreateShortcut($shortcutPath); $shortcut.TargetPath = $env:JOLT_LAUNCHER; $shortcut.WorkingDirectory = $env:JOLT_WORKDIR; $shortcut.Description = 'Start JOLT'; $shortcut.IconLocation = Join-Path $env:SystemRoot 'System32\SHELL32.dll,137'; $shortcut.Save(); Write-Host ('Created desktop shortcut: ' + $shortcutPath)"

if errorlevel 1 (
    echo ERROR: The JOLT desktop shortcut could not be created.
    pause
    exit /b 1
)

echo.
echo JOLT desktop shortcut created successfully.
pause
exit /b 0
