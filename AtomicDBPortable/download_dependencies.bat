@echo off
setlocal
title AtomicDB Portable - USB Dependency Downloader
echo ===================================================================
echo    AtomicDB Portable - Pre-download Dependencies to USB
echo ===================================================================
echo This tool downloads official Atomic Stockfish binaries and optional
echo tablebases directly to this folder, leaving ZERO trace on the PC.
echo.

python download_dependencies.py %*

echo.
echo Press any key to exit...
pause >nul
