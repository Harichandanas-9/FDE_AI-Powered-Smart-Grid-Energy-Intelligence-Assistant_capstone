@echo off
echo ================================================
echo  Smart Grid AI - Frontend Startup
echo ================================================
echo.

cd /d "%~dp0frontend"

echo Starting frontend on http://localhost:5173
echo.
npm run dev
pause
