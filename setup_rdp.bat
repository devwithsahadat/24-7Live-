@echo off
setlocal enabledelayedexpansion
title 24/7 Multi-Stream Live Hub - RDP Setup & Auto-Installer
color 0A

echo ======================================================================
echo       24/7 Multi-Stream Windows RDP Auto-Installer & Launcher
echo ======================================================================
echo.

cd /d "%~dp0"

:: -------------------------------------------------------------------------
:: STEP 1: DETECT OR INSTALL PYTHON
:: -------------------------------------------------------------------------
echo [1/4] Checking Python environment...

set "PY_CMD="

:: Check standard 'python'
python --version >nul 2>&1
if %errorlevel% equ 0 set "PY_CMD=python"

:: Check 'py' launcher
if "%PY_CMD%"=="" (
    py --version >nul 2>&1
    if %errorlevel% equ 0 set "PY_CMD=py"
)

:: Check specific known directories
if "%PY_CMD%"=="" (
    if exist "C:\Python312\python.exe" (
        set "PY_CMD=C:\Python312\python.exe"
        set "PATH=C:\Python312;C:\Python312\Scripts;!PATH!"
    ) else if exist "C:\Python311\python.exe" (
        set "PY_CMD=C:\Python311\python.exe"
        set "PATH=C:\Python311;C:\Python311\Scripts;!PATH!"
    ) else if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PY_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
        set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;!PATH!"
    ) else if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PY_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
        set "PATH=%LocalAppData%\Programs\Python\Python311;%LocalAppData%\Programs\Python\Python311\Scripts;!PATH!"
    )
)

:: If Python is still missing, auto-download and install Python 3.12 silently
if "%PY_CMD%"=="" (
    echo [*] Python not found on this system.
    echo [*] Downloading Python 3.12 installer...
    
    set "DOWNLOAD_OK=0"
    
    :: Method 1: curl.exe (Built-in Windows 10/11/Server 2019/2022)
    curl.exe -L -k -o "%~dp0python_installer.exe" "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe" >nul 2>&1
    if exist "%~dp0python_installer.exe" set "DOWNLOAD_OK=1"
    
    :: Method 2: PowerShell WebClient fallback
    if "!DOWNLOAD_OK!"=="0" (
        powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe', '%~dp0python_installer.exe')" >nul 2>&1
        if exist "%~dp0python_installer.exe" set "DOWNLOAD_OK=1"
    )

    if exist "%~dp0python_installer.exe" (
        echo [*] Installing Python 3.12 into C:\Python312 (Please wait 30 seconds)...
        "%~dp0python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_test=0 Shortcuts=0 TargetDir="C:\Python312"
        timeout /t 8 /nobreak >nul
        del "%~dp0python_installer.exe" >nul 2>&1
        
        if exist "C:\Python312\python.exe" (
            set "PY_CMD=C:\Python312\python.exe"
            set "PATH=C:\Python312;C:\Python312\Scripts;!PATH!"
        ) else if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
            set "PY_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
            set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;!PATH!"
        ) else (
            python --version >nul 2>&1 && set "PY_CMD=python"
        )
    )
)

if "%PY_CMD%"=="" (
    color 0C
    echo [ERROR] Automatic Python installation failed.
    echo Please install Python manually from: https://www.python.org/downloads/
    echo (Make sure to check "Add Python to PATH")
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

echo [OK] Python is active: %PY_CMD%

:: -------------------------------------------------------------------------
:: STEP 2: DETECT OR INSTALL FFMPEG
:: -------------------------------------------------------------------------
echo.
echo [2/4] Checking FFmpeg audio/video encoder...

set "FFMPEG_OK=0"
ffmpeg -version >nul 2>&1 && set "FFMPEG_OK=1"

if exist "%~dp0ffmpeg\bin\ffmpeg.exe" (
    set "PATH=%~dp0ffmpeg\bin;!PATH!"
    set "FFMPEG_OK=1"
)

if "!FFMPEG_OK!"=="0" (
    echo [*] FFmpeg not detected in PATH.
    echo [*] Downloading portable FFmpeg package (1-2 minutes)...
    
    set "FF_DL_OK=0"
    curl.exe -L -k -o "%~dp0ffmpeg.zip" "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" >nul 2>&1
    if exist "%~dp0ffmpeg.zip" set "FF_DL_OK=1"
    
    if "!FF_DL_OK!"=="0" (
        powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip', '%~dp0ffmpeg.zip')" >nul 2>&1
        if exist "%~dp0ffmpeg.zip" set "FF_DL_OK=1"
    )

    if exist "%~dp0ffmpeg.zip" (
        echo [*] Extracting FFmpeg binaries...
        powershell -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%~dp0ffmpeg.zip' -DestinationPath '%~dp0ffmpeg_temp' -Force"
        powershell -ExecutionPolicy Bypass -Command "$dir = Get-ChildItem '%~dp0ffmpeg_temp' | Select-Object -First 1; Move-Item $dir.FullName '%~dp0ffmpeg' -Force; Remove-Item '%~dp0ffmpeg_temp', '%~dp0ffmpeg.zip' -Recurse -Force"
        
        if exist "%~dp0ffmpeg\bin\ffmpeg.exe" (
            set "PATH=%~dp0ffmpeg\bin;!PATH!"
            set "FFMPEG_OK=1"
            echo [OK] FFmpeg configured locally in project!
        )
    )
)

if "!FFMPEG_OK!"=="1" (
    echo [OK] FFmpeg is ready.
) else (
    echo [WARNING] FFmpeg could not be configured automatically.
)

:: -------------------------------------------------------------------------
:: STEP 3: CREATE FOLDERS AND INSTALL DEPENDENCIES
:: -------------------------------------------------------------------------
echo.
echo [3/4] Preparing directories and installing requirements...

if not exist "videos" mkdir videos
if not exist "thumbnails" mkdir thumbnails
if not exist "logs" mkdir logs
if not exist "logs\ffmpeg_logs" mkdir logs\ffmpeg_logs

if not exist ".env" (
    if exist ".env.example" copy .env.example .env >nul
)

echo [*] Installing required Python packages...
"%PY_CMD%" -m pip install --upgrade pip --quiet --no-warn-script-location >nul 2>&1
"%PY_CMD%" -m pip install -r requirements.txt --no-warn-script-location

echo [OK] Dependencies ready!

:: -------------------------------------------------------------------------
:: STEP 4: LAUNCH BOT AUTOMATION
:: -------------------------------------------------------------------------
echo.
echo [4/4] Starting 24/7 Multi-Stream Live Automation Bot...
echo ======================================================================
echo.

"%PY_CMD%" main.py

if %errorlevel% neq 0 (
    echo.
    echo ======================================================================
    echo [!] Bot exited with code %errorlevel%.
    echo ======================================================================
    echo Press any key to exit...
    pause >nul
)
