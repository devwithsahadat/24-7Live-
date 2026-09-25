@echo off
setlocal enabledelayedexpansion
title 24/7 Multi-Stream Live Automation - Auto Installer & Setup
color 0B

echo ======================================================================
echo    24/7 Multi-Stream & Multi-RDP Windows Auto-Setup (Self-Healing)
echo ======================================================================
echo.

cd /d "%~dp0"

:: -------------------------------------------------------------------------
:: 1. CHECK AND AUTO-INSTALL PYTHON
:: -------------------------------------------------------------------------
echo [1/4] Checking Python installation...

set "PY_CMD="

:: Check standard 'python'
python --version >nul 2>&1
if %errorlevel% equ 0 set "PY_CMD=python"

:: Check 'py' launcher
if "%PY_CMD%"=="" (
    py --version >nul 2>&1
    if %errorlevel% equ 0 set "PY_CMD=py"
)

:: Check common Python installation paths
if "%PY_CMD%"=="" (
    if exist "C:\Python312\python.exe" (
        set "PY_CMD=C:\Python312\python.exe"
        set "PATH=C:\Python312;C:\Python312\Scripts;!PATH!"
    ) else if exist "C:\Program Files\Python312\python.exe" (
        set "PY_CMD=C:\Program Files\Python312\python.exe"
        set "PATH=C:\Program Files\Python312;C:\Program Files\Python312\Scripts;!PATH!"
    ) else if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PY_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
        set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;!PATH!"
    ) else if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PY_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
        set "PATH=%LocalAppData%\Programs\Python\Python311;%LocalAppData%\Programs\Python\Python311\Scripts;!PATH!"
    )
)

:: If Python still not found, download and install official Python silently
if "%PY_CMD%"=="" (
    echo.
    echo [*] Python not detected! Downloading official Python 3.12 64-bit installer...
    echo [*] Please wait a moment...
    
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile '%~dp0python_installer.exe'"
    
    if exist "%~dp0python_installer.exe" (
        echo [*] Installing Python 3.12 with pip and PATH configuration...
        "%~dp0python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 Shortcuts=0
        timeout /t 5 /nobreak >nul
        del "%~dp0python_installer.exe" >nul 2>&1
        
        :: Re-check installation paths
        if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
            set "PY_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
            set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;!PATH!"
        ) else (
            python --version >nul 2>&1 && set "PY_CMD=python"
        )
    )
)

if "%PY_CMD%"=="" (
    color 0C
    echo [ERROR] Automatic Python installation could not complete.
    echo Please install Python manually from https://www.python.org/downloads/
    echo (Make sure to check "Add Python to PATH")
    pause
    exit /b
)

echo [OK] Using Python: %PY_CMD%

:: -------------------------------------------------------------------------
:: 2. CHECK AND CONFIGURE FFMPEG
:: -------------------------------------------------------------------------
echo.
echo [2/4] Checking FFmpeg installation...

set "FFMPEG_OK=0"
ffmpeg -version >nul 2>&1 && set "FFMPEG_OK=1"

if exist "%~dp0ffmpeg\bin\ffmpeg.exe" (
    set "PATH=%~dp0ffmpeg\bin;!PATH!"
    set "FFMPEG_OK=1"
)

if "!FFMPEG_OK!"=="0" (
    echo [*] FFmpeg not found. Downloading standalone FFmpeg essentials build for RDP...
    echo [*] This will take 1-2 minutes depending on your RDP internet speed...
    
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile '%~dp0ffmpeg.zip'"
    
    if exist "%~dp0ffmpeg.zip" (
        echo [*] Extracting FFmpeg package...
        powershell -Command "Expand-Archive -Path '%~dp0ffmpeg.zip' -DestinationPath '%~dp0ffmpeg_temp' -Force"
        powershell -Command "$dir = Get-ChildItem '%~dp0ffmpeg_temp' | Select-Object -First 1; Move-Item $dir.FullName '%~dp0ffmpeg' -Force; Remove-Item '%~dp0ffmpeg_temp', '%~dp0ffmpeg.zip' -Recurse -Force"
        
        if exist "%~dp0ffmpeg\bin\ffmpeg.exe" (
            set "PATH=%~dp0ffmpeg\bin;!PATH!"
            set "FFMPEG_OK=1"
            echo [OK] FFmpeg downloaded and configured successfully!
        )
    )
)

if "!FFMPEG_OK!"=="1" (
    echo [OK] FFmpeg is ready.
) else (
    echo [WARNING] FFmpeg could not be downloaded automatically.
    echo Live streaming requires FFmpeg. Please ensure FFmpeg is in PATH if already installed.
)

:: -------------------------------------------------------------------------
:: 3. CREATE DIRECTORIES
:: -------------------------------------------------------------------------
echo.
echo [3/4] Preparing directories and dependencies...
if not exist "videos" mkdir videos
if not exist "thumbnails" mkdir thumbnails
if not exist "logs" mkdir logs
if not exist "logs\ffmpeg_logs" mkdir logs\ffmpeg_logs

:: Create .env if not exists
if not exist ".env" (
    if exist ".env.example" copy .env.example .env >nul
)

:: Upgrade pip and install requirements
echo [*] Installing all required Python dependencies (python-telegram-bot, psutil, etc.)...
"%PY_CMD%" -m pip install --upgrade pip --quiet --no-warn-script-location
"%PY_CMD%" -m pip install -r requirements.txt --no-warn-script-location

echo [OK] All dependencies installed successfully.

:: -------------------------------------------------------------------------
:: 4. LAUNCH APPLICATION
:: -------------------------------------------------------------------------
echo.
echo [4/4] Starting 24/7 Multi-Stream Live Hub...
echo ======================================================================
echo.

"%PY_CMD%" main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with an error code %errorlevel%.
    pause
)
