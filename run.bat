@echo off
title 24/7 Multi-Stream Live Automation
color 0A

echo ======================================================================
echo    24/7 Multi-Stream & Multi-RDP Live Hub (Parallel Channels)
echo ======================================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not installed or not added to PATH!
    echo Please install Python 3.10+ and make sure to check "Add Python to PATH".
    echo.
    pause
    exit /b
)

:: 2. Check FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    color 0E
    echo [WARNING] FFmpeg was not detected in PATH!
    echo Please make sure FFmpeg is installed for streaming to work.
    echo.
)

:: 3. Create .env if not exists
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
    )
)

:: 4. Install dependencies
echo [1/2] Checking and installing dependencies...
python -m pip install -r requirements.txt --quiet --no-warn-script-location

:: 5. Create directories
if not exist "videos" mkdir videos
if not exist "thumbnails" mkdir thumbnails
if not exist "logs" mkdir logs
if not exist "logs\ffmpeg_logs" mkdir logs\ffmpeg_logs

echo [2/2] Launching 24/7 Multi-Live Automation System...
echo.

:: 6. Run main.py
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with an error.
    pause
)
