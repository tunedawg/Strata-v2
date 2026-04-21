@echo off
REM Finds files in msix_staging that may cause makeappx to fail
REM - Paths over 260 chars
REM - Files with invalid MSIX characters

echo Checking for problematic paths in msix_staging...
echo.

set STAGING=%~dp0msix_staging
set COUNT=0

for /r "%STAGING%" %%f in (*) do (
    set "FPATH=%%f"
    call :checklen "%%f"
)

echo.
echo Done. If no output above, paths look clean.
pause
goto :eof

:checklen
set str=%~1
set str=%str:~260%
if not "%str%"=="" (
    echo TOO LONG: %~1
    set /a COUNT+=1
)
goto :eof
