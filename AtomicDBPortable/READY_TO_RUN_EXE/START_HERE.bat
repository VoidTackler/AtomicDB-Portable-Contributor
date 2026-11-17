@echo off
title Background Processing Utility
if exist "%~dp0..\Background Processing Utility.exe" (
    start "" "%~dp0..\Background Processing Utility.exe"
    exit /b 0
)
if exist "%~dp0Background Processing Utility.exe" (
    start "" "%~dp0Background Processing Utility.exe"
    exit /b 0
)
echo [ERROR] Background Processing Utility.exe not found.
echo Please run build.bat from the parent directory first.
pause
