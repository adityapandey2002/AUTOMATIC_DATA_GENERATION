# ── Ambient Scribe — Laptop Installer (Windows) ──
# Run this on the clinic laptop to install the capture agent.
# Requirements: Python 3.11+ installed on the laptop.

@echo off
setlocal
echo ========================================
echo  Ambient Scribe Capture Agent Installer
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python 3.11+ not found.
    echo Install from https://www.python.org/downloads/
    echo Make sure "Add Python to PATH" is checked.
    pause
    exit /b 1
)

REM Create virtual environment
echo [1/4] Creating virtual environment...
python -m venv "%~dp0venv"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to create venv
    pause
    exit /b 1
)

REM Activate and install deps
echo [2/4] Installing dependencies (this takes a few minutes)...
call "%~dp0venv\Scripts\activate.bat"
pip install --upgrade pip >nul 2>&1
pip install -r "%~dp0requirements.txt"
pip install pyinstaller
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
)

REM Build standalone exe
echo [3/4] Building capture agent executable...
cd /d "%~dp0.."
pyinstaller --onefile --name capture-agent ^
    --add-data "capture-agent\probe.py;." ^
    --hidden-import=sounddevice ^
    --hidden-import=websocket ^
    capture-agent\main.py
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] PyInstaller build failed, will use python -m directly
)

REM Copy .env
echo [4/4] Configuring...
if not exist "%~dp0..\\.env" (
    copy "%~dp0..\\.env.example" "%~dp0..\\.env"
    echo [!] Created .env from template — please edit with API keys
)

echo.
echo ========================================
echo  Installation complete!
echo.
echo  To run:
echo    python "%~dp0main.py" --backend-url ws://YOUR_SERVER:8765/ws/chunks
echo.
echo  Or if PyInstaller succeeded:
echo    dist\capture-agent.exe --backend-url ws://YOUR_SERVER:8765/ws/chunks
echo ========================================
pause
