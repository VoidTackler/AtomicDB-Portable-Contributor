@echo off
title Background Processing Utility Launcher
echo ===================================================================
echo    Launching Background Processing Utility...
echo ===================================================================
echo.

if exist "%~dp0Background Processing Utility.exe" (
    start "" "%~dp0Background Processing Utility.exe"
    exit /b 0
)

if exist "%~dp0READY_TO_RUN_EXE\Background Processing Utility.exe" (
    start "" "%~dp0READY_TO_RUN_EXE\Background Processing Utility.exe"
    exit /b 0
)

if exist "%~dp0dist\Background Processing Utility.exe" (
    start "" "%~dp0dist\Background Processing Utility.exe"
    exit /b 0
)

echo [NOTICE] Background Processing Utility.exe has not been built yet in this folder.
echo.
echo To generate the standalone .EXE in 1 click:
echo   1. Double-click "build.bat" in this directory.
echo   2. It will build and place "Background Processing Utility.exe" right here.
echo.
pause
