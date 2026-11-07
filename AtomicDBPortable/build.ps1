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

# 6. Assemble Self-Contained USB Bundle
Write-Host "[6/6] Assembling portable USB folder structure..." -ForegroundColor Yellow
$distTarget = "dist/AtomicDBPortable"

# Ensure essential USB directories exist
New-Item -ItemType Directory -Force -Path "$distTarget/engine" | Out-Null
New-Item -ItemType Directory -Force -Path "$distTarget/engine/backup" | Out-Null
New-Item -ItemType Directory -Force -Path "$distTarget/worker" | Out-Null
New-Item -ItemType Directory -Force -Path "$distTarget/config" | Out-Null
New-Item -ItemType Directory -Force -Path "$distTarget/logs" | Out-Null

# Copy upstream worker and docs
Copy-Item "worker/atomicdb_worker.py" "$distTarget/worker/" -Force
Copy-Item "README.md" "$distTarget/" -Force

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "   BUILD COMPLETE: Self-Contained USB Bundle Ready!       " -ForegroundColor Green
Write-Host "   Location: $distTarget                                  " -ForegroundColor Green
Write-Host "   Simply copy the contents of '$distTarget' onto any     " -ForegroundColor Green
Write-Host "   FAT32/NTFS/exFAT USB thumb drive and run .exe directly." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
