"""
AtomicDB Portable - Worker Subprocess Supervisor
Launches and monitors the official upstream atomicdb_worker.py process.
"""

import os
import sys
import time
import signal
import subprocess
import threading
import logging
from typing import List, Optional, Callable

try:
    from .configuration import get_builtin_credentials, get_base_dir
except (ImportError, ValueError):
    from configuration import get_builtin_credentials, get_base_dir

logger = logging.getLogger("AtomicDB.WorkerManager")


class WorkerManager:
    """Supervises the official atomicdb_worker.py script without modifying upstream code."""

    def __init__(self, python_executable: str, worker_script_path: str, analytics_logger=None):
        self.python_executable = python_executable
        self.worker_script_path = worker_script_path
        self.analytics_logger = analytics_logger
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.current_pid: Optional[int] = None
        self.log_callbacks: List[Callable[[str], None]] = []
        self._reader_thread: Optional[threading.Thread] = None
        self.is_paused = False
        self.stop_after_current_task = False
        self.stop_after_task_file: Optional[str] = None

    def set_analytics_logger(self, analytics_logger):
        self.analytics_logger = analytics_logger

    def add_log_callback(self, callback: Callable[[str], None]):
        self.log_callbacks.append(callback)

    def build_command_args(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        server_url: str = "https://belzedar.duckdns.org",
        threads: int = 4,
        hash_mb: int = 1024,
        jobs: int = 1,
        engine: str = "",
        syzygy: str = "",
        no_fetch_syzygy: bool = True,
        solve: bool = False,
        no_auto_update: bool = False,
        no_engine_update: bool = False,
        engine_update_minutes: float = 15.0,
        once: bool = False,
    ) -> List[str]:
        """Builds command-line arguments for the upstream worker."""
        default_user, default_pass = get_builtin_credentials()
        if username is None:
            username = default_user
        if password is None:
            password = default_pass
        if not username:
            raise ValueError("OpenBench username (-U) is required")
        if not password:
            raise ValueError("OpenBench password (-P) is required")

        exe_lower = self.python_executable.lower()
        is_bundled_exe = getattr(sys, "frozen", False) or (
            exe_lower.endswith(".exe") and ("atomicdb" in exe_lower or "background processing utility" in exe_lower)
        )
        args = (
            [self.python_executable, "--exec-worker"]
            if is_bundled_exe
            else [self.python_executable, "-u", self.worker_script_path]
        )
        args.extend([
            "-U", str(username),
            "-P", str(password),
            "-S", str(server_url),
            "-T", str(max(1, int(threads))),
            "--hash", str(max(64, int(hash_mb))),
        ])

        if jobs and int(jobs) > 1:
            args.extend(["--jobs", str(int(jobs))])
        if engine and str(engine).strip():
            args.extend(["--engine", str(engine).strip()])
        if syzygy and str(syzygy).strip():
            args.extend(["--syzygy", str(syzygy).strip()])
        args.append("--no-fetch-syzygy" if no_fetch_syzygy else "--fetch-syzygy")
        if solve:
            args.append("--solve")
        if no_auto_update:
            args.append("--no-auto-update")
        if no_engine_update:
            args.append("--no-engine-update")
        if engine_update_minutes and float(engine_update_minutes) != 15.0:
            args.extend(["--engine-update-minutes", str(float(engine_update_minutes))])
        if once:
            args.append("--once")
        return args

    def start_worker(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        server_url: str = "https://belzedar.duckdns.org",
        threads: int = 4,
        hash_mb: int = 1024,
        jobs: int = 1,
        engine: str = "",
        syzygy: str = "",
        no_fetch_syzygy: bool = True,
        solve: bool = False,
        no_auto_update: bool = False,
        no_engine_update: bool = False,
        engine_update_minutes: float = 15.0,
        once: bool = False,
        cwd: Optional[str] = None,
    ) -> bool:
        """Starts the worker subprocess and attaches stream readers."""
        default_user, default_pass = get_builtin_credentials()
        username = username or default_user
        password = password or default_pass

        if self.is_running and self.process and self.process.poll() is None:
            logger.warning("Worker is already running.")
            return True

        self.is_paused = False
        if self.analytics_logger:
            self.analytics_logger.reset_current_task()

        if not os.path.exists(self.worker_script_path) and hasattr(sys, "_MEIPASS"):
            bundled = os.path.join(sys._MEIPASS, "worker", "atomicdb_worker.py")
            if os.path.exists(bundled):
                self.worker_script_path = bundled

        if not os.path.exists(self.worker_script_path):
            msg = f"Upstream worker script not found at: {self.worker_script_path}"
            logger.error(msg)
            self._broadcast_log(f"[ERROR] {msg}")
            return False

        cmd = self.build_command_args(
            username=username, password=password, server_url=server_url,
            threads=threads, hash_mb=hash_mb, jobs=jobs, engine=engine,
            syzygy=syzygy, no_fetch_syzygy=no_fetch_syzygy, solve=solve,
            no_auto_update=no_auto_update, no_engine_update=no_engine_update,
            engine_update_minutes=engine_update_minutes, once=once,
        )
        sanitized = ["********" if (i > 0 and cmd[i - 1] in ("-U", "-P")) else arg for i, arg in enumerate(cmd)]
        logger.info(f"Launching worker: {' '.join(sanitized)}")
        self._broadcast_log(f"[SUPERVISOR] Starting official worker: {' '.join(sanitized)}")

        work_dir = cwd or get_base_dir()
        child_env = os.environ.copy()
        portable_temp = os.path.join(work_dir, "temp")
        os.makedirs(portable_temp, exist_ok=True)
        child_env["ATOMICDB_PORTABLE_ROOT"] = work_dir
        child_env["ATOMICDB_SYZYGY_DIR"] = os.path.join(work_dir, "syzygy-345")
        child_env["TEMP"] = portable_temp
        child_env["TMP"] = portable_temp

        stop_flag_path = os.path.join(portable_temp, "stop_after_task.flag")
        self._remove_file_quiet(stop_flag_path)
        self.stop_after_task_file = stop_flag_path
        self.stop_after_current_task = False
        child_env["ATOMICDB_STOP_AFTER_TASK_FILE"] = stop_flag_path

        try:
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            self.process = subprocess.Popen(
                cmd, cwd=work_dir, env=child_env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=creationflags,
            )
            self.is_running = True
            self.current_pid = self.process.pid
            self._start_stdout_reader()
            self._broadcast_log(f"[SUPERVISOR] Worker process spawned with PID {self.current_pid}")
            return True
        except Exception as e:
            logger.error(f"Failed to launch worker subprocess: {e}")
            self._broadcast_log(f"[ERROR] Failed to start worker: {e}")
            self.is_running = False
            return False

    def _start_stdout_reader(self):
        def reader():
            try:
                while self.process and self.process.poll() is None:
                    line = self.process.stdout.readline()
                    if line:
                        self._broadcast_log(line.strip())
                    else:
                        time.sleep(0.05)

                if self.process and self.process.stdout:
                    for line in self.process.stdout:
                        if line:
                            self._broadcast_log(line.strip())

                exit_code = self.process.poll() if self.process else None
                if exit_code:
                    self._broadcast_log(f"[WORKER ERROR] Process exited with error code {exit_code}. Check OpenBench credentials.")
                elif exit_code == 0:
                    self._broadcast_log("[SUPERVISOR] Process ended cleanly.")
            except Exception as e:
                logger.debug(f"Reader thread exited: {e}")
            finally:
                self.is_running = False
                self.current_pid = None
                self.is_paused = False
                self.stop_after_current_task = False
                if self.analytics_logger and self.analytics_logger.current_task_id:
                    self.analytics_logger.reset_current_task()

        self._reader_thread = threading.Thread(target=reader, daemon=True)
        self._reader_thread.start()

    def _set_tree_paused(self, pause: bool) -> bool:
        if not self.is_running or not self.process or self.process.poll() is not None:
            return False
        try:
            import psutil
            proc = psutil.Process(self.process.pid)
            children = proc.children(recursive=True)
            targets = children + [proc] if pause else [proc] + children
            for p in targets:
                try:
                    p.suspend() if pause else p.resume()
                except Exception:
                    pass
            self.is_paused = pause
            if self.analytics_logger:
                self.analytics_logger.pause_current_task() if pause else self.analytics_logger.resume_current_task()
            state = "paused" if pause else "resumed"
            self._broadcast_log(f"[SUPERVISOR] Worker {state}; ETA countdown {state}.")
            return True
        except Exception as e:
            logger.debug(f"Could not {'pause' if pause else 'resume'} worker process: {e}")
            return False

    def pause_worker(self) -> bool:
        """Suspends the worker process tree and pauses active task ETA countdown."""
        return self._set_tree_paused(True)

    def resume_worker(self) -> bool:
        """Resumes a paused worker process tree and resumes active task ETA countdown."""
        return self._set_tree_paused(False)

    def request_stop_after_current_task(self) -> bool:
        """Signals the worker to finish and submit the active task, then exit cleanly."""
        if not self.is_running or not self.process or self.process.poll() is not None:
            return False
        self.stop_after_current_task = True
        if self.stop_after_task_file:
            try:
                parent_dir = os.path.dirname(self.stop_after_task_file)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                with open(self.stop_after_task_file, "w", encoding="utf-8") as f:
                    f.write("stop_after_current_task\n")
            except Exception as e:
                logger.error(f"Failed to write stop-after-task flag: {e}")
        self._broadcast_log("[SUPERVISOR] Stop scheduled: finishing current task cleanly before stopping...")
        return True

    def _broadcast_log(self, text: str):
        if self.analytics_logger:
            try:
                self.analytics_logger.parse_worker_line(text)
            except Exception as e:
                logger.debug(f"Analytics parse error: {e}")

        if text.startswith(("task pv:", "task progress:")):
            return

        for cb in self.log_callbacks:
            try:
                cb(text)
            except Exception:
                pass

    def stop_worker(self, timeout_sec: float = 8.0) -> bool:
        """Gracefully terminates the worker process, forcing kill only on timeout."""
        if self.process and self.process.poll() is None:
            logger.info(f"Stopping worker PID {self.process.pid} gracefully...")
            self._broadcast_log("[SUPERVISOR] Sending graceful shutdown signal...")
            try:
                if self.is_paused:
                    self.resume_worker()
                sig = signal.CTRL_BREAK_EVENT if sys.platform == "win32" else signal.SIGINT
                self.process.send_signal(sig)
                try:
                    self.process.wait(timeout=timeout_sec)
                    self._broadcast_log("[SUPERVISOR] Worker process terminated cleanly.")
                except subprocess.TimeoutExpired:
                    logger.warning("Worker did not exit in time. Forcing termination...")
                    self._broadcast_log("[SUPERVISOR] Timeout expired. Forcing process kill...")
                    self.process.kill()
                    self.process.wait(timeout=3.0)
            except Exception as e:
                logger.error(f"Error terminating worker: {e}")
                try:
                    self.process.kill()
                except Exception:
                    pass

        self.is_running = False
        self.current_pid = None
        self.is_paused = False
        self.stop_after_current_task = False
        self._remove_file_quiet(self.stop_after_task_file)
        if self.analytics_logger:
            self.analytics_logger.reset_current_task()
        return True

    @staticmethod
    def _remove_file_quiet(path: Optional[str]):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
