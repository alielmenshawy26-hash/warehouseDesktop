@echo off
REM Run ONCE on the MAIN warehouse PC: right-click -> Run as administrator
net session >nul 2>&1
if errorlevel 1 (
  echo.
  echo   Right-click this file and choose "Run as administrator".
  echo.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0server_setup.ps1"
echo.
pause
