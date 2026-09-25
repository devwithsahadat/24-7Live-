@echo off
setlocal enabledelayedexpansion
title 24/7 Multi-Stream Live Automation
color 0A

echo ======================================================================
echo    24/7 Multi-Stream & Multi-RDP Live Hub (Parallel Channels)
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Check Python
set "PY_CMD="
python --version >nul 2>&1 && set "PY_CMD=python"
if "%PY_CMD%"=="" (
    py --version >nul 2>&1 && set "PY_CMD=py"
)
if "%PY_CMD%"=="" (
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PY_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
        set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;!PATH!"
    ) else if exist "C:\Python312\python.exe" (
        set "PY_CMD=C:\Python312\python.exe"
        set "PATH=C:\Python312;C:\Python312\Scripts;!PATH!"
    )
)

if "%PY_CMD%"=="" (
    echo [*] Python not detected. Running auto-installer...
    call "%~dp0setup_rdp.bat"
    exit /b
)

:: 2. Check FFmpeg
if exist "%~dp0ffmpeg\bin\ffmpeg.exe" (
    set "PATH=%~dp0ffmpeg\bin;!PATH!"
)

:: 3. Create directories
if not exist "videos" mkdir videos
if not exist "thumbnails" mkdir thumbnails
if not exist "logs" mkdir logs
if not exist "logs\ffmpeg_logs" mkdir logs\ffmpeg_logs

:: 4. Create .env if not exists
if not exist ".env" (
    if exist ".env.example" copy .env.example .env >nul
)

:: 5. Install dependencies
echo [1/2] Checking Python dependencies...
"%PY_CMD%" -m pip install -r requirements.txt --quiet --no-warn-script-location

echo [2/2] Launching 24/7 Multi-Live Automation System...
echo.

"%PY_CMD%" main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with an error.
    pause
)
