# Background Processing Utility (Windows x64)

Self-contained portable client for contributing computing cycles to AtomicDB (`https://belzedar.duckdns.org`).
Runs directly from a USB drive on Windows 10/11 x64 without requiring Python, pip, or administrator privileges.

## Quick Start

1. Double-click **`Background Processing Utility.exe`** (or **`RUN_ATOMICDB.bat`**).
2. Configure options in the **`API Parameters`** tab if needed, then click **`Start`**.
3. Optional account override: set `USERNAME=` and `PASSWORD=` in `account.txt` (leave blank for built-in default attribution).

## Building the Standalone `.EXE` (1-Click)

1. Double-click **`build.bat`**.
2. PyInstaller compiles a single **`Background Processing Utility.exe`** in this directory and removes temporary build/source files.

## Features

- **Single Standalone Executable**: Builds one `Background Processing Utility.exe` copy directly in the folder (no duplicate `.exe` copies) with unused Qt modules excluded for smaller size and faster builds.
- **3 Full-Screen Tabs**: `API Parameters`, `Live Analysis Console`, and `Graph and Analytics`.
- **1-Second Telemetry & ETA**: Real-time ETA countdown (integer steps, pauses when paused, negative when overdue), CPU %, and RAM counters update every 1 second.
- **Adaptive Resource Control**: Reserves 50% of host CPU cores in Adaptive mode with 20-second hysteresis.
- **USB-Local Analytics**: Persistent task history, NPH/Lifetime NPH, SAN calculating line with authentic openings, and live graphs stored strictly in `logs/`.
