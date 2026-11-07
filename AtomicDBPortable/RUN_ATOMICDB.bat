@echo off
title AtomicDB Portable Launcher
echo ===================================================================
echo    Launching AtomicDB Portable Client...
echo ===================================================================
echo.

if exist "%~dp0AtomicDB.exe" (
    start "" "%~dp0AtomicDB.exe"
    exit /b 0
)

if exist "%~dp0READY_TO_RUN_EXE\AtomicDB.exe" (
    start "" "%~dp0READY_TO_RUN_EXE\AtomicDB.exe"
    exit /b 0
)

if exist "%~dp0dist\AtomicDBPortable.exe" (
    start "" "%~dp0dist\AtomicDBPortable.exe"
    exit /b 0
)

echo [NOTICE] AtomicDB.exe has not been built yet in this folder.
echo.
echo To generate the standalone .EXE in 1 click:
echo   1. Double-click "build.bat" in this directory.
echo   2. It will build and place "AtomicDB.exe" right here.
echo.
pause
