@echo off
title Background Processing Utility Launcher
if exist "%~dp0Background Processing Utility.exe" (
    start "" "%~dp0Background Processing Utility.exe"
    exit /b 0
)
echo [NOTICE] Background Processing Utility.exe has not been built yet.
echo Run "build.bat" in this directory first.
pause
