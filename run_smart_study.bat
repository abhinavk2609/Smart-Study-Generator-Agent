@echo off
setlocal enabledelayedexpansion

title Smart Study Generator

set "PROJECT_ROOT=%~dp0"
set "PYTHON=C:\Users\avira\AppData\Local\Programs\Python\Python312\python.exe"
set "VENV_PYTHON=%PROJECT_ROOT%venv\Scripts\python.exe"
set "VENV_PIP=%PROJECT_ROOT%venv\Scripts\pip.exe"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "ENV_FILE=%PROJECT_ROOT%.env"
set "ENV_EXAMPLE=%PROJECT_ROOT%.env.example"
set "REQUIREMENTS=%PROJECT_ROOT%requirements.txt"

echo.
echo  ============================================================
echo   Smart Study Generator - AI Study Companion
echo   Powered by Groq + Qwen 3.8-27B
echo  ============================================================
echo.

:: ── Check .env ───────────────────────────────────────────────────
if not exist "%ENV_FILE%" (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo  ACTION REQUIRED: Open .env and set your GROQ_API_KEY
        echo  Get a free key at: https://console.groq.com/keys
        start "" notepad "%ENV_FILE%"
        pause
        exit /b 0
    )
)
copy /Y "%ENV_FILE%" "%BACKEND_DIR%\.env" >nul 2>&1

:: ── Create venv if missing ────────────────────────────────────────
if not exist "%VENV_PYTHON%" (
    echo  [1/3] Creating virtual environment...
    "%PYTHON%" -m venv "%PROJECT_ROOT%venv"
    if errorlevel 1 (
        echo  ERROR: Failed to create venv. Check Python installation.
        pause & exit /b 1
    )
    echo  Virtual environment created.
) else (
    echo  [1/3] Virtual environment OK.
)

:: ── Install dependencies ──────────────────────────────────────────
echo  [2/3] Installing dependencies...
"%VENV_PIP%" install -q -r "%REQUIREMENTS%"
echo  Dependencies ready.

:: ── Start server + open browser ──────────────────────────────────
echo  [3/3] Starting server...
echo.
echo  App: http://127.0.0.1:5000
echo  Press Ctrl+C to stop.
echo  ============================================================
echo.

start "" cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:5000"

cd /d "%BACKEND_DIR%"
"%VENV_PYTHON%" app.py

echo.
echo  Server stopped.
pause
