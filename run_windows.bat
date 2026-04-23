@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not on PATH.
  echo Install the development dependencies once with:
  echo    python -m pip install -r requirements.txt
  exit /b 1
)

python app.py
