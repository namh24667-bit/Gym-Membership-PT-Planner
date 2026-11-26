@echo off
setlocal
if exist "%~dp0package-manifest.json" goto portable
if exist "%~dp0instance\local05e\active.json" goto official
set "PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"
set "LAUNCHER=%~dp0ops\sql-02\Launch-LocalDemo.ps1"
if /i "%~1"=="--credentials" (
    "%PWSH%" -NoLogo -NoProfile -File "%LAUNCHER%" -ShowDemoCredentials
    pause
    exit /b
)
set "START_OPTIONS="
if /i "%~1"=="--restart" set "START_OPTIONS=%START_OPTIONS% -ReplaceExisting"
if /i "%~2"=="--restart" set "START_OPTIONS=%START_OPTIONS% -ReplaceExisting"
if /i "%~1"=="--https" set "START_OPTIONS=%START_OPTIONS% -UseHttps"
if /i "%~2"=="--https" set "START_OPTIONS=%START_OPTIONS% -UseHttps"
"%PWSH%" -NoLogo -NoProfile -File "%LAUNCHER%" %START_OPTIONS%
if errorlevel 1 (
    pause
    exit /b 1
)

exit /b 0

:official
set "MODE=Start"
if "%~1"=="" goto official_launch
if /i "%~1"=="--stop" (set "MODE=Stop"& goto official_launch)
if /i "%~1"=="--check" (set "MODE=Check"& goto official_launch)
if /i "%~1"=="--restart" (set "MODE=Restart"& goto official_launch)
if /i "%~1"=="--credentials" (set "MODE=Credentials"& goto official_launch)
if /i "%~1"=="--rollback" (set "MODE=Rollback"& goto official_launch)
echo Tuy chon khong hop le.
exit /b 2
:official_launch
if not "%~2"=="" exit /b 2
"%ProgramFiles%\PowerShell\7\pwsh.exe" -NoLogo -NoProfile -File "%~dp0ops\sql-02\Start-IronPulseOwner.ps1" -Mode %MODE%
set "RESULT=%ERRORLEVEL%"
if /i "%MODE%"=="Credentials" if /i not "%IRONPULSE_NO_PAUSE%"=="1" pause
exit /b %RESULT%

:portable
if not exist "%ProgramFiles%\PowerShell\7\pwsh.exe" (
    echo Can PowerShell 7 x64.
    exit /b 1
)
set "MODE=serve"
set "OPTIONS="
:parse
if "%~1"=="" goto launch
if /i "%~1"=="--check" (set "MODE=check"& goto next)
if /i "%~1"=="--restart" (set "MODE=restart"& goto next)
if /i "%~1"=="--stop" (set "MODE=stop"& goto next)
if /i "%~1"=="--credentials" (set "MODE=credentials"& goto next)
if /i "%~1"=="--version" (set "MODE=version"& goto next)
if /i "%~1"=="--https" (set "OPTIONS=%OPTIONS% -UseHttps"& goto next)
if /i "%~1"=="--no-browser" (set "OPTIONS=%OPTIONS% -NoBrowser"& goto next)
echo Tuy chon khong hop le.
exit /b 2
:next
shift
goto parse
:launch
"%ProgramFiles%\PowerShell\7\pwsh.exe" -NoLogo -NoProfile -File "%~dp0ops\portable\Launch.ps1" -Mode %MODE% %OPTIONS%
set "RESULT=%ERRORLEVEL%"
if /i "%MODE%"=="credentials" if /i not "%IRONPULSE_NO_PAUSE%"=="1" pause
if not "%RESULT%"=="0" if /i not "%IRONPULSE_NO_PAUSE%"=="1" pause
exit /b %RESULT%
