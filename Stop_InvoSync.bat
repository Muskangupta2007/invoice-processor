@echo off
title Stop InvoSync AI Server
color 0C
cls

echo ==============================================================
echo   Stopping InvoSync AI Server...
echo ==============================================================
echo.

:: End scheduled task if active
schtasks /end /tn "InvoSync_AI_Server" >nul 2>&1

:: Find and kill process listening on port 5000
set FOUND=0
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    echo [+] Found process with PID %%a listening on port 5000. Terminating...
    taskkill /F /PID %%a >nul 2>&1
    set FOUND=1
)

if %FOUND% == 1 (
    echo.
    echo   [+] InvoSync AI Server stopped successfully!
) else (
    echo   [-] No InvoSync AI Server process was found running on port 5000.
)

echo ==============================================================
echo.
timeout /t 3
