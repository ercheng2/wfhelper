@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   WeChat Friend Helper v2.0
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python 3.8+
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
pip install pymupdf Pillow pdf2image -q 2>nul

REM Kill existing server on port 8199
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8199 ^| findstr LISTENING') do (
    echo Stopping existing server ^(PID %%a^)...
    taskkill /PID %%a /F >nul 2>&1
)

REM Start server (same window, browser opens automatically from Python)
echo Starting server on port 8199...
python app.py

echo.
echo Server stopped.
