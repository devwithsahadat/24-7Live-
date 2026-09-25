@echo off
title 24/7 Multi-Stream - One Click Windows RDP Setup & Launcher
color 0B

echo ======================================================================
echo    Windows RDP One-Click Multi-Stream & Multi-Node Setup
echo ======================================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Installing Python automatically...
    powershell -Command "winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements" >nul 2>&1
    if %errorlevel% neq 0 (
        echo Please install Python 3.10+ and check 'Add Python to PATH'.
        pause
        exit /b
    )
    echo [OK] Python installed! Please restart this script.
    pause
    exit /b
)
echo [1/4] Python detected successfully.

:: 2. Check FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [2/4] FFmpeg not found! Auto-downloading and configuring FFmpeg...
    if not exist "%~dp0ffmpeg\bin\ffmpeg.exe" (
        echo Downloading FFmpeg package (please wait)...
        powershell -Command "$ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile '%~dp0ffmpeg.zip'"
        echo Extracting FFmpeg...
        powershell -Command "Expand-Archive -Path '%~dp0ffmpeg.zip' -DestinationPath '%~dp0ffmpeg_temp' -Force"
        powershell -Command "$dir = Get-ChildItem '%~dp0ffmpeg_temp' | Select-Object -First 1; Move-Item $dir.FullName '%~dp0ffmpeg' -Force; Remove-Item '%~dp0ffmpeg_temp', '%~dp0ffmpeg.zip' -Recurse -Force"
    )
    set "PATH=%~dp0ffmpeg\bin;%PATH%"
    echo [OK] FFmpeg configured!
) else (
    echo [2/4] FFmpeg detected.
)

:: 3. Create required directories
if not exist "videos" mkdir videos
if not exist "thumbnails" mkdir thumbnails
if not exist "logs" mkdir logs
if not exist "logs\ffmpeg_logs" mkdir logs\ffmpeg_logs

:: 4. Install all Python dependencies
echo [3/4] Installing all required Python dependencies...
python -m pip install -r requirements.txt --quiet --no-warn-script-location
echo [OK] All dependencies ready.

:: 5. Launch Application
echo.
echo [4/4] Starting 24/7 Multi-Live Automation Bot...
echo ======================================================================
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application encountered an error.
    pause
)
