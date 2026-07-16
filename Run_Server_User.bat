@echo off
title InvoSync AI - Server (User Mode)
color 0A
cd /d "%~dp0"

:: Prioritize the known working Python 3.12 path
set PYTHON_PATH=C:\Users\Muskan Gupta\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYTHON_PATH%" (
    set PYTHON_PATH=
    for /f "delims=" %%i in ('where python 2^>nul') do set PYTHON_PATH=%%i
)

echo Starting InvoSync AI Server...
echo.
echo Verifying packages...
"%PYTHON_PATH%" -m pip install flask pandas openpyxl zeroconf

echo.
echo Starting application...
"%PYTHON_PATH%" app.py
echo.
echo Server stopped.
pause
