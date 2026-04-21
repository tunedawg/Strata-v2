@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  Strata — Windows Build Script
REM  Output: dist\Strata_Setup.exe
REM
REM  ── FIRST TIME SETUP ──────────────────────────────────────
REM  Run these once with Python 3.12:
REM
REM    py -3.12 -m pip install pyinstaller pywebview pdfplumber pypdf
REM    py -3.12 -m pip install python-docx openpyxl reportlab python-pptx
REM    py -3.12 -m pip install extract-msg pillow pytesseract pdf2image
REM
REM  ── OPTIONAL: BUNDLE OCR ──────────────────────────────────
REM  STEP A — Tesseract:
REM    1. Download: https://github.com/UB-Mannheim/tesseract/wiki
REM    2. Install, then copy to .\tesseract\ next to this script:
REM       xcopy /E /I "C:\Program Files\Tesseract-OCR" tesseract
REM
REM  STEP B — Poppler:
REM    1. Download: https://github.com/oschwartz10612/poppler-windows/releases
REM    2. Extract and copy folder to .\poppler\ so .\poppler\bin\pdftoppm.exe exists
REM
REM  ── INSTALLER ─────────────────────────────────────────────
REM  Inno Setup 6: https://jrsoftware.org/isdl.php
REM ============================================================

echo.
echo  Strata ^— Windows Build
echo  ====================================
echo.

REM ── Use Python 3.12 explicitly ───────────────────────────────────────────────
set PY=py -3.12
set PI=py -3.12 -m PyInstaller

echo  Checking Python 3.12...
%PY% --version
if errorlevel 1 (
    echo  ERROR: Python 3.12 not found. Install from python.org
    pause & exit /b 1
)

REM ── Report OCR bundling status ───────────────────────────────────────────────
echo  Checking optional OCR components...
if exist tesseract\tesseract.exe (
    echo  [OK] Tesseract found ^— will be bundled
) else (
    echo  [--] No tesseract\ folder ^— OCR requires user install
)
if exist poppler\bin\pdftoppm.exe (
    echo  [OK] Poppler found ^— will be bundled
) else (
    echo  [--] No poppler\bin\ folder ^— PDF-to-image unavailable
)
echo.

REM ── Clean previous build ─────────────────────────────────────────────────────
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist

REM ── Run PyInstaller ──────────────────────────────────────────────────────────
echo  Building application bundle...
%PI% universal_search.spec --noconfirm

if errorlevel 1 (
    echo.
    echo  ERROR: PyInstaller build failed. See output above.
    pause & exit /b 1
)

echo.
echo  Bundle created: dist\Strata\

REM ── Run Inno Setup ───────────────────────────────────────────────────────────
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"

if exist %ISCC% (
    echo  Building installer...
    %ISCC% installer.iss
    if errorlevel 1 (
        echo  ERROR: Inno Setup failed.
    ) else (
        echo.
        echo  ============================================================
        echo   SUCCESS: dist\Strata_Setup.exe is ready to share.
        echo  ============================================================
    )
) else (
    echo.
    echo  Inno Setup not found ^— skipping installer.
    echo  ^> Install from: https://jrsoftware.org/isdl.php
    echo  ^> Or zip and distribute dist\Strata\ directly.
)

echo.
pause
