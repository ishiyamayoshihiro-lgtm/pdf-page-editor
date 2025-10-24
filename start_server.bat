@echo off
echo ================================
echo PDF Web App Server Starting...
echo ================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Python found. Starting server...
    echo.
    python app.py
    goto end
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Python found. Starting server...
    echo.
    py app.py
    goto end
)

echo ERROR: Python not found.
echo Please install Python 3.7 or higher.
echo https://www.python.org/downloads/
echo.
pause
goto end

:end
echo.
echo ================================
echo Server stopped.
echo ================================
pause
