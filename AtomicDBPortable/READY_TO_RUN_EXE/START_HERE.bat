@echo off
title AtomicDB Portable
if exist "%~dp0AtomicDB.exe" (
    start "" "%~dp0AtomicDB.exe"
    exit /b 0
)
echo [ERROR] AtomicDB.exe not found in this folder.
echo Please run build.bat from the parent directory first.
pause
