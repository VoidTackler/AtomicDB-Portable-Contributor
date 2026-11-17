@echo off
title Background Processing Utility - Windows x64 Builder
echo ===================================================================
echo    Background Processing Utility - 1-Click .EXE Generator
echo ===================================================================
echo.

python --version >nul 2>&1
if %errorlevel% equ 0 (
    python build_exe.py
    set "BUILD_ERR=%errorlevel%"
    goto CHECK_RESULT
)

py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    py -3 build_exe.py
    set "BUILD_ERR=%errorlevel%"
    goto CHECK_RESULT
)

set "BUILD_ERR=1"
echo [ERROR] Python 64-bit was not found in your system PATH.
echo Install Python 3.10+ (64-bit) with "Add python.exe to PATH".

:CHECK_RESULT
if %BUILD_ERR% neq 0 (
    echo.
    echo [ERROR] Build process exited with error code %BUILD_ERR%.
    pause
    exit /b %BUILD_ERR%
)

if not exist "Background Processing Utility.exe" (
    echo.
    echo [ERROR] Background Processing Utility.exe was not found after build.
    pause
    exit /b 1
)

for %%d in (build dist temp .pytest_cache src worker tests) do @if exist "%%d" rd /s /q "%%d" >nul 2>&1
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" >nul 2>&1
del /s /q *.pyc *.pyo *.tmp *.part *.bak *.old *.bin >nul 2>&1
for %%f in (AtomicDBPortable.spec AtomicDBPortable.py AtomicDB.exe READY_TO_RUN_EXE\AtomicDB.exe "READY_TO_RUN_EXE\Background Processing Utility.exe" requirements.txt build.ps1 build_exe.py README.md download_dependencies.py download_dependencies.bat READY_TO_RUN_EXE\download_dependencies.bat) do @if exist "%%f" del /q "%%f" >nul 2>&1

echo.
echo [SUCCESS] Single standalone Background Processing Utility.exe ready!
echo.
pause
(goto) 2>nul & del "%~f0"
