# AtomicDB Portable (Windows x64)

Self-contained, portable client for contributing computing cycles to the [AtomicDB](https://belzedar.duckdns.org) atomic chess book and analysis network.

Entirely written by Google Gemini 3.8 Flash.

Designed for zero-trace execution from any USB flash drive on Windows 10/11 x64 systems without requiring Python, Git, pip, or administrator privileges.

---

## Quick Start (How to Run)

1. Double-click **`AtomicDB.exe`** (or **`RUN_ATOMICDB.bat`**).
2. Choose your preferred CPU Mode (Adaptive, Balanced, Maximum, or Custom).
3. Click **Start Contributing**.

The client comes pre-configured with the official contributor credentials (`PortableExe`) and connects automatically to `https://belzedar.duckdns.org`.

---

## Folder Layout

The project structure is organized so the compiled executable is immediately accessible:

```text
AtomicDBPortable/
├── AtomicDB.exe                  <- Compiled standalone Windows x64 executable (generated after build)
├── RUN_ATOMICDB.bat              <- 1-Click launcher (launches AtomicDB.exe directly)
├── build.bat                     <- 1-Click Windows .exe generator
├── download_dependencies.bat     <- Optional pre-downloader for engines
├── READY_TO_RUN_EXE/             <- Self-contained USB distribution folder
│   ├── AtomicDB.exe              <- Standalone executable ready for USB
│   ├── START_HERE.bat            <- 1-Click USB launcher
│   ├── config/settings.json      <- Portable configuration
│   └── README_USB.txt            <- Quick guide for USB users
├── config/                       <- Local settings and credentials
├── worker/                       <- Upstream atomicdb_worker.py logic
└── src/                          <- Application source code
```

---

## How to Build the `.EXE` (1-Click)

On any Windows 10/11 x64 computer with Python 3.8+ (64-bit) installed:

1. Double-click **`build.bat`**.
2. PyInstaller will compile a standalone single-file binary.
3. When finished, your executable will be placed directly in:
   - **`AtomicDB.exe`** (in this root directory)
   - **`READY_TO_RUN_EXE\AtomicDB.exe`** (in the USB-ready folder)

---

## Features

- **Zero Footprint on Host**: All temporary files, engine binaries, and logs are kept strictly on the USB storage drive (zero trace left on host `C:` drive).
- **No Tablebase by Default**: Automatically runs with `--no-fetch-syzygy` enabled to avoid downloading large tablebases to the host machine.
- **Adaptive Hardware Control**: Automatically throttles worker CPU threads if user activity spikes on the host machine to prevent system lag.
- **Emergency Local Stop**: A single-click override allows the local operator to instantly halt all analysis.
- **Offline Dependency Pre-Downloader**: Double-click `download_dependencies.bat` to pre-fetch required engine files directly to your USB drive before connecting to target machines.
