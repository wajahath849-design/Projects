@echo off
setlocal
set "PROJECT_SETUP_SCRIPT=%~dp0setup_environment.ps1"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_SETUP_SCRIPT%" %*
exit /b %ERRORLEVEL%
