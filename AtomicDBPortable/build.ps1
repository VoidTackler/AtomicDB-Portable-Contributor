<#
.SYNOPSIS
    Background Processing Utility - Windows x64 Automated Single-EXE Build Script
#>

param(
    [string]$PythonExe = "python.exe",
    [switch]$SkipTests = $false,
    [switch]$Clean = $false
)

$ErrorActionPreference = "Stop"

Write-Host "[1/5] Verifying Python x64 Environment..." -ForegroundColor Yellow
$pyVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} ({sys.maxsize > 2**32 and \"64-bit\" or \"32-bit\"})')"
if ($pyVersion -notmatch "64-bit") {
    Write-Error "A 64-bit Python installation is strictly required."
    exit 1
}

Write-Host "[2/5] Installing build and runtime dependencies..." -ForegroundColor Yellow
& $PythonExe -m pip install -r requirements.txt

if (-not $SkipTests) {
    Write-Host "[3/5] Running automated test suite..." -ForegroundColor Yellow
    & $PythonExe -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if ($Clean) {
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
}

Write-Host "[4/5] Building single-file executable via AtomicDBPortable.spec..." -ForegroundColor Yellow
& $PythonExe -m PyInstaller --noconfirm AtomicDBPortable.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[5/5] Finalizing single Background Processing Utility.exe & cleaning build artifacts..." -ForegroundColor Yellow
$exeName = "Background Processing Utility.exe"
$singleExe = "dist/$exeName"
if (-not (Test-Path $singleExe) -or ((Get-Item $singleExe).Length -le 0)) {
    Write-Error "Compiled $exeName is missing or empty! Skipping cleanup."
    exit 1
}

if (Test-Path $exeName) { Remove-Item -Force $exeName }
Move-Item $singleExe $exeName -Force
if (Test-Path "READY_TO_RUN_EXE/$exeName") { Remove-Item -Force "READY_TO_RUN_EXE/$exeName" }

if (-not (Test-Path $exeName) -or ((Get-Item $exeName).Length -le 0)) {
    Write-Error "Target $exeName verification failed!"
    exit 1
}

foreach ($d in @("build", "dist", "temp", ".pytest_cache", "src", "worker", "tests")) {
    if (Test-Path $d) { Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue }
}
foreach ($f in @("AtomicDBPortable.spec", "AtomicDBPortable.py", "AtomicDB.exe", "READY_TO_RUN_EXE/AtomicDB.exe", "requirements.txt", "build.bat", "build_exe.py", "README.md", "download_dependencies.py", "download_dependencies.bat", "READY_TO_RUN_EXE/download_dependencies.bat")) {
    if (Test-Path $f) { Remove-Item -Force $f -ErrorAction SilentlyContinue }
}
Get-ChildItem -Path . -Recurse -Include "__pycache__", ".pytest_cache" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -Include "*.pyc", "*.pyo", "*.tmp", "*.part", "*.bak", "*.old", "*.bin" | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "BUILD COMPLETE: $exeName (single copy ready in root folder)" -ForegroundColor Green
