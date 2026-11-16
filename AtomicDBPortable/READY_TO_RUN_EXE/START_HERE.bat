@echo off
title Background Processing Utility
if exist "%~dp0Background Processing Utility.exe" (
    start "" "%~dp0Background Processing Utility.exe"
    exit /b 0
)
echo [ERROR] Background Processing Utility.exe not found in this folder.
echo Please run build.bat from the parent directory first.
pause
