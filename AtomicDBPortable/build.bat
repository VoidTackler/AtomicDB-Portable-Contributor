@echo off
title Background Processing Utility - Windows x64 Builder
echo ===================================================================
echo    Background Processing Utility - 1-Click .EXE Generator
echo ===================================================================
echo.

:: Try 'python' first
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python build_exe.py
    set "BUILD_ERR=%errorlevel%"
    goto CHECK_RESULT
)

:: If 'python' was not found in PATH, try Windows Python Launcher 'py -3'
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Detected Windows Python Launcher 'py'. Launching builder...
    py -3 build_exe.py
    set "BUILD_ERR=%errorlevel%"
    goto CHECK_RESULT
)

:: If neither was found
set "BUILD_ERR=1"
echo [ERROR] Python 64-bit was not found in your system PATH.
echo.
echo Please install Python 3.10, 3.11, or 3.12 (64-bit) from https://www.python.org
echo IMPORTANT: During installation, be sure to check the box:
echo           "Add python.exe to PATH"
echo.

:CHECK_RESULT
if %BUILD_ERR% neq 0 (
    echo.
    echo [ERROR] Build process exited with error code %BUILD_ERR%. Keeping source/build files for troubleshooting.
    echo.
    pause
    exit /b %BUILD_ERR%
)

if not exist "Background Processing Utility.exe" (
    echo.
    echo [ERROR] Background Processing Utility.exe was not found after build. Skipping cleanup.
    echo.
    pause
    exit /b 1
)

:: Verified post-build cleanup of excess setup/build/temp/redundant .bin files
if exist "build" rd /s /q "build" >nul 2>&1
if exist "dist" rd /s /q "dist" >nul 2>&1
if exist "temp" rd /s /q "temp" >nul 2>&1
if exist ".pytest_cache" rd /s /q ".pytest_cache" >nul 2>&1
if exist "src" rd /s /q "src" >nul 2>&1
if exist "worker" rd /s /q "worker" >nul 2>&1
if exist "tests" rd /s /q "tests" >nul 2>&1
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" >nul 2>&1
del /s /q *.pyc *.pyo *.tmp *.part *.bak *.old *.bin >nul 2>&1
for %%f in (AtomicDBPortable.spec AtomicDBPortable.py AtomicDB.exe READY_TO_RUN_EXE\AtomicDB.exe requirements.txt build.ps1 build_exe.py README.md download_dependencies.py download_dependencies.bat READY_TO_RUN_EXE\download_dependencies.bat) do @if exist "%%f" del /q "%%f" >nul 2>&1

echo.
echo [SUCCESS] Standalone single file Background Processing Utility.exe ready! Unnecessary setup/build/temp/.bin files removed.
echo.
pause
:: Remove build.bat itself once the build is complete
(goto) 2>nul & del "%~f0"

