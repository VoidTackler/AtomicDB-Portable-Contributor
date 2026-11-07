#!/usr/bin/env python3
"""
AtomicDB Portable - Automated Executable & USB Packager
Cross-platform, robust packaging runner that eliminates Windows batch script parsing issues.
"""

import os
import sys
import shutil
import subprocess

def print_banner(msg: str):
    print("\n" + "=" * 65)
    print(f"   {msg}")
    print("=" * 65 + "\n")

def main():
    print_banner("AtomicDB Portable - Windows x64 .EXE Generator")

    # 1. Check Python version and 64-bit architecture
    print("[1/5] Verifying Python Environment...")
    is_64bit = sys.maxsize > 2**32
    arch_str = "64-bit" if is_64bit else "32-bit"
    print(f"Detected Python {sys.version.split()[0]} ({arch_str})")

    if not is_64bit:
        print("\n[ERROR] 64-bit Python is strictly required to build Windows x64 binaries.")
        print("Please install 64-bit Python 3.10+ from https://www.python.org\n")
        sys.exit(1)

    if sys.version_info < (3, 8):
        print("\n[ERROR] Python 3.8+ is required.\n")
        sys.exit(1)

    # 2. Check dependencies (PyInstaller, PySide6, etc.)
    print("\n[2/5] Checking PyInstaller & build dependencies...")
    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    
    # Check if PyInstaller is already installed and usable
    has_pyinstaller = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    ).returncode == 0

    if not has_pyinstaller:
        print("Installing build dependencies via pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=False)
        res = subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file])
        if res.returncode != 0:
            print("\n[ERROR] Failed to install dependencies via pip.")
            print("Please run manually: python -m pip install -r requirements.txt")
            sys.exit(res.returncode)
    else:
        print("PyInstaller is already installed and ready.")

    # 3. Clean previous build artifacts
    print("\n[3/5] Cleaning previous build folders...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(base_dir, "build")
    dist_dir = os.path.join(base_dir, "dist")

    shutil.rmtree(build_dir, ignore_errors=True)
    # Don't delete entire dist if locked, just clean dist/AtomicDBPortable
    target_dist = os.path.join(dist_dir, "AtomicDBPortable")
    shutil.rmtree(target_dist, ignore_errors=True)

    # 4. Run PyInstaller using AtomicDBPortable.spec
    print("\n[4/5] Compiling AtomicDBPortable.exe via PyInstaller...")
    spec_file = os.path.join(base_dir, "AtomicDBPortable.spec")
    
    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        spec_file
    ]

    res = subprocess.run(pyinstaller_cmd, cwd=base_dir)
    if res.returncode != 0:
        print("\n[ERROR] PyInstaller compilation failed!")
        sys.exit(res.returncode)

    # 5. Place the compiled .exe in root and READY_TO_RUN_EXE so it is immediately obvious
    print("\n[5/5] Finalizing standalone executable placement...")
    single_exe_path = os.path.join(dist_dir, "AtomicDBPortable.exe")
    
    # 1. Place directly in project root folder as AtomicDB.exe (easiest to find!)
    root_exe_path = os.path.join(base_dir, "AtomicDB.exe")
    if os.path.exists(single_exe_path):
        shutil.copy2(single_exe_path, root_exe_path)
    
    # 2. Place in dedicated READY_TO_RUN_EXE folder
    ready_folder = os.path.join(base_dir, "READY_TO_RUN_EXE")
    os.makedirs(os.path.join(ready_folder, "config"), exist_ok=True)
    os.makedirs(os.path.join(ready_folder, "engine"), exist_ok=True)
    os.makedirs(os.path.join(ready_folder, "logs"), exist_ok=True)
    
    ready_exe_path = os.path.join(ready_folder, "AtomicDB.exe")
    if os.path.exists(single_exe_path):
        shutil.copy2(single_exe_path, ready_exe_path)
    
    src_config = os.path.join(base_dir, "config", "settings.json")
    if os.path.exists(src_config):
        shutil.copy2(src_config, os.path.join(ready_folder, "config", "settings.json"))

    downloader_bat = os.path.join(base_dir, "download_dependencies.bat")
    if os.path.exists(downloader_bat):
        shutil.copy2(downloader_bat, os.path.join(ready_folder, "download_dependencies.bat"))

    print("\n" + "=" * 65)
    print("   BUILD COMPLETE! YOUR EXECUTABLE IS READY TO RUN")
    print("=" * 65)
    print(f"\n[1] Directly in this folder:  {root_exe_path}")
    print(f"[2] Ready-to-copy USB folder: {ready_exe_path}")
    print("\nHow to run:")
    print("  -> Just double-click 'AtomicDB.exe' or 'RUN_ATOMICDB.bat'")
    print("  -> Zero Python, pip, or administrator privileges required!\n")

if __name__ == "__main__":
    main()
