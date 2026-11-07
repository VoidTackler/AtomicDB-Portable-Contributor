# AtomicDB Portable — Windows x64 Distributed Computing Client

**AtomicDB Portable** is a self-contained, USB-relocatable client application designed to contribute compute cycles to the [AtomicDB](https://belzedar.duckdns.org) / [OpenBench](https://github.com/Belzedar94/OpenBench) atomic chess opening book and analysis network.

It includes an enterprise-grade **Central Administrator Management Platform** allowing the software owner to remotely monitor fleet health, adjust resource budgets, issue signed commands, and review cryptographic audit trails.

---

## 1. Core Architectural Principles

1. **Zero-Dependency USB Portability**: Runs directly from any USB flash drive without requiring Python, Git, pip, C++ runtimes, or administrative privileges on the target Windows 10/11 x64 machine.
2. **Drive Letter Independence**: Resolves all engine binaries, logs, configuration, and scratch data relative to the executable root directory (`os.path.dirname(sys.executable)`).
3. **Adaptive Hardware Management**: Automatically balances CPU threads and hash memory using real-time system monitoring. If host activity spikes, thread counts are dynamically reduced using a multi-cycle hysteresis buffer to avoid CPU thrashing.
4. **Local Operator Precedence**: The computer owner always retains absolute control. Engaging the **Emergency Local Stop** overrides and rejects any remote `RESUME` commands from the central administrator.
5. **Upstream Worker Fidelity**: Strictly preserves the official `atomicdb_worker.py` argument contract:
   ```powershell
   python atomicdb_worker.py -U USER -P PASSWORD -S https://belzedar.duckdns.org -T 8 --hash 1024
   ```
   No unsupported or hallucinated flags are passed.

---

## 2. Resource Allocation Models

| Profile | CPU Threads Allocated | Hash Memory Budget | Hysteresis Response |
| :--- | :--- | :--- | :--- |
| **Adaptive (Default)** | Up to 75% of logical cores; scales down to 25% during host load | Clamped to safe available RAM minus 1.5 GB OS reserve | 3 consecutive cycles (15s) of sustained low load required before restoring compute |
| **Balanced** | ~50% of logical cores | Clamped to 50% usable RAM (up to 2048 MB) | Static allocation |
| **Maximum** | `logical_cores - 1` | Maximum safe power-of-two hash | Static allocation |
| **Custom** | User / Admin specified | User / Admin specified | Manual overrides |

### Memory Sizing Formula
Per upstream OpenBench documentation:
$$\text{RAM per instance} = \text{Hash Size} + 300\text{ MB}$$
The client guarantees at least 1,500 MB of free host RAM is preserved under all conditions.

---

## 3. Directory Structure

```text
AtomicDBPortable/
├── AtomicDBPortable.exe       # Native Windows x64 PyInstaller binary
├── config/
│   └── settings.json         # Relocatable client configuration
├── engine/
│   ├── atomic-stockfish-x64-avx2.exe
│   └── backup/               # Retention of last-known-good engine
├── worker/
│   └── atomicdb_worker.py    # Official upstream worker script
├── logs/
│   └── atomicdb_client.log   # Rotating logs confined strictly to USB
├── src/
│   ├── main.py               # Main launcher (GUI & Headless)
│   ├── gui.py                # Native PySide6 user interface
│   ├── worker_manager.py     # Subprocess supervisor
│   ├── resource_manager.py   # Adaptive CPU/RAM allocation engine
│   ├── engine_manager.py     # Instruction detection & SHA256 integrity
│   ├── management_client.py  # Central admin HTTPS polling client
│   ├── device_registration.py# One-time token enrollment
│   ├── security.py           # HMAC-SHA256, nonces, credential protection
│   └── logging_manager.py    # USB-confined log rotators
├── tests/                    # Automated unit and integration test suite
├── build.ps1                 # Windows PowerShell packaging script
├── requirements.txt          # Python runtime dependencies
└── README.md
```

---

## 4. How to Generate the `AtomicDBPortable.exe` File

The application can be compiled into a standalone Windows x64 executable using any of the following methods on a Windows 10/11 x64 machine with Python 3.10, 3.11, or 3.12 (64-bit) installed:

### Method A: 1-Click Batch Build (Easiest)
1. Open the `AtomicDBPortable` folder in Windows File Explorer.
2. Double-click **`build.bat`**.
3. The script will automatically install requirements, invoke PyInstaller with `AtomicDBPortable.spec`, and output the self-contained folder to:
   ```text
   dist\AtomicDBPortable\AtomicDBPortable.exe
   ```

### Method B: Automated PowerShell Build
Open PowerShell in the `AtomicDBPortable` directory and execute:
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1 -Clean
```

### Method C: Manual Terminal Build
```cmd
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Run PyInstaller with the provided specification
python -m PyInstaller --clean --noconfirm AtomicDBPortable.spec
```

### Resulting USB Distribution
After compilation, the folder `dist\AtomicDBPortable` contains:
- `AtomicDBPortable.exe` (Windowed GUI client, zero UAC elevation)
- `_internal\` (Bundled Python runtime, PySide6 Qt6 libraries, and dependencies)
- `worker\atomicdb_worker.py` (Official upstream worker)
- `engine\` (Engine folder for Atomic-Stockfish binaries)
- `config\` (Portable configuration)
- `logs\` (Confined execution logs)

Copy the entire `dist\AtomicDBPortable` directory onto any USB flash drive. Target computers do not require Python, compilers, Git, or administrator privileges.

---

## 5. Central Administrator Management Setup

1. Start the management dashboard:
   ```bash
   npm run dev
   ```
2. Navigate to `http://localhost:3000` to access the **AtomicDB Fleet Console**.
3. Generate an enrollment token from the dashboard.
4. On the USB client, enroll the device:
   ```powershell
   AtomicDBPortable.exe --enroll ATOMIC-ENROLL-XXXXXXXXXXXXXXXX
   ```
5. The device will appear in the fleet table and report live telemetry every 10 seconds.
