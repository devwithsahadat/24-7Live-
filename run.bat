@echo off
cd /d "%~dp0"
title 24/7 Multi-Stream Live Hub
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if %errorlevel% neq 0 (
    echo.
    echo ======================================================================
    echo Execution finished with code %errorlevel%. Press any key to close...
    echo ======================================================================
    pause >nul
)
