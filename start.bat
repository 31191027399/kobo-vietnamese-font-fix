@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 server.py
    goto :done
)

where python >nul 2>nul
if %errorlevel%==0 (
    python server.py
    goto :done
)

echo.
echo Python 3 was not found.
echo Install it from https://www.python.org/downloads/ and tick
echo "Add python.exe to PATH" during setup, then run this file again.
echo.
pause

:done
endlocal
