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
    print_banner("Background Processing Utility - Windows x64 .EXE Generator")

    # 1. Check Python version and 64-bit architecture
    print("[1/6] Verifying Python Environment...")
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
    print("\n[2/6] Checking PyInstaller & build dependencies...")
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
    print("\n[3/6] Cleaning previous build folders...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(base_dir, "build")
    dist_dir = os.path.join(base_dir, "dist")

    shutil.rmtree(build_dir, ignore_errors=True)
    for old_sub in ("AtomicDBPortable", "Background Processing Utility"):
        shutil.rmtree(os.path.join(dist_dir, old_sub), ignore_errors=True)

    # 4. Run PyInstaller using AtomicDBPortable.spec
    print("\n[4/6] Compiling 'Background Processing Utility.exe' via PyInstaller...")
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

    # 5. Place the compiled .exe in root and READY_TO_RUN_EXE and verify integrity
    print("\n[5/6] Finalizing and verifying standalone executable...")
    exe_filename = "Background Processing Utility.exe"
    single_exe_path = os.path.join(dist_dir, exe_filename)
    if not os.path.exists(single_exe_path) or os.path.getsize(single_exe_path) <= 0:
        print(f"\n[ERROR] Compiled {exe_filename} is missing or empty! Skipping cleanup.")
        sys.exit(1)

    # 1. Place directly in project root folder
    root_exe_path = os.path.join(base_dir, exe_filename)
    shutil.copy2(single_exe_path, root_exe_path)

    # 2. Place in dedicated READY_TO_RUN_EXE folder
    ready_folder = os.path.join(base_dir, "READY_TO_RUN_EXE")
    os.makedirs(os.path.join(ready_folder, "config"), exist_ok=True)
    os.makedirs(os.path.join(ready_folder, "engine"), exist_ok=True)
    os.makedirs(os.path.join(ready_folder, "logs"), exist_ok=True)

    ready_exe_path = os.path.join(ready_folder, exe_filename)
    shutil.copy2(single_exe_path, ready_exe_path)

    src_config = os.path.join(base_dir, "config", "settings.json")
    if os.path.exists(src_config):
        shutil.copy2(src_config, os.path.join(ready_folder, "config", "settings.json"))

    src_account = os.path.join(base_dir, "account.txt")
    if os.path.exists(src_account):
        shutil.copy2(src_account, os.path.join(ready_folder, "account.txt"))

    # Verify both target EXEs exist and are non-empty before removing setup/build files
    if (
        not os.path.exists(root_exe_path) or os.path.getsize(root_exe_path) <= 0
        or not os.path.exists(ready_exe_path) or os.path.getsize(ready_exe_path) <= 0
    ):
        print(f"\n[ERROR] Verification of {exe_filename} failed! Skipping cleanup.")
        sys.exit(1)

    # 6. Delete unnecessary setup/build/temp/redundant .bin files while keeping runtime essentials
    print("\n[6/6] Cleaning up unnecessary setup, build, temp, and redundant .bin files...")

    unnecessary_dirs = [
        "build",
        "dist",
        "temp",
        ".pytest_cache",
        "src",
        "worker",
        "tests",
    ]
    for d in unnecessary_dirs:
        target = os.path.join(base_dir, d)
        if os.path.exists(target):
            shutil.rmtree(target, ignore_errors=True)
            print(f"  -> Removed {d}/")

    unnecessary_files = [
        "AtomicDBPortable.spec",
        "AtomicDBPortable.py",
        "AtomicDB.exe",
        os.path.join("READY_TO_RUN_EXE", "AtomicDB.exe"),
        "requirements.txt",
        "build.ps1",
        "README.md",
        "download_dependencies.py",
        "download_dependencies.bat",
        os.path.join("READY_TO_RUN_EXE", "download_dependencies.bat"),
    ]
    for rel_path in unnecessary_files:
        target = os.path.join(base_dir, rel_path)
        if os.path.exists(target):
            try:
                os.remove(target)
                print(f"  -> Removed {rel_path}")
            except Exception:
                pass

    # Recursively remove __pycache__, bytecode, temp files, and redundant .bin files
    cleaned_caches = 0
    cleaned_files = 0
    temp_and_redundant_exts = (".pyc", ".pyo", ".tmp", ".part", ".bak", ".old", ".bin")
    for root, dirs, files in os.walk(base_dir):
        for d in list(dirs):
            if d == "__pycache__" or d == ".pytest_cache":
                full_dir = os.path.join(root, d)
                shutil.rmtree(full_dir, ignore_errors=True)
                dirs.remove(d)
                cleaned_caches += 1
        for f in files:
            if f.lower().endswith(temp_and_redundant_exts):
                try:
                    os.remove(os.path.join(root, f))
                    cleaned_files += 1
                except Exception:
                    pass

    if cleaned_caches:
        print(f"  -> Cleaned {cleaned_caches} cache directory(ies)")
    if cleaned_files:
        print(f"  -> Cleaned {cleaned_files} temp/bytecode/redundant .bin file(s)")

    # Remove build_exe.py itself last (safe on Windows as script is already compiled in memory)
    try:
        self_path = os.path.abspath(__file__)
        if os.path.exists(self_path):
            os.remove(self_path)
            print("  -> Removed build_exe.py")
    except Exception:
        pass

    print("\n" + "=" * 65)
    print("   BUILD COMPLETE! YOUR EXECUTABLE IS READY TO RUN")
    print("=" * 65)
    print(f"\n[1] Directly in this folder:  {root_exe_path}")
    print(f"[2] Ready-to-copy USB folder: {ready_exe_path}")
    print("\nKept runtime essentials:")
    print(f"  -> {exe_filename}, account.txt, RUN_ATOMICDB.bat, READY_TO_RUN_EXE/")
    print("  -> config/, logs/, Engines/, engine/, syzygy-345/ (if present)")
    print("Status:")
    print(f"  -> Standalone single-file '{exe_filename}' generated successfully.")
    print("  -> Unnecessary setup, build, temp, and redundant .bin files removed.")
    print("  -> Zero Python, pip, or administrator privileges required!\n")

if __name__ == "__main__":
    main()

