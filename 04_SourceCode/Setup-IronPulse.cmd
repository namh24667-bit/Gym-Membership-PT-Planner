@echo off
setlocal
set "PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not exist "%PWSH%" (
    echo Can PowerShell 7 x64. Xem README.
    exit /b 1
)
"%PWSH%" -NoLogo -NoProfile -File "%~dp0ops\portable\Setup.ps1" %*
if errorlevel 1 (
    pause
    exit /b 1
)
