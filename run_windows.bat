@echo off
title Strata — Starting...
color 0A

echo.
echo  ================================================
echo   Strata — Legal Document Search
echo  ================================================
echo.

REM ── Find Python ──────────────────────────────────────────────────────────────
set PYTHON=
for %%p in (
    "py -3.12"
    "py -3.11"
    "py -3.10"
    "py -3.9"
    "py"
    "python3"
    "python"
) do (
    if not defined PYTHON (
        %%~p --version >nul 2>&1 && set PYTHON=%%~p
    )
)

REM ── No Python found — download and install it ─────────────────────────────────
if not defined PYTHON (
    echo  Python not found. Downloading Python 3.12...
    echo  This will take a few minutes on first run.
    echo.

    REM Download Python installer silently
    set PY_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
    set PY_INSTALLER=%TEMP%\python_installer.exe

    REM Try PowerShell to download
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%PY_URL%', '%PY_INSTALLER%')}"

    if not exist "%PY_INSTALLER%" (
        echo  ERROR: Could not download Python.
        echo  Please visit https://www.python.org/downloads/ and install Python 3.12.
        echo  Then run this script again.
        pause
        exit /b 1
    )

    echo  Installing Python 3.12...
    "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
    del "%PY_INSTALLER%"

    REM Refresh PATH
    set PYTHON=py -3.12
    py -3.12 --version >nul 2>&1
    if errorlevel 1 (
        set PYTHON=python
        python --version >nul 2>&1
        if errorlevel 1 (
            echo  Python installation may need a restart.
            echo  Please restart your computer and run this script again.
            pause
            exit /b 1
        )
    )
    echo  Python installed successfully.
    echo.
)

echo  Python found: %PYTHON%

REM ── Install/upgrade pip packages ─────────────────────────────────────────────
echo  Checking dependencies...
%PYTHON% -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo  Installing required packages (first run only, takes ~2 minutes)...
    %PYTHON% -m pip install --quiet --upgrade pip
    %PYTHON% -m pip install --quiet flask pdfplumber pypdf python-docx openpyxl reportlab python-pptx extract-msg pillow pytesseract pdf2image
    echo  Dependencies installed.
    echo.
)

REM ── Find a free port ─────────────────────────────────────────────────────────
set PORT=5000
%PYTHON% -c "import socket; s=socket.socket(); s.bind(('',5000)); s.close()" >nul 2>&1
if errorlevel 1 (
    for /f %%p in ('%PYTHON% -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()"') do set PORT=%%p
)

REM ── Start Flask app ──────────────────────────────────────────────────────────
echo  Starting Strata on port %PORT%...
echo  Opening browser...
echo.
echo  To stop Strata, close this window.
echo.

REM Open browser after short delay
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:%PORT%"

REM Run the app
set FLASK_PORT=%PORT%
%PYTHON% app_flask.py

pause
