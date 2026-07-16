@echo off
title InvoSync AI Server Manager
color 0B
cls

:: Check admin privilege
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Administrative privileges are required. Requesting elevation...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Set working directory to the script's directory (handles Admin execution directory reset)
cd /d "%~dp0"

:: Add Firewall rule
netsh advfirewall firewall add rule name="InvoSync AI Port 5000" dir=in action=allow protocol=TCP localport=5000 >nul 2>&1

:: Map invoice.local to localhost in hosts
findstr /L /I /C:"127.0.0.1 invoice.local" %SystemRoot%\System32\drivers\etc\hosts >nul
if %errorLevel% neq 0 (
    echo.>>%SystemRoot%\System32\drivers\etc\hosts
    echo 127.0.0.1 invoice.local>>%SystemRoot%\System32\drivers\etc\hosts
)

:: Map invoice to localhost in hosts
findstr /L /I /C:"127.0.0.1 invoice" %SystemRoot%\System32\drivers\etc\hosts >nul
if %errorLevel% neq 0 (
    echo.>>%SystemRoot%\System32\drivers\etc\hosts
    echo 127.0.0.1 invoice>>%SystemRoot%\System32\drivers\etc\hosts
)

:: Map muskan to localhost in hosts
findstr /L /I /C:"127.0.0.1 muskan" %SystemRoot%\System32\drivers\etc\hosts >nul
if %errorLevel% neq 0 (
    echo.>>%SystemRoot%\System32\drivers\etc\hosts
    echo 127.0.0.1 muskan>>%SystemRoot%\System32\drivers\etc\hosts
)

:: Detect if mappings are successful
findstr /L /I /C:"127.0.0.1 invoice.local" %SystemRoot%\System32\drivers\etc\hosts >nul
set HAS_INVOICE_LOCAL_MAPPING=%errorLevel%

findstr /L /I /C:"127.0.0.1 invoice" %SystemRoot%\System32\drivers\etc\hosts >nul
set HAS_INVOICE_MAPPING=%errorLevel%

findstr /L /I /C:"127.0.0.1 muskan" %SystemRoot%\System32\drivers\etc\hosts >nul
set HAS_MUSKAN_MAPPING=%errorLevel%

:: Find pythonw.exe and python.exe paths
set PYTHONW_PATH=
set PYTHON_PATH=
for /f "delims=" %%i in ('where pythonw 2^>nul') do set PYTHONW_PATH=%%i
for /f "delims=" %%i in ('where python 2^>nul') do set PYTHON_PATH=%%i

if "%PYTHON_PATH%"=="" (
    if not "%PYTHONW_PATH%"=="" (
        set PYTHON_PATH=%PYTHONW_PATH:pythonw.exe=python.exe%
    )
)
if "%PYTHONW_PATH%"=="" (
    if not "%PYTHON_PATH%"=="" (
        set PYTHONW_PATH=%PYTHON_PATH:python.exe=pythonw.exe%
    )
)

if "%PYTHON_PATH%"=="" (
    set PYTHON_PATH=C:\Users\Muskan Gupta\AppData\Local\Programs\Python\Python312\python.exe
)
if "%PYTHONW_PATH%"=="" (
    set PYTHONW_PATH=C:\Users\Muskan Gupta\AppData\Local\Programs\Python\Python312\pythonw.exe
)

:menu
cls
echo  ==============================================================
echo    InvoSync AI - Ingestion and Verification Hub Server Manager
echo  ==============================================================
echo.
echo   [1] Start Server in Foreground (Visible Window)
echo   [2] Install ^& Start Server in Background (Runs silently on Startup)
echo   [3] Stop Server (Kill process on port 5000)
echo   [4] Uninstall Background Startup Task
echo   [5] Exit
echo.

echo  ==============================================================
set /p opt="Select an option (1-5): "

if "%opt%"=="1" goto start_fg
if "%opt%"=="2" goto start_bg
if "%opt%"=="3" goto stop_server
if "%opt%"=="4" goto uninstall_bg
if "%opt%"=="5" exit

echo [!] Invalid option. Please try again.
timeout /t 2 >nul
goto menu

:start_fg
cls
echo Starting InvoSync AI Server in Foreground...
:: Automatically open browser for the host user
timeout /t 2 /nobreak >nul
if %HAS_INVOICE_LOCAL_MAPPING% == 0 (
    start "" "http://invoice.local:5000"
) else if %HAS_MUSKAN_MAPPING% == 0 (
    start "" "http://muskan:5000"
) else if %HAS_INVOICE_MAPPING% == 0 (
    start "" "http://invoice:5000"
) else (
    start "" "http://127.0.0.1:5000"
)
"%PYTHON_PATH%" app.py
pause
goto menu

:start_bg
cls
echo Installing and starting background task...
schtasks /create /tn "InvoSync_AI_Server" /tr "\"%PYTHONW_PATH%\" \"%CD%\app.py\"" /sc onlogon /rl highest /f >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Failed to create scheduled task.
    pause
    goto menu
)
schtasks /run /tn "InvoSync_AI_Server" >nul 2>&1
echo.
echo [+] Background Startup Task "InvoSync_AI_Server" registered successfully!
echo [+] The server will run silently in the background whenever you log in.
echo.
timeout /t 2 /nobreak >nul
if %HAS_INVOICE_LOCAL_MAPPING% == 0 (
    start "" "http://invoice.local:5000"
) else if %HAS_MUSKAN_MAPPING% == 0 (
    start "" "http://muskan:5000"
) else if %HAS_INVOICE_MAPPING% == 0 (
    start "" "http://invoice:5000"
) else (
    start "" "http://127.0.0.1:5000"
)
pause
goto menu

:stop_server
cls
echo Stopping InvoSync AI Server...
schtasks /end /tn "InvoSync_AI_Server" >nul 2>&1
set FOUND=0
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    set FOUND=1
)
if %FOUND% == 1 (
    echo [+] Server on port 5000 terminated.
) else (
    echo [-] No running server found on port 5000.
)
pause
goto menu

:uninstall_bg
cls
echo Uninstalling background task...
schtasks /delete /tn "InvoSync_AI_Server" /f >nul 2>&1
echo [+] Background startup task "InvoSync_AI_Server" uninstalled.
pause
goto menu
