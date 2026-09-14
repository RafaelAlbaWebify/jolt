@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "CI=1"

echo Testing bootstrap...
call "%ROOT%AI_CONTEXT.bat" bootstrap
if errorlevel 1 goto fail

echo Testing delta...
call "%ROOT%AI_CONTEXT.bat" delta
if errorlevel 1 goto fail

echo Testing full...
call "%ROOT%AI_CONTEXT.bat" full
if errorlevel 1 goto fail

echo Testing module scope: review...
call "%ROOT%AI_CONTEXT.bat" bootstrap review
if errorlevel 1 goto fail

echo Testing session handoff...
pushd "%ROOT%"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "tools\finish_ai_session.py"
) else (
  python "tools\finish_ai_session.py"
)
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" goto fail

if not exist "%ROOT%.ai\generated\AI_CONTEXT_BUNDLE.md" goto fail
if not exist "%ROOT%.ai\generated\AI_CONTEXT_MANIFEST.json" goto fail
if not exist "%ROOT%.ai\generated\SESSION_HANDOFF.md" goto fail
if not exist "%ROOT%.ai\generated\SESSION_HANDOFF.json" goto fail

powershell -NoProfile -Command "$m=Get-Content '%ROOT%.ai\generated\AI_CONTEXT_MANIFEST.json' -Raw | ConvertFrom-Json; if([string]::IsNullOrWhiteSpace($m.commit) -or $m.commit -eq 'unknown'){exit 2}; if($null -eq $m.freshness -or [string]::IsNullOrWhiteSpace($m.freshness.overall)){exit 3}; $h=Get-Content '%ROOT%.ai\generated\SESSION_HANDOFF.json' -Raw | ConvertFrom-Json; if([string]::IsNullOrWhiteSpace($h.commit)){exit 4}; $b=Get-Item '%ROOT%.ai\generated\AI_CONTEXT_BUNDLE.md'; if($b.Length -lt 500){exit 5}"
if errorlevel 1 goto fail

echo.
echo ================================================
echo   PASS - ENHANCED AI WORKFLOW IS WORKING
echo ================================================
echo bootstrap / delta / full / module / freshness / handoff: PASS
echo.
pause
exit /b 0

:fail
echo.
echo ================================================
echo   FAIL - ENHANCED AI WORKFLOW NEEDS ATTENTION
echo ================================================
echo.
pause
exit /b 1
