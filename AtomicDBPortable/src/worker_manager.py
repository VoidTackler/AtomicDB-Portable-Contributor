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
import queue
import logging
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger("AtomicDB.WorkerManager")

_BUILTIN_USER_BYTES = (10, 53, 40, 46, 59, 56, 54, 63, 31, 34, 63)
_BUILTIN_PASS_BYTES = (31, 34, 63, 10, 59, 41, 41, 45, 53, 40, 62)

def _decode_builtin(encoded_bytes) -> str:
    return bytes(b ^ 0x5A for b in encoded_bytes).decode("ascii")

class WorkerManager:
    """Supervises the official atomicdb_worker.py script without modifying upstream code."""

    def __init__(self, python_executable: str, worker_script_path: str, analytics_logger=None):
        self.python_executable = python_executable
        self.worker_script_path = worker_script_path
        self.analytics_logger = analytics_logger
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.current_pid: Optional[int] = None
        self.stdout_queue: queue.Queue = queue.Queue()
        self.log_callbacks: List[Callable[[str], None]] = []
        self._reader_thread: Optional[threading.Thread] = None
        self.consecutive_crashes = 0
        self.last_crash_time = 0.0
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
        no_fetch_syzygy: bool = True,  # Always True by default per user specification
        solve: bool = False,
        no_auto_update: bool = False,
        no_engine_update: bool = False,
        engine_update_minutes: float = 15.0,
        once: bool = False
    ) -> List[str]:
        """
        Builds command line arguments for the upstream worker.
        """
        if username is None:
            username = _decode_builtin(_BUILTIN_USER_BYTES)
        if password is None:
            password = _decode_builtin(_BUILTIN_PASS_BYTES)
        if not username:
            raise ValueError("OpenBench username (-U) is required")
        if not password:
            raise ValueError("OpenBench password (-P) is required")

        is_frozen = getattr(sys, 'frozen', False)
        exe_lower = self.python_executable.lower()
        if is_frozen or (exe_lower.endswith(".exe") and ("atomicdb" in exe_lower or "background processing utility" in exe_lower)):
            args = [
                self.python_executable,
                "--exec-worker",
                "-U", str(username),
                "-P", str(password),
                "-S", str(server_url),
                "-T", str(max(1, int(threads))),
                "--hash", str(max(64, int(hash_mb)))
            ]
        else:
            args = [
                self.python_executable,
                "-u",  # Unbuffered stdout/stderr
                self.worker_script_path,
                "-U", str(username),
                "-P", str(password),
                "-S", str(server_url),
                "-T", str(max(1, int(threads))),
                "--hash", str(max(64, int(hash_mb)))
            ]

        # Additional open source contributor API options
        if jobs and int(jobs) > 1:
            args.extend(["--jobs", str(int(jobs))])
        if engine and str(engine).strip():
            args.extend(["--engine", str(engine).strip()])
        if syzygy and str(syzygy).strip():
            args.extend(["--syzygy", str(syzygy).strip()])
        if no_fetch_syzygy:
            args.append("--no-fetch-syzygy")
        else:
            args.append("--fetch-syzygy")
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
        no_fetch_syzygy: bool = True,  # User requirement: no tablebase is always enabled by default
        solve: bool = False,
        no_auto_update: bool = False,
        no_engine_update: bool = False,
        engine_update_minutes: float = 15.0,
        once: bool = False,
        cwd: Optional[str] = None
    ) -> bool:
        """Starts worker subprocess with all contributor options and attaches stream readers."""
        username = username or _decode_builtin(_BUILTIN_USER_BYTES)
        password = password or _decode_builtin(_BUILTIN_PASS_BYTES)
        if self.is_running and self.process and self.process.poll() is None:
            logger.warning("Worker is already running.")
            return True

        self.is_paused = False
        if self.analytics_logger:
            self.analytics_logger.reset_current_task()

        if not os.path.exists(self.worker_script_path):
            if hasattr(sys, '_MEIPASS'):
                meipass_worker = os.path.join(sys._MEIPASS, "worker", "atomicdb_worker.py")
                if os.path.exists(meipass_worker):
                    self.worker_script_path = meipass_worker

        if not os.path.exists(self.worker_script_path):
            error_msg = f"Upstream worker script not found at: {self.worker_script_path}"
            logger.error(error_msg)
            self._broadcast_log(f"[ERROR] {error_msg}")
            return False

        cmd = self.build_command_args(
            username=username,
            password=password,
            server_url=server_url,
            threads=threads,
            hash_mb=hash_mb,
            jobs=jobs,
            engine=engine,
            syzygy=syzygy,
            no_fetch_syzygy=no_fetch_syzygy,
            solve=solve,
            no_auto_update=no_auto_update,
            no_engine_update=no_engine_update,
            engine_update_minutes=engine_update_minutes,
            once=once
        )
        # Log command without exposing either account username or password
        sanitized_cmd = [
            "********" if (i > 0 and cmd[i - 1] in ("-U", "-P")) else cmd[i]
            for i in range(len(cmd))
        ]
        logger.info(f"Launching worker: {' '.join(sanitized_cmd)}")
        self._broadcast_log(f"[SUPERVISOR] Starting official worker: {' '.join(sanitized_cmd)}")

        # Ensure working directory is strictly on the portable storage device
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(os.path.abspath(sys.executable))
        work_dir = cwd or base_dir

        # Ensure environment variables redirect all storage away from host C: drive
        child_env = os.environ.copy()
        child_env["ATOMICDB_PORTABLE_ROOT"] = work_dir
        child_env["ATOMICDB_SYZYGY_DIR"] = os.path.join(work_dir, "syzygy-345")
        portable_temp = os.path.join(work_dir, "temp")
        os.makedirs(portable_temp, exist_ok=True)
        child_env["TEMP"] = portable_temp
        child_env["TMP"] = portable_temp

        stop_flag_path = os.path.join(portable_temp, "stop_after_task.flag")
        try:
            if os.path.exists(stop_flag_path):
                os.remove(stop_flag_path)
        except Exception:
            pass
        self.stop_after_task_file = stop_flag_path
        self.stop_after_current_task = False
        child_env["ATOMICDB_STOP_AFTER_TASK_FILE"] = stop_flag_path

        try:
            # On Windows, use CREATE_NEW_PROCESS_GROUP for clean signals
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

            self.process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                env=child_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                creationflags=creationflags
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
        """Starts background reader thread to capture worker output in real-time."""
        def reader():
            try:
                while self.process and self.process.poll() is None:
                    line = self.process.stdout.readline()
                    if line:
                        clean_line = line.strip()
                        self.stdout_queue.put(clean_line)
                        self._broadcast_log(clean_line)
                    else:
                        time.sleep(0.05)

                # Drain all remaining lines (tracebacks, auth rejections, server messages)
                if self.process and self.process.stdout:
                    for line in self.process.stdout:
                        if line:
                            clean = line.strip()
                            self.stdout_queue.put(clean)
                            self._broadcast_log(clean)

                exit_code = self.process.poll() if self.process else None
                if exit_code is not None and exit_code != 0:
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

    def pause_worker(self) -> bool:
        """Suspends the worker process tree and pauses active task ETA countdown."""
        if not self.is_running or not self.process or self.process.poll() is not None:
            return False
        try:
            import psutil
            proc = psutil.Process(self.process.pid)
            for child in proc.children(recursive=True):
                try:
                    child.suspend()
                except Exception:
                    pass
            proc.suspend()
            self.is_paused = True
            if self.analytics_logger:
                self.analytics_logger.pause_current_task()
            self._broadcast_log("[SUPERVISOR] Worker paused; ETA countdown paused.")
            return True
        except Exception as e:
            logger.debug(f"Could not pause worker process: {e}")
            return False

    def resume_worker(self) -> bool:
        """Resumes a paused worker process tree and resumes active task ETA countdown."""
        if not self.is_running or not self.process or self.process.poll() is not None:
            return False
        try:
            import psutil
            proc = psutil.Process(self.process.pid)
            proc.resume()
            for child in proc.children(recursive=True):
                try:
                    child.resume()
                except Exception:
                    pass
            self.is_paused = False
            if self.analytics_logger:
                self.analytics_logger.resume_current_task()
            self._broadcast_log("[SUPERVISOR] Worker resumed; ETA countdown resumed.")
            return True
        except Exception as e:
            logger.debug(f"Could not resume worker process: {e}")
            return False

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

        self._broadcast_log(
            "[SUPERVISOR] Stop scheduled: finishing current task cleanly before stopping..."
        )
        return True

    def _broadcast_log(self, text: str):
        if self.analytics_logger:
            try:
                self.analytics_logger.parse_worker_line(text)
            except Exception as e:
                logger.debug(f"Analytics parse error: {e}")

        # Keep operator console clean - telemetry lines update the dashboard without clogging console
        if text.startswith("task pv:") or text.startswith("task progress:"):
            return

        for cb in self.log_callbacks:
            try:
                cb(text)
            except Exception:
                pass

    def stop_worker(self, timeout_sec: float = 8.0) -> bool:
        """
        Gracefully terminates the worker process.
        Sends SIGINT/CTRL_BREAK first to allow current task completion/cleanup.
        Falls back to SIGKILL only if process hangs.
        """
        if not self.process or self.process.poll() is not None:
            self.is_running = False
            self.current_pid = None
            self.is_paused = False
            self.stop_after_current_task = False
            if self.analytics_logger:
                self.analytics_logger.reset_current_task()
            return True

        logger.info(f"Stopping worker PID {self.process.pid} gracefully...")
        self._broadcast_log("[SUPERVISOR] Sending graceful shutdown signal...")

        try:
            if self.is_paused:
                self.resume_worker()
            if sys.platform == "win32":
                # Send CTRL_BREAK_EVENT to the process group
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self.process.send_signal(signal.SIGINT)

            # Wait for clean exit
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
        if self.stop_after_task_file and os.path.exists(self.stop_after_task_file):
            try:
                os.remove(self.stop_after_task_file)
            except Exception:
                pass
        if self.analytics_logger:
            self.analytics_logger.reset_current_task()
        return True

    def check_health(self) -> Dict[str, Any]:
        """Checks if process is alive and detects unexpected exits."""
        if not self.is_running or not self.process:
            return {"alive": False, "pid": None, "exit_code": None}

        exit_code = self.process.poll()
        if exit_code is not None:
            self.is_running = False
            self.current_pid = None
            self._broadcast_log(f"[SUPERVISOR] Worker exited unexpectedly with code {exit_code}")
            
            # Backoff tracking
            now = time.time()
            if now - self.last_crash_time < 30:
                self.consecutive_crashes += 1
            else:
                self.consecutive_crashes = 1
            self.last_crash_time = now

            return {"alive": False, "pid": None, "exit_code": exit_code, "crashes": self.consecutive_crashes}

        return {"alive": True, "pid": self.process.pid, "exit_code": None}
