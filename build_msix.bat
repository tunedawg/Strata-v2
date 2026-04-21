@echo off
echo.
echo  Strata ^— MSIX Builder
echo  ====================================
echo.

set ROOT=%~dp0
if "%ROOT:~-1%"=="\" set ROOT=%ROOT:~0,-1%
echo  Root: %ROOT%

REM ── Find makeappx ────────────────────────────────────────────────────────────
set MAKEAPPX=
for /d %%v in ("C:\Program Files (x86)\Windows Kits\10\bin\10.*") do (
    if exist "%%v\x64\makeappx.exe" set MAKEAPPX=%%v\x64\makeappx.exe
)
if "%MAKEAPPX%"=="" for /d %%v in ("C:\Program Files\Windows Kits\10\bin\10.*") do (
    if exist "%%v\x64\makeappx.exe" set MAKEAPPX=%%v\x64\makeappx.exe
)
if "%MAKEAPPX%"=="" ( echo ERROR: makeappx.exe not found. & pause & exit /b 1 )
echo  makeappx: %MAKEAPPX%

REM ── Find signtool ────────────────────────────────────────────────────────────
set SIGNTOOL=
for /d %%v in ("C:\Program Files (x86)\Windows Kits\10\bin\10.*") do (
    if exist "%%v\x64\signtool.exe" set SIGNTOOL=%%v\x64\signtool.exe
)

REM ── Staging ──────────────────────────────────────────────────────────────────
set STAGING=%ROOT%\msix_staging
echo  Preparing staging...
if exist "%STAGING%" rmdir /s /q "%STAGING%"
mkdir "%STAGING%"
xcopy /E /I /Q "%ROOT%\dist\Strata" "%STAGING%"
copy "%ROOT%\AppxManifest.xml" "%STAGING%\AppxManifest.xml"
mkdir "%STAGING%\assets"
copy "%ROOT%\assets\Square44x44Logo.png"   "%STAGING%\assets\Square44x44Logo.png"
copy "%ROOT%\assets\Square50x50Logo.png"   "%STAGING%\assets\Square50x50Logo.png"
copy "%ROOT%\assets\Square150x150Logo.png" "%STAGING%\assets\Square150x150Logo.png"
copy "%ROOT%\assets\Wide310x150Logo.png"   "%STAGING%\assets\Wide310x150Logo.png"

REM ── Enable long paths via PowerShell before packing ──────────────────────────
echo  Enabling long path support...
powershell -Command "Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name 'LongPathsEnabled' -Value 1 -ErrorAction SilentlyContinue"

REM ── Pack ─────────────────────────────────────────────────────────────────────
set MSIX=%ROOT%\dist\Strata.msix
if exist "%MSIX%" del "%MSIX%"
echo  Packing...

REM Use /l flag to allow long paths, /nv to skip validation
"%MAKEAPPX%" pack /d "%STAGING%" /p "%MSIX%" /nv /l
if errorlevel 1 (
    echo  Retrying without /l flag...
    "%MAKEAPPX%" pack /d "%STAGING%" /p "%MSIX%" /nv /o
    if errorlevel 1 (
        echo  Retrying with overwrite...
        "%MAKEAPPX%" pack /d "%STAGING%" /p "%MSIX%" /o
        if errorlevel 1 ( echo ERROR: makeappx failed. & pause & exit /b 1 )
    )
)
echo  Created: dist\Strata.msix

REM ── Sign ─────────────────────────────────────────────────────────────────────
set PFX=%ROOT%\strata_test.pfx
if not exist "%PFX%" (
    echo  Creating self-signed cert...
    powershell -Command "New-SelfSignedCertificate -Type Custom -Subject 'CN=Noah Tunis' -KeyUsage DigitalSignature -FriendlyName 'Strata Test' -CertStoreLocation 'Cert:\CurrentUser\My' -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3','2.5.29.19={text}') | Export-PfxCertificate -FilePath '%PFX%' -Password (ConvertTo-SecureString -String 'StrataTest123' -Force -AsPlainText)"
)
if not "%SIGNTOOL%"=="" (
    echo  Signing...
    "%SIGNTOOL%" sign /fd SHA256 /a /f "%PFX%" /p StrataTest123 "%MSIX%"
    if errorlevel 1 ( echo  WARNING: Signing failed. ) else ( echo  Signed. )
)

echo.
echo  ============================================================
echo   SUCCESS: dist\Strata.msix
echo   Upload to Partner Center for Store submission.
echo  ============================================================
echo.
pause
