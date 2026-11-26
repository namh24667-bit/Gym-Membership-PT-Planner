@echo off
setlocal
set "PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not exist "%PWSH%" exit /b 1
"%PWSH%" -NoLogo -NoProfile -File "%~dp0ops\portable\Update.ps1" %*
if errorlevel 1 (
    pause
    exit /b 1
)
