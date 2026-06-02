@echo off
echo ================================================
echo  Smart Grid AI - Backend Startup
echo ================================================
echo.

cd /d "%~dp0backend"

echo [1/3] Killing any process on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo [2/3] Activating virtual environment...
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo WARNING: No venv found, using system Python
)

echo [3/3] Starting backend on http://localhost:8000
echo.
echo  Health check: http://localhost:8000/api/v1/health
echo  API docs:     http://localhost:8000/docs
echo  Press Ctrl+C to stop
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop asyncio
pause
