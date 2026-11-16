# AtomicDB Portable (Windows x64)

Self-contained, portable client for contributing computing cycles to the [AtomicDB](https://belzedar.duckdns.org) atomic chess book and analysis network.

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

- **Standalone Single File & Post-Build Cleanup**: `build.bat` / `build_exe.py` outputs a single standalone `AtomicDB.exe` and automatically cleans up all intermediate build artifacts, `dist/`, `build/`, and bytecode caches.
- **Zero Footprint on Host**: All temporary files, engine binaries, and logs are kept strictly on the USB storage drive (zero trace left on host `C:` drive).
- **Adaptive Mode with 50% Cores Reserved**: Leaves 50% of the computer's cores off (rounded up to 1 if below one), updating on an unobtrusive 20-second hysteresis cycle.
- **High-Speed Telemetry (0.8s Refresh)**: Real-time worker and system CPU/RAM monitoring refreshes every 0.8 seconds.
- **Diagnostic Data Dashboard & Session Graphs**:
  - **Session Statistics**: Tasks completed, total nodes, current NPS, average NPS, and digital session uptime (saved in `logs/session_statistics.log`).
  - **Current Task Monitor**: Real-time task ID, budget nodes, line being calculated (candidate moves / PV / FEN), and remaining ETA based on the average NPS of the last 3 completed tasks (saved in `logs/current_task.log`).
  - **Lifetime Statistics (`logs/lifetime_statistics.txt`)**: Permanently tracks total tasks, lifetime nodes, lifetime average NPS, accumulated runtime, CPU hours, and total sessions across all portable runs. **Log files are strictly never cleared**.
  - **Real-time Session Graphs**: Native vector-drawn visual graphs for CPU usage over time (System vs Worker %), RAM usage over time (Worker RSS vs Available MB), and NPS per task speed trend.
- **Persistent Local USB Analytics**: Detailed execution logs and performance metrics (`history.json`, `analytics.json`, `crashes.log`, `session_statistics.log`, `current_task.log`, `lifetime_statistics.txt`) stored right on the USB drive.
- **Emergency Local Stop**: A single-click override allows the local operator to instantly halt all analysis.
- **Offline Dependency Pre-Downloader**: Double-click `download_dependencies.bat` to pre-fetch required engine files directly to your USB drive before connecting to target machines.

