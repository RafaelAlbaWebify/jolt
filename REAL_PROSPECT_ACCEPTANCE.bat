@echo off
setlocal EnableExtensions

set "REPO=%~dp0"
set "BACKEND=%REPO%backend"
set "SCRIPT=%REPO%tools\jolt-real-prospect-acceptance.py"

where uv.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: uv.exe was not found on PATH.
    exit /b 1
)

if not exist "%BACKEND%\data\jolt.db" (
    echo ERROR: Active JOLT database was not found at "%BACKEND%\data\jolt.db".
    exit /b 1
)

echo Running non-destructive JOLT real-prospect acceptance rehearsal...
echo The active database will be backed up and read, but cleanup is executed only on a restored copy.
echo.

pushd "%BACKEND%"
uv.exe run python "%SCRIPT%"
set "EXITCODE=%ERRORLEVEL%"
popd

if not "%EXITCODE%"=="0" (
    echo.
    echo JOLT real-prospect acceptance FAILED.
    exit /b %EXITCODE%
)

echo.
echo JOLT real-prospect acceptance PASSED.
echo Evidence is under %%USERPROFILE%%\Downloads\JOLT_ACCEPTANCE
exit /b 0
