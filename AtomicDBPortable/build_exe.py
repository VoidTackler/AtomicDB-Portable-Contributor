#!/usr/bin/env python3
"""
Background Processing Utility - Automated Single-EXE Packager
Builds one standalone Windows x64 .exe in the project folder and cleans build artifacts.
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
    print("[1/5] Verifying Python Environment...")
    if sys.maxsize <= 2**32:
        print("\n[ERROR] 64-bit Python is strictly required to build Windows x64 binaries.")
        sys.exit(1)
    if sys.version_info < (3, 8):
        print("\n[ERROR] Python 3.8+ is required.")
        sys.exit(1)
    print(f"Detected Python {sys.version.split()[0]} (64-bit)")

    # 2. Check PyInstaller availability
    print("\n[2/5] Checking PyInstaller & build dependencies...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    req_file = os.path.join(base_dir, "requirements.txt")
    has_pyinstaller = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0

    if not has_pyinstaller:
        print("Installing build dependencies via pip...")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file])
        if res.returncode != 0:
            print("\n[ERROR] Failed to install dependencies via pip.")
            sys.exit(res.returncode)
    else:
        print("PyInstaller is ready.")

    # 3. Clean previous build artifacts
    print("\n[3/5] Cleaning previous build folders...")
    build_dir = os.path.join(base_dir, "build")
    dist_dir = os.path.join(base_dir, "dist")
    shutil.rmtree(build_dir, ignore_errors=True)
    for old_sub in ("AtomicDBPortable", "Background Processing Utility"):
        shutil.rmtree(os.path.join(dist_dir, old_sub), ignore_errors=True)

    # 4. Run PyInstaller using AtomicDBPortable.spec
    print("\n[4/5] Compiling 'Background Processing Utility.exe' via PyInstaller...")
    spec_file = os.path.join(base_dir, "AtomicDBPortable.spec")
    res = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", spec_file], cwd=base_dir)
    if res.returncode != 0:
        print("\n[ERROR] PyInstaller compilation failed!")
        sys.exit(res.returncode)

    # 5. Move compiled .exe to single location in project root (only ONE copy) & clean up
    print("\n[5/5] Finalizing single executable & cleaning up build files...")
    exe_filename = "Background Processing Utility.exe"
    single_exe_path = os.path.join(dist_dir, exe_filename)
    if not os.path.exists(single_exe_path) or os.path.getsize(single_exe_path) <= 0:
        print(f"\n[ERROR] Compiled {exe_filename} is missing or empty! Skipping cleanup.")
        sys.exit(1)

    root_exe_path = os.path.join(base_dir, exe_filename)
    if os.path.exists(root_exe_path):
        os.remove(root_exe_path)
    shutil.move(single_exe_path, root_exe_path)

    # Ensure no duplicate .exe exists in READY_TO_RUN_EXE
    dup_ready_exe = os.path.join(base_dir, "READY_TO_RUN_EXE", exe_filename)
    if os.path.exists(dup_ready_exe):
        os.remove(dup_ready_exe)

    if not os.path.exists(root_exe_path) or os.path.getsize(root_exe_path) <= 0:
        print(f"\n[ERROR] Verification of {exe_filename} failed! Skipping cleanup.")
        sys.exit(1)

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
            except Exception:
                pass

    temp_and_redundant_exts = (".pyc", ".pyo", ".tmp", ".part", ".bak", ".old", ".bin")
    for root, dirs, files in os.walk(base_dir):
        for d in list(dirs):
            if d in ("__pycache__", ".pytest_cache"):
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                dirs.remove(d)
        for f in files:
            if f.lower().endswith(temp_and_redundant_exts):
                try:
                    os.remove(os.path.join(root, f))
                except Exception:
                    pass

    try:
        self_path = os.path.abspath(__file__)
        if os.path.exists(self_path):
            os.remove(self_path)
    except Exception:
        pass

    print("\n" + "=" * 65)
    print(f"   BUILD COMPLETE: {root_exe_path}")
    print("=" * 65)
    print("\nKept runtime essentials:")
    print(f"  -> {exe_filename}, account.txt, RUN_ATOMICDB.bat, config/, logs/")


if __name__ == "__main__":
    main()
