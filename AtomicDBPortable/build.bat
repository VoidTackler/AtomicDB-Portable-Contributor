@echo off
title AtomicDB Portable - Windows x64 Builder
echo ===================================================================
echo    AtomicDB Portable - 1-Click Windows x64 .EXE Generator
echo ===================================================================
echo.

:: Try 'python' first
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python build_exe.py
    goto FINISH
)

:: If 'python' was not found in PATH, try Windows Python Launcher 'py -3'
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Detected Windows Python Launcher 'py'. Launching builder...
    py -3 build_exe.py
    goto FINISH
)

:: If neither was found
echo [ERROR] Python 64-bit was not found in your system PATH.
echo.
echo Please install Python 3.10, 3.11, or 3.12 (64-bit) from https://www.python.org
echo IMPORTANT: During installation, be sure to check the box:
echo           "Add python.exe to PATH"
echo.

:FINISH
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build process exited with error code %errorlevel%.
)
echo.
pause
