"""
AtomicDB Portable - Main Executable Entrypoint
Launches the native Windows GUI or headless supervisor for the distributed computing client.
"""

import os
import sys
import time
import argparse
import logging

try:
    from .configuration import PortableConfig, get_base_dir
    from .logging_manager import setup_portable_logging
    from .security import SecurityManager
    from .resource_manager import ResourceManager
    from .engine_manager import EngineManager
    from .worker_manager import WorkerManager
except (ImportError, ValueError):
    # Running directly as top-level script or compiled by PyInstaller
    from configuration import PortableConfig, get_base_dir
    from logging_manager import setup_portable_logging
    from security import SecurityManager
    from resource_manager import ResourceManager
    from engine_manager import EngineManager
    from worker_manager import WorkerManager

def main():
    # 0. Check if invoked as internal worker subprocess by compiled .exe
    if len(sys.argv) > 1 and sys.argv[1] == "--exec-worker":
        base_dir = get_base_dir()
        try:
            os.chdir(base_dir)
        except Exception:
            pass
        os.environ["ATOMICDB_PORTABLE_ROOT"] = base_dir
        os.environ["ATOMICDB_SYZYGY_DIR"] = os.path.join(base_dir, "syzygy-345")
        portable_temp = os.path.join(base_dir, "temp")
        os.makedirs(portable_temp, exist_ok=True)
        os.environ["TEMP"] = portable_temp
        os.environ["TMP"] = portable_temp

        worker_script = os.path.join(base_dir, "worker", "atomicdb_worker.py")
        if not os.path.exists(worker_script):
            # Try PyInstaller temporary bundled directory if frozen
            if hasattr(sys, '_MEIPASS'):
                worker_script = os.path.join(sys._MEIPASS, "worker", "atomicdb_worker.py")

        # Forward arguments to atomicdb_worker
        forward_args = list(sys.argv[2:])
        # User requirement: ensure no tablebase is always enabled by default
        if "--no-fetch-syzygy" not in forward_args and not any(a.startswith("--syzygy") for a in forward_args):
            forward_args.append("--no-fetch-syzygy")

        sys.argv = [worker_script] + forward_args
        import runpy
        runpy.run_path(worker_script, run_name="__main__")
        sys.exit(0)

    parser = argparse.ArgumentParser(description="AtomicDB Portable Client (Windows x64)")
    parser.add_argument("--headless", action="store_true", help="Run without graphical user interface")
    parser.add_argument("--verify-only", action="store_true", help="Verify engine checksums and exit")
    parser.add_argument("--mode", type=str, choices=["Adaptive", "Balanced", "Maximum", "Custom"], help="Override CPU mode")
    args = parser.parse_args()

    base_dir = get_base_dir()
    logger = setup_portable_logging(base_dir)
    logger.info("================================================================")
    logger.info("   Starting AtomicDB Portable Client (Windows x64 Distribution)  ")
    logger.info(f"   Base Directory: {base_dir}")
    logger.info("================================================================")

    # Initialize Subsystems
    config = PortableConfig()
    security = SecurityManager()
    resource_mgr = ResourceManager(mode=args.mode or config.get("resources", "cpu_mode", default="Adaptive"))
    
    engine_dir = config.get_path("engine")
    engine_mgr = EngineManager(engine_dir)

    worker_script = config.get_path("worker/atomicdb_worker.py")
    python_bin = sys.executable
    worker_mgr = WorkerManager(python_bin, worker_script)

    # Handle verify-only CLI argument
    if args.verify_only:
        selected_binary = config.get("engine", "selected_binary", default="atomic-stockfish-x64-avx2.exe")
        bin_path = os.path.join(engine_dir, selected_binary)
        verified, msg = engine_mgr.verify_binary(bin_path)
        logger.info(f"Engine verification: {msg}")
        sys.exit(0 if verified else 1)

    # Determine whether to launch GUI or Headless
    # Check if GUI is requested and PySide6 is available
    use_gui = not args.headless
    if use_gui:
        try:
            from PySide6.QtWidgets import QApplication
            from .gui import MainWindow
            app = QApplication(sys.argv)
            window = MainWindow(config, resource_mgr, worker_mgr, engine_mgr, security)
            window.show()
            sys.exit(app.exec())
        except (ImportError, RuntimeError) as e:
            logger.warning(f"Could not initialize PySide6 GUI ({e}). Falling back to headless supervisor mode.")
            use_gui = False

    if not use_gui:
        # Headless supervisor loop
        logger.info("Operating in headless supervisor mode (standalone, zero server requirements).")
        user = config.get("openbench", "username") or "PortableExe"
        enc_pass = config.get("openbench", "password_encrypted")
        pwd = security.caesar_decrypt(enc_pass) if enc_pass else "ExePassword"
        server = config.get("openbench", "server", default="https://belzedar.duckdns.org")

        threads, hash_mb = resource_mgr.compute_allocation()
        logger.info(f"Starting worker in headless mode (user={user}, threads={threads}, hash={hash_mb}MB)...")
        worker_mgr.start_worker(user, pwd, server, threads, hash_mb)

        try:
            while True:
                time.sleep(5.0)
                snapshot = resource_mgr.get_system_snapshot(worker_mgr.current_pid)
                # Adaptive load management
                resource_mgr.update_adaptive_state(snapshot["system_cpu_pct"])
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Stopping worker...")
            worker_mgr.stop_worker()
            sys.exit(0)
            logger.info("Keyboard interrupt received. Stopping worker...")
            worker_mgr.stop_worker()
            sys.exit(0)

if __name__ == "__main__":
    main()
