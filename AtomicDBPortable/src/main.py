"""
AtomicDB Portable - Main Executable Entrypoint
Launches the GUI or headless supervisor for the distributed computing client.
"""

import os
import sys
import time
import argparse

try:
    from .configuration import PortableConfig, get_base_dir
    from .logging_manager import setup_portable_logging
    from .resource_manager import ResourceManager
    from .engine_manager import EngineManager
    from .worker_manager import WorkerManager
    from .analytics_logger import AnalyticsLogger
except (ImportError, ValueError):
    from configuration import PortableConfig, get_base_dir
    from logging_manager import setup_portable_logging
    from resource_manager import ResourceManager
    from engine_manager import EngineManager
    from worker_manager import WorkerManager
    from analytics_logger import AnalyticsLogger


def main():
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
        if not os.path.exists(worker_script) and hasattr(sys, "_MEIPASS"):
            worker_script = os.path.join(sys._MEIPASS, "worker", "atomicdb_worker.py")

        sys.argv = [worker_script] + list(sys.argv[2:])
        import runpy
        runpy.run_path(worker_script, run_name="__main__")
        sys.exit(0)

    parser = argparse.ArgumentParser(description="Background Processing Utility")
    parser.add_argument("--headless", action="store_true", help="Run without graphical user interface")
    parser.add_argument("--verify-only", action="store_true", help="Verify engine checksums and exit")
    parser.add_argument("--mode", type=str, choices=["Adaptive", "Balanced", "Maximum", "Custom"], help="Override CPU mode")
    args = parser.parse_args()

    base_dir = get_base_dir()
    logger = setup_portable_logging(base_dir)
    logger.info("Starting Background Processing Utility (Windows x64) | Base: %s", base_dir)

    config = PortableConfig()
    resource_mgr = ResourceManager(mode=args.mode or config.get("resources", "cpu_mode", default="Adaptive"))
    engine_dir = config.get_path("engine")
    engine_mgr = EngineManager(engine_dir)
    analytics_logger = AnalyticsLogger(base_dir)
    worker_mgr = WorkerManager(sys.executable, config.get_path("worker/atomicdb_worker.py"), analytics_logger=analytics_logger)

    if args.verify_only:
        selected_binary = config.get("engine", "selected_binary", default="atomic-stockfish-x64-avx2.exe")
        verified, msg = engine_mgr.verify_binary(os.path.join(engine_dir, selected_binary))
        logger.info(f"Engine verification: {msg}")
        sys.exit(0 if verified else 1)

    if not args.headless:
        try:
            from PySide6.QtWidgets import QApplication
            try:
                from .gui import MainWindow, APP_NAME, get_default_windows_app_icon
            except (ImportError, ValueError):
                from gui import MainWindow, APP_NAME, get_default_windows_app_icon

            app = QApplication(sys.argv)
            app.setApplicationName(APP_NAME)
            app.setApplicationDisplayName(APP_NAME)
            app.setStyle("Fusion")
            default_icon = get_default_windows_app_icon()
            if default_icon and not default_icon.isNull():
                app.setWindowIcon(default_icon)

            window = MainWindow(config, resource_mgr, worker_mgr, engine_mgr, analytics_logger=analytics_logger)
            if default_icon and not default_icon.isNull():
                window.setWindowIcon(default_icon)
            window.show()
            sys.exit(app.exec())
        except (ImportError, RuntimeError) as e:
            logger.warning(f"Could not initialize PySide6 GUI ({e}). Falling back to headless mode.")

    logger.info("Operating in headless supervisor mode.")
    user, pwd = config.get_account_credentials()
    server = config.get("openbench", "server", default="https://belzedar.duckdns.org")
    threads, hash_mb = resource_mgr.compute_allocation()
    logger.info(f"Starting worker (threads={threads}, hash={hash_mb}MB)...")
    worker_mgr.start_worker(user, pwd, server, threads, hash_mb)

    try:
        while True:
            time.sleep(5.0)
            snapshot = resource_mgr.get_system_snapshot(worker_mgr.current_pid)
            resource_mgr.update_adaptive_state(snapshot["system_cpu_pct"])
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Stopping worker...")
        worker_mgr.stop_worker()
        sys.exit(0)


if __name__ == "__main__":
    main()
