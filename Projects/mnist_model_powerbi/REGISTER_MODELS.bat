@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment is missing.
    echo Run INSTALL_PROJECT.ps1 first.
    goto :end
)

"%~dp0.venv\Scripts\python.exe" -m scripts.install_trained_models
if errorlevel 1 goto :end

"%~dp0.venv\Scripts\python.exe" -m scripts.verify_project

:end
pause
