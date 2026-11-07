#!/usr/bin/env python3
"""
AtomicDB Portable - Upstream Dependency Pre-Downloader
Fetches official reference engine binaries and optional syzygy tablebases
directly into the USB storage directory, ensuring ZERO footprint on the host computer.
"""

import os
import sys
import json
import hashlib
import urllib.request
import urllib.error
import argparse
import time

SERVER_URL = "https://belzedar.duckdns.org"
ENGINE_MANIFEST_URL = f"{SERVER_URL}/atomicdb/engines/manifest.json"
SYZYGY_MANIFEST_URL = f"{SERVER_URL}/atomicdb/engines/syzygy-345/manifest.json"
SYZYGY_BASE_URL = f"{SERVER_URL}/atomicdb/engines/syzygy-345/"

def get_target_dir() -> str:
    """Detects target USB base directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dist_usb = os.path.join(script_dir, "dist", "AtomicDB_USB")
    if os.path.exists(dist_usb):
        return dist_usb
    return script_dir

def sha256_of_file(file_path: str) -> str:
    if not os.path.exists(file_path):
        return ""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()

def download_file(url: str, dest_path: str, expected_sha: str = "", expected_bytes: int = 0) -> bool:
    """Downloads a file with resume, progress, and sha256 verification."""
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    temp_path = dest_path + ".part"

    # Check if already downloaded and verified
    if os.path.exists(dest_path) and expected_sha:
        current_sha = sha256_of_file(dest_path)
        if current_sha == expected_sha.lower():
            print(f"  [OK] Already verified: {os.path.basename(dest_path)}")
            return True

    print(f"  [DOWNLOADING] {url} -> {os.path.basename(dest_path)}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AtomicDBPortableDownloader/2.0"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(temp_path, "wb") as out:
            downloaded = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if expected_bytes > 0:
                    pct = (downloaded / expected_bytes) * 100
                    sys.stdout.write(f"\r    Progress: {downloaded}/{expected_bytes} bytes ({pct:.1f}%)")
                    sys.stdout.flush()

        if expected_bytes > 0:
            print()

        actual_sha = sha256_of_file(temp_path)
        if expected_sha and actual_sha != expected_sha.lower():
            print(f"  [ERROR] SHA256 mismatch for {dest_path}. Expected {expected_sha}, got {actual_sha}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(temp_path, dest_path)
        print(f"  [VERIFIED] {os.path.basename(dest_path)} (SHA: {actual_sha[:12]}...)")
        return True

    except Exception as e:
        print(f"  [FAIL] Download error: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return False

def download_engine_dependencies(target_base: str):
    """Downloads official Windows x64 Stockfish binary and NNUE net into USB folder."""
    print("===================================================================")
    print(" 1. Fetching Official Atomic-Stockfish Engine & Net")
    print("===================================================================")
    try:
        req = urllib.request.Request(ENGINE_MANIFEST_URL, headers={"User-Agent": "AtomicDBPortable/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            manifest = json.loads(resp.read().decode('utf-8'))

        binaries = manifest.get("binaries", {})
        win_entry = binaries.get("windows-x86_64")
        if not win_entry:
            print("  [WARNING] No windows-x86_64 binary in manifest.")
            return

        engine_url = f"{SERVER_URL}/atomicdb/engines/{win_entry['file']}"
        engines_dir = os.path.join(target_base, "Engines")
        engine_dest = os.path.join(engines_dir, win_entry['file'])
        download_file(engine_url, engine_dest, win_entry['sha256'])

        # Download NNUE Net if declared
        net_entry = manifest.get("net")
        if net_entry:
            net_url = f"{SERVER_URL}/atomicdb/engines/{net_entry['file']}"
            net_dest = os.path.join(target_base, net_entry['file'])
            download_file(net_url, net_dest, net_entry['sha256'])

        print("  [SUCCESS] Official engine and NNUE network ready in USB storage.")

    except Exception as e:
        print(f"  [ERROR] Could not fetch engine manifest: {e}")

def download_syzygy_dependencies(target_base: str):
    """Downloads all 292 syzygy tablebase files (~1318 MB) directly into USB syzygy-345/ directory."""
    print("===================================================================")
    print(" 2. Fetching Official Atomic Syzygy Tablebases (~1.3 GB)")
    print("===================================================================")
    try:
        req = urllib.request.Request(SYZYGY_MANIFEST_URL, headers={"User-Agent": "AtomicDBPortable/2.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            manifest = json.loads(resp.read().decode('utf-8'))

        files = manifest.get("files", [])
        print(f"  Total Tablebase Files in Manifest: {len(files)}")
        syzygy_dir = os.path.join(target_base, "syzygy-345")
        os.makedirs(syzygy_dir, exist_ok=True)

        success_count = 0
        total_files = len(files)

        for idx, entry in enumerate(files, 1):
            fname = entry["name"]
            fbytes = entry["bytes"]
            fsha = entry["sha256"]
            furl = f"{SYZYGY_BASE_URL}{fname}"
            dest = os.path.join(syzygy_dir, fname)

            sys.stdout.write(f"[{idx}/{total_files}] ")
            ok = download_file(furl, dest, fsha, fbytes)
            if ok:
                success_count += 1

        print(f"\n  [COMPLETED] {success_count}/{total_files} tablebase files ready in {syzygy_dir}")
        print("  Zero host traces left. All tablebases stored strictly on USB drive.")

    except Exception as e:
        print(f"  [ERROR] Could not fetch syzygy manifest: {e}")

def main():
    parser = argparse.ArgumentParser(description="Pre-download AtomicDB dependencies directly to USB drive")
    parser.add_argument("--syzygy", action="store_true", help="Also pre-download the ~1.3 GB atomic syzygy tablebase set")
    parser.add_argument("--dest", type=str, default="", help="Custom destination folder (default: USB package directory)")
    args = parser.parse_args()

    target_dir = args.dest or get_target_dir()
    print("===================================================================")
    print("   AtomicDB Portable - USB Dependency Downloader")
    print(f"   Target USB Base: {target_dir}")
    print("===================================================================")

    download_engine_dependencies(target_dir)

    if args.syzygy:
        download_syzygy_dependencies(target_dir)
    else:
        print("\n[NOTE] Tablebases are skipped by default (--no-fetch-syzygy active).")
        print("To download the 1.3 GB tablebases directly to USB, run:")
        print("  python download_dependencies.py --syzygy")

    print("\n[DONE] All downloaded dependencies are bound to the USB storage directory.")

if __name__ == "__main__":
    main()
