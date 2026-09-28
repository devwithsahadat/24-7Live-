# 24/7 Multi-Stream & Multi-RDP Live Hub - Automated Setup & Launcher
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "24/7 Multi-Stream Live Automation - Auto Setup"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "     24/7 Multi-Stream & Multi-RDP Windows Auto-Setup Engine" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Enable TLS 1.2 / TLS 1.3 for secure downloads
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor 3072
} catch {}

# Helper function to download file safely using WebClient or curl
function Download-FileSafely([string]$url, [string]$destination) {
    Write-Host "[*] Downloading: $url" -ForegroundColor Yellow
    
    # Try WebClient
    try {
        $wc = New-Object System.Net.WebClient
        $wc.Headers.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        $wc.DownloadFile($url, $destination)
        if (Test-Path $destination) { return $true }
    } catch {
        Write-Host "[!] WebClient download failed, trying curl.exe..." -ForegroundColor DarkYellow
    }

    # Fallback to curl.exe
    try {
        & curl.exe -L -k -o $destination $url
        if (Test-Path $destination) { return $true }
    } catch {
        Write-Host "[!] curl.exe failed, trying Invoke-WebRequest..." -ForegroundColor DarkYellow
    }

    # Fallback to Invoke-WebRequest
    try {
        Invoke-WebRequest -Uri $url -OutFile $destination -UseBasicParsing -UserAgent "Mozilla/5.0"
        if (Test-Path $destination) { return $true }
    } catch {
        Write-Host "[ERROR] All download methods failed for $url" -ForegroundColor Red
        return $false
    }
    return (Test-Path $destination)
}

# -------------------------------------------------------------------------
# STEP 1: PYTHON DETECTION & AUTO-INSTALL
# -------------------------------------------------------------------------
Write-Host "[1/4] Checking Python environment..." -ForegroundColor Cyan

$PythonExe = $null

# Check current PATH
$pyCheck = Get-Command python -ErrorAction SilentlyContinue
if ($pyCheck) {
    $PythonExe = $pyCheck.Source
}

if (-not $PythonExe) {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $PythonExe = "py"
    }
}

# Check common Windows paths
$commonPaths = @(
    "C:\Python312\python.exe",
    "C:\Program Files\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "C:\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
)

if (-not $PythonExe) {
    foreach ($p in $commonPaths) {
        if (Test-Path $p) {
            $PythonExe = $p
            $pDir = Split-Path -Parent $p
            $env:Path = "$pDir;$pDir\Scripts;" + $env:Path
            break
        }
    }
}

# If Python not found, auto-download and install Python 3.12
if (-not $PythonExe) {
    Write-Host "[*] Python is not installed. Downloading official Python 3.12 installer..." -ForegroundColor Yellow
    $pyInstaller = Join-Path $ScriptDir "python_installer.exe"
    $pyUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
    
    $downloaded = Download-FileSafely $pyUrl $pyInstaller
    if ($downloaded) {
        Write-Host "[*] Installing Python 3.12 (Please wait 30-45 seconds)..." -ForegroundColor Yellow
        $proc = Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_test=0 Shortcuts=0 TargetDir=`"C:\Python312`"" -Wait -PassThru
        
        Start-Sleep -Seconds 5
        Remove-Item $pyInstaller -Force -ErrorAction SilentlyContinue

        if (Test-Path "C:\Python312\python.exe") {
            $PythonExe = "C:\Python312\python.exe"
            $env:Path = "C:\Python312;C:\Python312\Scripts;" + $env:Path
        } else {
            $userPy = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
            if (Test-Path $userPy) {
                $PythonExe = $userPy
                $pDir = Split-Path -Parent $userPy
                $env:Path = "$pDir;$pDir\Scripts;" + $env:Path
            }
        }
    }
}

if (-not $PythonExe) {
    Write-Host "[ERROR] Failed to install Python automatically." -ForegroundColor Red
    Write-Host "Please install Python 3.12 manually from https://www.python.org/downloads/ (Check 'Add Python to PATH')" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    exit 1
}

Write-Host "[OK] Python is active: $PythonExe" -ForegroundColor Green

# -------------------------------------------------------------------------
# STEP 2: FFMPEG DETECTION & AUTO-INSTALL
# -------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/4] Checking FFmpeg video/audio engine..." -ForegroundColor Cyan

$FFmpegOk = $false
$localFFmpeg = Join-Path $ScriptDir "ffmpeg\bin\ffmpeg.exe"

if (Test-Path $localFFmpeg) {
    $ffmpegBin = Join-Path $ScriptDir "ffmpeg\bin"
    $env:Path = "$ffmpegBin;" + $env:Path
    $FFmpegOk = $true
} else {
    $ffCheck = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($ffCheck) {
        $FFmpegOk = $true
    }
}

if (-not $FFmpegOk) {
    Write-Host "[*] FFmpeg not found. Downloading portable FFmpeg package..." -ForegroundColor Yellow
    $ffZip = Join-Path $ScriptDir "ffmpeg.zip"
    $ffTemp = Join-Path $ScriptDir "ffmpeg_temp"
    $ffUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

    $ffDownloaded = Download-FileSafely $ffUrl $ffZip
    if ($ffDownloaded) {
        Write-Host "[*] Extracting FFmpeg package (1-2 minutes)..." -ForegroundColor Yellow
        try {
            Expand-Archive -Path $ffZip -DestinationPath $ffTemp -Force
            $extractedDir = Get-ChildItem $ffTemp | Select-Object -First 1
            $targetDir = Join-Path $ScriptDir "ffmpeg"
            if (Test-Path $targetDir) { Remove-Item $targetDir -Recurse -Force -ErrorAction SilentlyContinue }
            Move-Item $extractedDir.FullName $targetDir -Force
            Remove-Item $ffTemp, $ffZip -Recurse -Force -ErrorAction SilentlyContinue

            if (Test-Path $localFFmpeg) {
                $ffmpegBin = Join-Path $ScriptDir "ffmpeg\bin"
                $env:Path = "$ffmpegBin;" + $env:Path
                $FFmpegOk = $true
                Write-Host "[OK] FFmpeg configured locally!" -ForegroundColor Green
            }
        } catch {
            Write-Host "[!] Error extracting FFmpeg: $_" -ForegroundColor Red
        }
    }
}

if ($FFmpegOk) {
    Write-Host "[OK] FFmpeg is ready." -ForegroundColor Green
} else {
    Write-Host "[WARNING] FFmpeg could not be configured automatically." -ForegroundColor Yellow
}

# -------------------------------------------------------------------------
# STEP 3: DIRECTORIES & CONFIG SYNC
# -------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/4] Preparing directories and dependencies..." -ForegroundColor Cyan

$dirs = @("videos", "thumbnails", "logs", "logs\ffmpeg_logs")
foreach ($d in $dirs) {
    $fullPath = Join-Path $ScriptDir $d
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}

$envFile = Join-Path $ScriptDir ".env"
$envExample = Join-Path $ScriptDir ".env.example"

# Auto-fix .env if placeholder exists or file missing
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    if ($envContent -match "your_telegram_bot_token_here" -and (Test-Path $envExample)) {
        Write-Host "[*] Syncing valid credentials from .env.example..." -ForegroundColor Yellow
        Copy-Item $envExample $envFile -Force
    }
} elseif (Test-Path $envExample) {
    Copy-Item $envExample $envFile -Force
}

Write-Host "[*] Installing required Python libraries from requirements.txt..." -ForegroundColor Yellow
& $PythonExe -m pip install --upgrade pip --quiet --no-warn-script-location
& $PythonExe -m pip install -r (Join-Path $ScriptDir "requirements.txt") --no-warn-script-location

Write-Host "[OK] All dependencies installed successfully!" -ForegroundColor Green

# -------------------------------------------------------------------------
# STEP 4: LAUNCH MAIN.PY
# -------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/4] Starting 24/7 Multi-Stream Live Bot..." -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$mainPy = Join-Path $ScriptDir "main.py"
& $PythonExe $mainPy

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[!] Bot exited with code $LASTEXITCODE." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
