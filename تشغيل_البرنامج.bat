@echo off
chcp 65001 >nul
py -3 warehouse_app.py
if errorlevel 1 (echo.
echo If Python is not installed, install Python 3 from python.org and select Add Python to PATH.
pause)
