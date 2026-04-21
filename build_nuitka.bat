@echo off
REM ============================================================
REM  Strata — Nuitka Build Script
REM  Compiles Python to a native Windows exe
REM
REM  Prerequisites:
REM    py -3.12 -m pip install "nuitka[onefile]" zstandard
REM    Visual Studio Build Tools with "Desktop development with C++"
REM    https://visualstudio.microsoft.com/visual-cpp-build-tools/
REM ============================================================

echo.
echo  Strata ^— Nuitka Build
echo  ====================================
echo.

set PY=py -3.12
set ROOT=%~dp0
if "%ROOT:~-1%"=="\" set ROOT=%ROOT:~0,-1%

REM ── Install zstandard if missing (needed for onefile compression) ─────────────
%PY% -c "import zstandard" 2>nul || (
    echo  Installing zstandard...
    %PY% -m pip install zstandard -q
)

REM ── Clean ────────────────────────────────────────────────────────────────────
echo  Cleaning previous build...
if exist "%ROOT%\launcher.dist"  rmdir /s /q "%ROOT%\launcher.dist"
if exist "%ROOT%\launcher.build" rmdir /s /q "%ROOT%\launcher.build"
if exist "%ROOT%\dist"           rmdir /s /q "%ROOT%\dist"
mkdir "%ROOT%\dist"

REM ── Build ────────────────────────────────────────────────────────────────────
echo  Compiling with Nuitka (5-15 minutes)...
echo.

%PY% -m nuitka ^
  --standalone ^
  --onefile ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico="%ROOT%\strata.ico" ^
  --output-filename=Strata.exe ^
  --output-dir="%ROOT%\dist" ^
  --include-data-dir="%ROOT%\templates=templates" ^
  --include-module=app ^
  --include-package-data=webview ^
  --include-package-data=pdfplumber ^
  --include-package-data=reportlab ^
  --include-package-data=docx ^
  --include-package-data=openpyxl ^
  --include-package-data=pptx ^
  ^
  --include-package=webview ^
  --include-package=webview.platforms.winforms ^
  --include-package=webview.platforms.edgechromium ^
  --nofollow-import-to=webview.platforms.android ^
  --nofollow-import-to=webview.platforms.cocoa ^
  --nofollow-import-to=webview.platforms.gtk ^
  --nofollow-import-to=webview.platforms.qt ^
  --nofollow-import-to=webview.platforms.cef ^
  --nofollow-import-to=webview.platforms.mshtml ^
  ^
  --include-package=pdfplumber ^
  --include-package=pdfminer ^
  --include-package=pypdf ^
  --include-package=docx ^
  --include-package=openpyxl ^
  --include-package=reportlab ^
  --include-package=pptx ^
  --include-package=PIL ^
  --include-package=pytesseract ^
  --include-package=pdf2image ^
  --include-package=extract_msg ^
  --include-package=cryptography ^
  --include-package=charset_normalizer ^
  --include-package=cffi ^
  --include-package=csv ^
  --include-package=email ^
  --include-package=zipfile ^
  --include-package=pickle ^
  --include-package=difflib ^
  --include-package=uuid ^
  --include-package=platform ^
  --include-package=http ^
  --include-package=urllib ^
  --include-package=json ^
  --include-package=comtypes ^
  ^
  --nofollow-import-to=tkinter ^
  --nofollow-import-to=_tkinter ^
  --nofollow-import-to=matplotlib ^
  --nofollow-import-to=numpy ^
  --nofollow-import-to=pandas ^
  --nofollow-import-to=scipy ^
  --nofollow-import-to=PyQt5 ^
  --nofollow-import-to=PyQt6 ^
  --nofollow-import-to=PySide2 ^
  --nofollow-import-to=PySide6 ^
  --nofollow-import-to=wx ^
  --nofollow-import-to=gi ^
  --nofollow-import-to=gtk ^
  --nofollow-import-to=IPython ^
  --nofollow-import-to=jupyter ^
  ^
  --disable-plugin=pywebview ^
  --assume-yes-for-downloads ^
  "%ROOT%\launcher.py"

if errorlevel 1 (
    echo.
    echo  ERROR: Nuitka build failed. See output above.
    pause & exit /b 1
)

echo.
echo  Compiled: dist\Strata.exe

REM ── Bundle Tesseract ─────────────────────────────────────────────────────────
if exist "%ROOT%\tesseract" (
    echo  Bundling Tesseract...
    xcopy /E /I /Q "%ROOT%\tesseract" "%ROOT%\dist\tesseract"
)

REM ── Bundle Poppler ───────────────────────────────────────────────────────────
if exist "%ROOT%\poppler" (
    echo  Bundling Poppler...
    xcopy /E /I /Q "%ROOT%\poppler" "%ROOT%\dist\poppler"
)

REM ── Inno Setup installer ─────────────────────────────────────────────────────
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"

if exist %ISCC% (
    echo  Building installer with Inno Setup...
    %ISCC% "%ROOT%\installer_nuitka.iss"
    if errorlevel 1 (
        echo  WARNING: Inno Setup failed.
    ) else (
        echo.
        echo  ============================================================
        echo   SUCCESS: dist\Strata_Setup.exe
        echo  ============================================================
    )
) else (
    echo.
    echo  ============================================================
    echo   SUCCESS: dist\Strata.exe
    echo   ^(Inno Setup not found ^— distribute Strata.exe directly^)
    echo  ============================================================
)

echo.
pause
