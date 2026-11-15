@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo  NASA Space Apps Challenge 2026 - Health Monitoring Software
echo  Astronaut Psychological Check-in Assistant & HUD Widget
echo =====================================================================
echo.

:: 1. Detect Python executable
set "PY_CMD="
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set "PY_CMD=py"
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] Python was not found in PATH!
    echo Please install Python 3.10+ and make sure to check "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/5] Using Python: %PY_CMD%

:: 2. Create virtual environment if it does not exist
if not exist "venv" (
    echo [2/5] Creating virtual environment 'venv'...
    %PY_CMD% -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
) else (
    echo [2/5] Virtual environment 'venv' already exists.
)

:: Activate virtual environment if available
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: 3. Prepare .env configuration file
if not exist ".env" (
    echo [3/5] Copying .env.example to .env (MOCK_LLM=true enabled by default)...
    copy .env.example .env >nul
) else (
    echo [3/5] .env file detected.
)

:: 4. Install dependencies
echo [4/5] Checking and installing dependencies from requirements.txt...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Dependency install had notices. Continuing...
)

:: 5. Initialize database and seed demo data
echo [5/5] Initializing database and seeding demo astronauts and KB chunks...
python seed.py

echo.
echo =====================================================================
echo  SERVER READY!
echo  Opening at: http://localhost:8000
echo  - Demo Page:     http://localhost:8000/chatbot-demo.html
echo  - Widget JS:     http://localhost:8000/widget.js
echo  - API Docs:      http://localhost:8000/docs
echo =====================================================================
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

if %errorlevel% neq 0 (
    echo [NOTE] Server terminated with code %errorlevel%.
    pause
)
