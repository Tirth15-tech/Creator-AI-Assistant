@echo off
setlocal
title ContentAI - Creator Assistant

cd /d "%~dp0"

echo ============================================
echo  ContentAI - AI Social Media Content Assistant
echo ============================================
echo.

REM ---- Check for Python ----
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM ---- Check for the virtual environment ----
if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

set "PY=%~dp0venv\Scripts\python.exe"
set "PIP=%~dp0venv\Scripts\pip.exe"

REM ---- Create .env if it does not exist ----
if not exist ".env" (
    if exist ".env.example" (
        echo Creating .env from .env.example...
        copy ".env.example" ".env" >nul
    ) else (
        echo [WARNING] No .env or .env.example found. Using defaults.
    )
)

REM ---- Install dependencies if not already installed ----
"%PY%" -c "import fastapi, uvicorn, sqlalchemy" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies, this may take a while on the first run...
    "%PIP%" install --upgrade pip
    "%PIP%" install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    echo Dependencies already installed.
)

echo.
echo Starting the server at http://localhost:8000
echo Press Ctrl+C to stop.
echo.

"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
endlocal
