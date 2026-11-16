<#
.SYNOPSIS
    AtomicDB Portable - Windows x64 Automated PyInstaller Build Script
.DESCRIPTION
    Builds a completely self-contained, relocatable onedir distribution for USB deployment.
    Requires 64-bit Windows with Python 3.10+ installed.
#>

param(
    [string]$PythonExe = "python.exe",
    [switch]$SkipTests = $false,
    [switch]$Clean = $false
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   AtomicDB Portable - Windows x64 Build System          " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Environment Verification
Write-Host "[1/6] Verifying Python x64 Environment..." -ForegroundColor Yellow
$pyVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} ({sys.maxsize > 2**32 and \"64-bit\" or \"32-bit\"})')"
Write-Host "Detected Python: $pyVersion" -ForegroundColor Green

if ($pyVersion -notmatch "64-bit") {
    Write-Error "A 64-bit Python installation is strictly required to build Windows x64 binaries."
    exit 1
}

# 2. Dependency Installation
Write-Host "[2/6] Installing build and runtime dependencies..." -ForegroundColor Yellow
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r requirements.txt

# 3. Running Automated Tests
if (-not $SkipTests) {
    Write-Host "[3/6] Running automated test suite before packaging..." -ForegroundColor Yellow
    & $PythonExe -m pytest tests/ -v
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Automated test suite failed! Aborting packaging to prevent broken release."
        exit $LASTEXITCODE
    }
    Write-Host "All tests passed successfully." -ForegroundColor Green
} else {
    Write-Host "[3/6] Skipping tests as requested." -ForegroundColor DarkGray
}

# 4. Clean previous builds if requested
if ($Clean) {
    Write-Host "[4/6] Cleaning legacy build artifacts..." -ForegroundColor Yellow
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
}

# 5. Execute PyInstaller Onedir Packaging via Spec File
Write-Host "[5/6] Executing PyInstaller Onedir Packaging via AtomicDBPortable.spec..." -ForegroundColor Yellow
& $PythonExe -m PyInstaller --clean --noconfirm AtomicDBPortable.spec

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed."
    exit $LASTEXITCODE
}

# 6. Assemble Standalone Single-File .EXE & Cleanup Excess Files
Write-Host "[6/6] Finalizing standalone AtomicDB.exe and cleaning excess build files..." -ForegroundColor Yellow
$singleExe = "dist/AtomicDBPortable.exe"
if (-not (Test-Path $singleExe) -or ((Get-Item $singleExe).Length -le 0)) {
    Write-Error "Compiled AtomicDBPortable.exe is missing or empty! Skipping cleanup."
    exit 1
}

Copy-Item $singleExe "AtomicDB.exe" -Force
New-Item -ItemType Directory -Force -Path "READY_TO_RUN_EXE" | Out-Null
New-Item -ItemType Directory -Force -Path "READY_TO_RUN_EXE/config" | Out-Null
New-Item -ItemType Directory -Force -Path "READY_TO_RUN_EXE/engine" | Out-Null
New-Item -ItemType Directory -Force -Path "READY_TO_RUN_EXE/logs" | Out-Null
Copy-Item $singleExe "READY_TO_RUN_EXE/AtomicDB.exe" -Force
if (Test-Path "config/settings.json") {
    Copy-Item "config/settings.json" "READY_TO_RUN_EXE/config/settings.json" -Force
}

if (-not (Test-Path "AtomicDB.exe") -or ((Get-Item "AtomicDB.exe").Length -le 0)) {
    Write-Error "Target AtomicDB.exe verification failed! Skipping cleanup."
    exit 1
}

# Verified post-build cleanup of unnecessary setup/build/temp/redundant .bin files
$unnecessaryDirs = @("build", "dist", "temp", ".pytest_cache", "src", "worker", "tests")
foreach ($d in $unnecessaryDirs) {
    if (Test-Path $d) { Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue }
}

$unnecessaryFiles = @(
    "AtomicDBPortable.spec",
    "AtomicDBPortable.py",
    "requirements.txt",
    "build.bat",
    "build_exe.py",
    "README.md",
    "download_dependencies.py",
    "download_dependencies.bat",
    "READY_TO_RUN_EXE/download_dependencies.bat"
)
foreach ($f in $unnecessaryFiles) {
    if (Test-Path $f) { Remove-Item -Force $f -ErrorAction SilentlyContinue }
}

Get-ChildItem -Path . -Recurse -Include "__pycache__", ".pytest_cache" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -Include "*.pyc", "*.pyo", "*.tmp", "*.part", "*.bak", "*.old", "*.bin" | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "   BUILD COMPLETE: Standalone Single-File AtomicDB.exe!   " -ForegroundColor Green
Write-Host "   Location: AtomicDB.exe (and READY_TO_RUN_EXE/)         " -ForegroundColor Green
Write-Host "   Unnecessary setup/build/temp/.bin files cleaned up.    " -ForegroundColor Green
Write-Host "   Copy AtomicDB.exe to your USB stick and run directly.  " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

