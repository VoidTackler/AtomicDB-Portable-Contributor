"""
AtomicDB Portable - Local USB Analytics & History Logger
Records all task executions, average nodes, NPS, system events, and crashes
strictly to the USB storage device (zero host footprint).
"""

import os
import sys
import re
import json
import time
import socket
import platform
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("AtomicDB.Analytics")

def format_nodes_compact(nodes: int) -> str:
    """Formats node counts compactly as e.g. '128m', '512m', '2b', '500k'."""
    try:
        n = int(nodes)
    except (TypeError, ValueError):
        return "0"
    if n < 0:
        n = 0
    if n >= 1_000_000_000:
        val = f"{n / 1_000_000_000:.2f}".rstrip("0").rstrip(".")
        return f"{val}b"
    if n >= 1_000_000:
        val = f"{n / 1_000_000:.2f}".rstrip("0").rstrip(".")
        return f"{val}m"
    if n >= 1_000:
        val = f"{n / 1_000:.2f}".rstrip("0").rstrip(".")
        return f"{val}k"
    return str(n)

def format_duration(seconds: float) -> str:
    """Formats seconds into human-readable duration like '14h 22m 30s' or '45s'."""
    s = max(0, int(seconds))
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"

def format_uptime_digital(seconds: float) -> str:
    """Formats seconds into digital clock string 'HH:MM:SS'."""
    s = max(0, int(seconds))
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

class AnalyticsLogger:
    """Manages persistent USB-local task history, node analytics, lifetime logs, and session graphs."""

    def __init__(self, base_dir: str, active_threads: int = 4):
        self.base_dir = os.path.abspath(base_dir)
        self.logs_dir = os.path.join(self.base_dir, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        self.active_threads = max(1, int(active_threads))
        self.device_name = (
            platform.node()
            or socket.gethostname()
            or os.environ.get("COMPUTERNAME")
            or os.environ.get("HOSTNAME")
            or "Unknown-Device"
        ).strip()

        # Core log and data files (Strictly preserved, never cleared)
        self.history_file = os.path.join(self.logs_dir, "history.json")
        self.analytics_file = os.path.join(self.logs_dir, "analytics.json")
        self.lifetime_txt_file = os.path.join(self.logs_dir, "lifetime_statistics.txt")
        self.session_log_file = os.path.join(self.logs_dir, "session_statistics.log")
        self.current_task_file = os.path.join(self.logs_dir, "current_task.log")
        self.activity_log_file = os.path.join(self.logs_dir, "activity.log")
        self.crashes_log_file = os.path.join(self.logs_dir, "crashes.log")
        self.system_log_file = os.path.join(self.logs_dir, "system.log")

        self.listeners: List[Callable[[Dict[str, Any]], None]] = []
        self.tasks_history: List[Dict[str, Any]] = []

        # Session-specific state (initialized fresh per session)
        self.session_start_time = time.time()
        self.session_tasks_completed = 0
        self.session_total_nodes = 0
        self.current_nps = 0
        self.session_average_nps = 0
        self.last_session_log_time = 0.0

        # Current task state
        self.current_task_id: Optional[str] = None
        self.current_task_nodes: int = 0
        self.current_task_nodes_done: int = 0
        self.current_task_line: str = "Idle (waiting for next task)"
        self.current_task_start_time: Optional[float] = None
        self.current_task_initial_eta_seconds: Optional[float] = None
        self.current_task_eta_seconds: Optional[float] = None
        self.is_worker_paused: bool = False
        self.current_task_paused_at: Optional[float] = None
        self.current_task_paused_duration: float = 0.0

        # Time-series graph data for current session (capped in memory)
        self.cpu_history: List[Dict[str, Any]] = []
        self.ram_history: List[Dict[str, Any]] = []
        self.nps_task_history: List[Dict[str, Any]] = []

        # Lifetime data structure (persistent across all sessions)
        self.analytics_data = {
            # Legacy keys kept for backwards compatibility
            "total_tasks_completed": 0,
            "total_nodes_analyzed": 0,
            "average_nodes_per_task": 0,
            "average_nps": 0,
            "tablebase_hits": 0,
            "engine_tasks": 0,
            "solve_tasks": 0,
            "total_time_seconds": 0.0,
            "engine_restarts": 0,
            "crashes": 0,
            "first_started_at": datetime.now().isoformat(),
            "last_task_at": None,
            "last_task_id": None,

            # Lifetime statistics explicitly required
            "lifetime_tasks_completed": 0,
            "lifetime_total_nodes": 0,
            "lifetime_average_nps": 0,
            "lifetime_total_runtime_seconds": 0.0,
            "lifetime_cpu_hours": 0.0,
            "lifetime_total_sessions": 0
        }

        # Compiled regex matchers for official upstream worker stdout
        self._re_analysis = re.compile(r"\[\d+\] task (\d+) \((\d+)n, ([\d\.]+)s\) -> (.*)")
        self._re_tb = re.compile(r"\[\d+\] task (\d+) TB wdl=(-?\d+)(?: dtz=(-?\d+))? -> (.*)")
        self._re_solve = re.compile(r"solve task (\d+) (.*?) \((\d+)n, ([\d\.]+)s\) -> (.*)")
        self._re_engine_fail = re.compile(r"\[\d+\] engine failure: (.*)")
        self._re_process_err = re.compile(r"\[WORKER ERROR\] Process exited with error code (-?\d+)")
        self._re_tb_status = re.compile(r"syzygy: (.*)")

        # Matchers for real-time current task state
        self._re_start_task = re.compile(r"(?:\[\d+\] )?starting (?:solve )?task (\d+) \((\d+)n\) calculating: (.*)")
        self._re_pv_line = re.compile(r"task pv: (.*)")
        self._re_task_progress = re.compile(r"task progress: nodes=(\d+) nps=(\d+)")

        self.load_persisted_data()

    def set_active_threads(self, threads: int):
        """Updates active threads for CPU-hour calculations."""
        self.active_threads = max(1, int(threads))

    def add_listener(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback for real-time UI notification on new task/stats."""
        self.listeners.append(callback)

    def _notify_listeners(self):
        summary = self.get_summary()
        for cb in self.listeners:
            try:
                cb(summary)
            except Exception as e:
                logger.debug(f"Listener error: {e}")

    def get_session_uptime(self) -> float:
        """Returns elapsed session uptime in seconds."""
        return max(0.0, time.time() - self.session_start_time)

    def get_session_uptime_str(self) -> str:
        """Returns formatted session uptime e.g. '01:23:45'."""
        return format_uptime_digital(self.get_session_uptime())

    def get_last_3_avg_nps(self) -> float:
        """
        Calculates the average NPS of up to the last three completed search tasks.
        When only 1 or 2 search tasks have been done in this session, divides by 1 or 2
        respectively (never pads or divides by 3, and excludes 0-node tablebase hits).
        """
        session_recent = [t["nps"] for t in self.nps_task_history if t.get("nps", 0) > 0][-3:]
        if session_recent:
            return sum(session_recent) / len(session_recent)
        recent_nps = [t["nps"] for t in self.tasks_history if t.get("nps", 0) > 0][-3:]
        if recent_nps:
            return sum(recent_nps) / len(recent_nps)
        if self.current_nps > 0:
            return float(self.current_nps)
        if self.session_total_nodes > 0:
            uptime = self.get_session_uptime()
            if uptime > 0:
                return self.session_total_nodes / uptime
        if self.analytics_data.get("lifetime_average_nps", 0) > 0:
            return float(self.analytics_data["lifetime_average_nps"])
        return 0.0

    @staticmethod
    def filter_history_by_timeframe(
        series: List[Dict[str, Any]],
        timeframe_seconds: float,
        now: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Filters a time-series list to points within the trailing timeframe_seconds window."""
        if not series:
            return []
        ref_time = time.time() if now is None else float(now)
        cutoff = ref_time - float(timeframe_seconds)
        return [pt for pt in series if float(pt.get("time", 0.0)) >= cutoff]

    def calculate_estimated_time_remaining(self) -> Optional[int]:
        """
        The average time remaining is based on the last three tasks, not last three lines or calculations.
        Calculated before each task (rounded to whole seconds), reduces by 1 second steps,
        pauses when the worker is paused, resets when the worker is reset,
        and can go into negative integers when overdue.
        """
        if not self.current_task_id or self.current_task_initial_eta_seconds is None or self.current_task_start_time is None:
            return None
        ref_now = (
            self.current_task_paused_at
            if (self.is_worker_paused and self.current_task_paused_at is not None)
            else time.time()
        )
        elapsed_float = max(0.0, ref_now - self.current_task_start_time - self.current_task_paused_duration)
        elapsed_sec = int(round(elapsed_float))
        remaining = int(self.current_task_initial_eta_seconds) - elapsed_sec
        return remaining

    def pause_current_task(self):
        """Pauses the active task ETA countdown at its exact current value."""
        if not self.is_worker_paused:
            self.is_worker_paused = True
            self.current_task_paused_at = time.time()
            self.current_task_eta_seconds = self.calculate_estimated_time_remaining()
            self.write_current_task_log()
            self._notify_listeners()

    def resume_current_task(self):
        """Resumes the active task ETA countdown, excluding paused duration."""
        if self.is_worker_paused:
            if self.current_task_paused_at is not None:
                self.current_task_paused_duration += max(0.0, time.time() - self.current_task_paused_at)
            self.current_task_paused_at = None
            self.is_worker_paused = False
            self.current_task_eta_seconds = self.calculate_estimated_time_remaining()
            self.write_current_task_log()
            self._notify_listeners()

    def reset_current_task(self):
        """Resets active task state and Estimated Time Remaining when the worker stops or resets."""
        self.current_task_id = None
        self.current_task_nodes = 0
        self.current_task_nodes_done = 0
        self.current_task_line = "Idle (waiting for next task)"
        self.current_task_initial_eta_seconds = None
        self.current_task_eta_seconds = None
        self.current_task_start_time = None
        self.is_worker_paused = False
        self.current_task_paused_at = None
        self.current_task_paused_duration = 0.0
        self.write_current_task_log()
        self._notify_listeners()

    @staticmethod
    def format_eta_str(eta: Optional[float]) -> str:
        """Formats remaining time as whole integer seconds/minutes with negative support and no decimals."""
        if eta is None:
            return "Calculating..."
        whole = int(round(eta))
        if whole == 0:
            return "0s"
        if whole > 0:
            if whole < 60:
                return f"{whole}s"
            m = whole // 60
            s = whole % 60
            return f"{m}m {s:02d}s"
        else:
            abs_eta = abs(whole)
            if abs_eta < 60:
                return f"-{abs_eta}s"
            m = abs_eta // 60
            s = abs_eta % 60
            return f"-{m}m {s:02d}s"

    def load_persisted_data(self):
        """Loads prior history and lifetime analytics from USB logs directory."""
        try:
            if os.path.exists(self.analytics_file):
                with open(self.analytics_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.analytics_data.update(data)
        except Exception as e:
            logger.warning(f"Could not load analytics.json from USB: {e}")

        # Ensure lifetime statistics sync from legacy keys if first run after update
        if self.analytics_data["lifetime_tasks_completed"] == 0 and self.analytics_data["total_tasks_completed"] > 0:
            self.analytics_data["lifetime_tasks_completed"] = self.analytics_data["total_tasks_completed"]
            self.analytics_data["lifetime_total_nodes"] = self.analytics_data["total_nodes_analyzed"]
            self.analytics_data["lifetime_total_runtime_seconds"] = self.analytics_data["total_time_seconds"]
            self.analytics_data["lifetime_average_nps"] = self.analytics_data["average_nps"]
            self.analytics_data["lifetime_cpu_hours"] = round(
                (self.analytics_data["lifetime_total_runtime_seconds"] * self.active_threads) / 3600.0, 4
            )

        # Increment total session count for this run
        self.analytics_data["lifetime_total_sessions"] += 1

        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self.tasks_history = json.load(f)
                    if len(self.tasks_history) > 5000:
                        self.tasks_history = self.tasks_history[-5000:]
        except Exception as e:
            logger.warning(f"Could not load history.json from USB: {e}")

        self.save_persisted_data()
        self.write_lifetime_statistics_txt()
        self.log_session_event("Client session initialized")

    def save_persisted_data(self):
        """Atomically saves analytics and history to the USB drive."""
        try:
            temp_analytics = self.analytics_file + ".tmp"
            payload = self.get_summary()
            with open(temp_analytics, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            if os.path.exists(self.analytics_file):
                os.remove(self.analytics_file)
            os.rename(temp_analytics, self.analytics_file)
        except Exception as e:
            logger.error(f"Error persisting analytics to USB: {e}")

        try:
            temp_hist = self.history_file + ".tmp"
            with open(temp_hist, "w", encoding="utf-8") as f:
                json.dump(self.tasks_history[-2000:], f, indent=2)
            if os.path.exists(self.history_file):
                os.remove(self.history_file)
            os.rename(temp_hist, self.history_file)
        except Exception as e:
            logger.error(f"Error persisting history to USB: {e}")

    def write_lifetime_statistics_txt(self):
        """Writes formatted human-readable lifetime statistics report to USB text file."""
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tasks = self.analytics_data.get("lifetime_tasks_completed", 0)
            nodes = self.analytics_data.get("lifetime_total_nodes", 0)
            avg_nps = self.analytics_data.get("lifetime_average_nps", 0)
            runtime_sec = self.analytics_data.get("lifetime_total_runtime_seconds", 0.0)
            cpu_hrs = self.analytics_data.get("lifetime_cpu_hours", 0.0)
            sessions = self.analytics_data.get("lifetime_total_sessions", 1)

            # Node formatting helper
            if nodes >= 1_000_000_000:
                nodes_fmt = f"{nodes:,} ({nodes / 1_000_000_000:.2f} B)"
            elif nodes >= 1_000_000:
                nodes_fmt = f"{nodes:,} ({nodes / 1_000_000:.2f} M)"
            else:
                nodes_fmt = f"{nodes:,}"

            # NPS formatting helper
            if avg_nps >= 1_000_000:
                nps_fmt = f"{avg_nps:,} nodes/sec ({avg_nps / 1_000_000:.2f} M/s)"
            elif avg_nps >= 1_000:
                nps_fmt = f"{avg_nps:,} nodes/sec ({avg_nps / 1_000:.1f} k/s)"
            else:
                nps_fmt = f"{avg_nps:,} nodes/sec"

            runtime_fmt = f"{format_duration(runtime_sec)} ({int(runtime_sec):,} seconds)"
            cpu_hrs_str = f"{cpu_hrs:.4f}" if (0 < cpu_hrs < 0.1) else f"{cpu_hrs:.2f}"

            content = (
                "===================================================================\n"
                "   ATOMICDB PORTABLE — LIFETIME STATISTICS (PERMANENT USB LOG)     \n"
                "===================================================================\n"
                f"Last Updated:             {ts}\n"
                f"Last Device:              {self.device_name}\n"
                f"Total Tasks Completed:    {tasks:,}\n"
                f"Total Lifetime Nodes:     {nodes_fmt}\n"
                f"Lifetime Average NPS:     {nps_fmt}\n"
                f"Total Accumulated Time:   {runtime_fmt}\n"
                f"Total CPU Hours:          {cpu_hrs_str} CPU hours\n"
                f"Total Number of Sessions: {sessions:,} sessions\n"
                "===================================================================\n"
                "NOTICE: This log records all historical analysis performed from\n"
                "this portable drive. Logs and metrics are preserved permanently.\n"
                "===================================================================\n"
            )

            temp_txt = self.lifetime_txt_file + ".tmp"
            with open(temp_txt, "w", encoding="utf-8") as f:
                f.write(content)
            if os.path.exists(self.lifetime_txt_file):
                os.remove(self.lifetime_txt_file)
            os.rename(temp_txt, self.lifetime_txt_file)
        except Exception as e:
            logger.error(f"Error writing lifetime_statistics.txt: {e}")

    def write_current_task_log(self):
        """Saves current task status (Task ID, Nodes, Calculating Line, ETA) into USB current_task.log."""
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tid = self.current_task_id or "IDLE"
            nodes = self.current_task_nodes
            done = self.current_task_nodes_done
            line = self.current_task_line or "None"
            eta = self.calculate_estimated_time_remaining()
            eta_str = self.format_eta_str(eta) if self.current_task_id else "-"

            content = (
                f"[{ts}] [CURRENT TASK]\n"
                f"Device Name:              {self.device_name}\n"
                f"Task ID:                  {tid}\n"
                f"Budget Nodes:             {format_nodes_compact(nodes)} ({nodes:,})\n"
                f"Nodes Done So Far:        {format_nodes_compact(done)} ({done:,})\n"
                f"Estimated Time Remaining: {eta_str}\n"
                f"Calculating Line:         {line}\n"
            )
            with open(self.current_task_file, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.debug(f"Error writing current_task.log: {e}")

    def log_session_event(self, event_note: str = ""):
        """Appends a snapshot of session statistics to logs/session_statistics.log."""
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            uptime = self.get_session_uptime_str()
            tasks = self.session_tasks_completed
            nodes = self.session_total_nodes
            curr_nps = self.current_nps
            avg_nps = self.session_average_nps

            log_line = (
                f"[{ts}] Device: {self.device_name} | Session Uptime: {uptime} | Tasks: {tasks} | "
                f"Nodes: {format_nodes_compact(nodes)} ({nodes:,}) | Current NPS: {curr_nps:,} | "
                f"Avg NPS: {avg_nps:,} | Note: {event_note}\n"
            )
            with open(self.session_log_file, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            logger.debug(f"Error appending to session_statistics.log: {e}")

    def record_hardware_sample(self, sys_cpu: float, worker_cpu: float, worker_ram_mb: int, available_ram_mb: int):
        """Records a real-time CPU & RAM data point for session time-series graphs (12m buffer for 10m dial)."""
        now = time.time()
        ts_str = datetime.now().strftime("%H:%M:%S")

        self.cpu_history.append({
            "time": now,
            "timestamp": ts_str,
            "system_cpu": round(float(sys_cpu), 1),
            "worker_cpu": round(float(worker_cpu), 1)
        })
        if len(self.cpu_history) > 1000:
            self.cpu_history.pop(0)

        self.ram_history.append({
            "time": now,
            "timestamp": ts_str,
            "worker_ram": int(worker_ram_mb),
            "available_ram": int(available_ram_mb)
        })
        if len(self.ram_history) > 1000:
            self.ram_history.pop(0)

        # Update session average NPS dynamically
        uptime = self.get_session_uptime()
        if uptime > 0 and self.session_total_nodes > 0:
            self.session_average_nps = int(self.session_total_nodes / uptime)

    def record_task_start(self, task_id: str, budget_nodes: int, line_info: str):
        """
        Called before each task begins. Computes initial ETA based on last 3 tasks.
        Only logs by individual tasks (no per-line writes).
        """
        self.current_task_id = str(task_id)
        self.current_task_nodes = int(budget_nodes)
        self.current_task_nodes_done = 0
        self.current_task_line = str(line_info).strip()
        self.current_task_start_time = time.time()
        self.is_worker_paused = False
        self.current_task_paused_at = None
        self.current_task_paused_duration = 0.0

        # ETA is calculated before each task based on last 3 tasks (rounded to whole seconds)
        avg_3 = self.get_last_3_avg_nps()
        if avg_3 > 0 and self.current_task_nodes > 0:
            self.current_task_initial_eta_seconds = int(round(float(self.current_task_nodes) / float(avg_3)))
        else:
            self.current_task_initial_eta_seconds = None

        self.current_task_eta_seconds = self.current_task_initial_eta_seconds

        # Save once at task start
        self.write_current_task_log()
        self._notify_listeners()

    def update_task_progress(self, nodes_done: int, current_nps: int):
        """Updates in-memory nodes done and NPS for UI without disk writes."""
        self.current_task_nodes_done = max(self.current_task_nodes_done, int(nodes_done))
        self.current_nps = int(current_nps)
        self._notify_listeners()

    def update_task_pv(self, pv_line: str):
        """Updates the exact variation/line being calculated in memory for the UI without disk writes."""
        self.current_task_line = str(pv_line).strip()
        self._notify_listeners()

    def record_task(
        self,
        task_id: str,
        nodes: int,
        elapsed_sec: float,
        summary: str,
        is_tb: bool = False,
        wdl: Optional[int] = None,
        dtz: Optional[int] = None,
        is_solve: bool = False
    ):
        """Records a completed task into USB history and updates aggregate analytics."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nps = int(nodes / elapsed_sec) if elapsed_sec > 0 else 0
        self.current_nps = nps

        task_type = "Tablebase" if is_tb else ("Solve" if is_solve else "Engine")

        item = {
            "task_id": str(task_id),
            "timestamp": timestamp,
            "device": self.device_name,
            "type": task_type,
            "nodes": int(nodes),
            "elapsed_sec": round(float(elapsed_sec), 2),
            "nps": nps,
            "summary": str(summary).strip()
        }
        if wdl is not None:
            item["wdl"] = int(wdl)
            item["tb_wdl"] = int(wdl)
        if dtz is not None:
            item["dtz"] = int(dtz)
            item["tb_dtz"] = int(dtz)

        self.tasks_history.append(item)
        if len(self.tasks_history) > 5000:
            self.tasks_history.pop(0)

        # Update session statistics
        self.session_tasks_completed += 1
        self.session_total_nodes += int(nodes)
        uptime = self.get_session_uptime()
        self.session_average_nps = int(self.session_total_nodes / max(1.0, uptime))

        # Record into NPS per task session graph history
        self.nps_task_history.append({
            "task_id": str(task_id),
            "nps": nps,
            "nodes": int(nodes),
            "elapsed": round(float(elapsed_sec), 2),
            "device": self.device_name,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "time": time.time()
        })
        if len(self.nps_task_history) > 500:
            self.nps_task_history.pop(0)

        # Update legacy running aggregates
        self.analytics_data["total_tasks_completed"] += 1
        self.analytics_data["total_nodes_analyzed"] += int(nodes)
        self.analytics_data["total_time_seconds"] = round(
            self.analytics_data["total_time_seconds"] + float(elapsed_sec), 2
        )
        total_tasks = self.analytics_data["total_tasks_completed"]
        total_nodes = self.analytics_data["total_nodes_analyzed"]
        total_time = self.analytics_data["total_time_seconds"]

        self.analytics_data["average_nodes_per_task"] = total_nodes // total_tasks if total_tasks else 0
        self.analytics_data["average_nps"] = int(total_nodes / total_time) if total_time > 0 else 0

        # Update lifetime statistics
        self.analytics_data["lifetime_tasks_completed"] += 1
        self.analytics_data["lifetime_total_nodes"] += int(nodes)
        self.analytics_data["lifetime_total_runtime_seconds"] = round(
            self.analytics_data.get("lifetime_total_runtime_seconds", 0.0) + float(elapsed_sec), 2
        )
        lt_runtime = self.analytics_data["lifetime_total_runtime_seconds"]
        self.analytics_data["lifetime_average_nps"] = (
            int(self.analytics_data["lifetime_total_nodes"] / lt_runtime) if lt_runtime > 0 else 0
        )
        # Add CPU hours for this task: (elapsed_sec * threads) / 3600
        task_cpu_hours = (float(elapsed_sec) * self.active_threads) / 3600.0
        self.analytics_data["lifetime_cpu_hours"] = round(
            self.analytics_data.get("lifetime_cpu_hours", 0.0) + task_cpu_hours, 4
        )

        if is_tb:
            self.analytics_data["tablebase_hits"] += 1
        elif is_solve:
            self.analytics_data["solve_tasks"] += 1
        else:
            self.analytics_data["engine_tasks"] += 1

        self.analytics_data["last_task_at"] = timestamp
        self.analytics_data["last_task_id"] = str(task_id)
        self.analytics_data["last_device"] = self.device_name

        # Reset current task state to idle
        self.current_task_id = None
        self.current_task_nodes = 0
        self.current_task_nodes_done = 0
        self.current_task_line = "Idle (waiting for next task)"
        self.current_task_initial_eta_seconds = None
        self.current_task_eta_seconds = None
        self.current_task_start_time = None
        self.is_worker_paused = False
        self.current_task_paused_at = None
        self.current_task_paused_duration = 0.0

        # Append to human-readable activity.log on USB (including Device name after each task)
        try:
            with open(self.activity_log_file, "a", encoding="utf-8") as f:
                f.write(
                    f"[{timestamp}] [TASK DONE] Device: {self.device_name} | ID: {task_id} | Type: {task_type} | "
                    f"Nodes: {format_nodes_compact(nodes)} ({nodes:,}) | Time: {elapsed_sec:.2f}s | NPS: {nps:,} | {summary}\n"
                )
        except Exception as e:
            logger.warning(f"Could not append to activity.log on USB: {e}")

        # Update current task log file
        self.write_current_task_log()

        # Append to session statistics log (includes Device name)
        self.log_session_event(f"Task {task_id} completed ({format_nodes_compact(nodes)} nodes, {nps:,} NPS)")

        # Persist to disk and update text file
        self.save_persisted_data()
        self.write_lifetime_statistics_txt()
        self._notify_listeners()

    def record_crash(self, event_type: str, details: str):
        """Records an engine restart, worker crash, or system failure into USB crash log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.analytics_data["crashes"] += 1
        if "ENGINE" in event_type.upper():
            self.analytics_data["engine_restarts"] += 1

        try:
            with open(self.crashes_log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{event_type}] {details}\n")
            with open(self.system_log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [WARNING/CRASH] [{event_type}] {details}\n")
        except Exception as e:
            logger.warning(f"Could not append to crashes.log on USB: {e}")

        self.save_persisted_data()
        self._notify_listeners()

    def record_system_event(self, message: str):
        """Records general supervisor and engine events into system.log on USB."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.system_log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [SYSTEM] {message}\n")
        except Exception:
            pass

    def parse_worker_line(self, line: str):
        """Analyzes a single stdout line from the upstream worker process."""
        if not line:
            return

        clean = line.strip()

        # 0. Real-time task start tracking
        m_start = self._re_start_task.search(clean)
        if m_start:
            task_id, budget_n, line_info = m_start.groups()
            self.record_task_start(task_id, int(budget_n), line_info)
            return

        # 0b. Real-time PV variation update
        m_pv = self._re_pv_line.search(clean)
        if m_pv:
            self.update_task_pv(m_pv.group(1))
            return

        # 0c. Real-time nodes and NPS progress update
        m_prog = self._re_task_progress.search(clean)
        if m_prog:
            nodes_val, nps_val = m_prog.groups()
            self.update_task_progress(int(nodes_val), int(nps_val))
            return

        # 1. Standard engine analysis task completion
        m1 = self._re_analysis.search(clean)
        if m1:
            task_id, nodes_s, elapsed_s, summary = m1.groups()
            self.record_task(
                task_id=task_id,
                nodes=int(nodes_s),
                elapsed_sec=float(elapsed_s),
                summary=summary,
                is_tb=False
            )
            return

        # 2. Tablebase hit
        m2 = self._re_tb.search(clean)
        if m2:
            task_id, wdl_s, dtz_s, summary = m2.groups()
            self.record_task(
                task_id=task_id,
                nodes=0,
                elapsed_sec=0.01,
                summary=summary,
                is_tb=True,
                wdl=int(wdl_s) if wdl_s is not None else None,
                dtz=int(dtz_s) if dtz_s is not None else None
            )
            return

        # 3. Solve task completion
        m3 = self._re_solve.search(clean)
        if m3:
            task_id, outcome, nodes_s, elapsed_s, summary = m3.groups()
            self.record_task(
                task_id=task_id,
                nodes=int(nodes_s),
                elapsed_sec=float(elapsed_s),
                summary=f"{outcome}: {summary}",
                is_solve=True
            )
            return

        # 4. Engine failure & restart
        m4 = self._re_engine_fail.search(clean)
        if m4:
            self.record_crash("ENGINE_FAILURE", m4.group(1))
            return

        # 5. Worker process crash
        m5 = self._re_process_err.search(clean)
        if m5:
            self.reset_current_task()
            self.record_crash("WORKER_EXIT_ERROR", f"Exit code {m5.group(1)}")
            return

        # 5b. Clean worker stop / task interruption resets current task ETA
        if (
            "interrupted by the stop" in clean
            or "[SUPERVISOR] Process ended cleanly" in clean
            or "[SUPERVISOR] Worker process terminated cleanly" in clean
        ):
            self.reset_current_task()
            return

        # 6. Syzygy download status logging
        m6 = self._re_tb_status.search(clean)
        if m6:
            self.record_system_event(f"Syzygy status: {m6.group(1)}")

    def get_summary(self) -> Dict[str, Any]:
        """Returns consolidated analytics for display with session, current task, lifetime, and graphs."""
        uptime_sec = self.get_session_uptime()
        eta = self.calculate_estimated_time_remaining()

        # Dynamic session average NPS
        session_avg_nps = self.session_average_nps
        if uptime_sec > 0 and self.session_total_nodes > 0:
            session_avg_nps = int(self.session_total_nodes / uptime_sec)

        return {
            **self.analytics_data,
            "device_name": self.device_name,
            "is_worker_paused": self.is_worker_paused,
            # Session statistics
            "session_tasks_completed": self.session_tasks_completed,
            "session_total_nodes": self.session_total_nodes,
            "current_nps": self.current_nps,
            "session_average_nps": session_avg_nps,
            "session_uptime_seconds": round(uptime_sec, 1),
            "session_uptime_str": self.get_session_uptime_str(),

            # Current task
            "current_task_id": self.current_task_id,
            "current_task_nodes": self.current_task_nodes,
            "current_task_nodes_done": self.current_task_nodes_done,
            "current_task_line": self.current_task_line,
            "current_task_eta_seconds": int(eta) if eta is not None else None,
            "current_task_eta_str": self.format_eta_str(eta) if self.current_task_id else "-",

            # Lifetime statistics
            "lifetime_tasks_completed": self.analytics_data.get("lifetime_tasks_completed", 0),
            "lifetime_total_nodes": self.analytics_data.get("lifetime_total_nodes", 0),
            "lifetime_average_nps": self.analytics_data.get("lifetime_average_nps", 0),
            "lifetime_total_runtime_seconds": self.analytics_data.get("lifetime_total_runtime_seconds", 0.0),
            "lifetime_total_runtime_str": format_duration(self.analytics_data.get("lifetime_total_runtime_seconds", 0.0)),
            "lifetime_cpu_hours": round(self.analytics_data.get("lifetime_cpu_hours", 0.0), 4),
            "lifetime_total_sessions": self.analytics_data.get("lifetime_total_sessions", 1),

            # Graph series (this session, retaining >= 10 minutes at 0.8s refresh)
            "cpu_history": list(self.cpu_history[-900:]),
            "ram_history": list(self.ram_history[-900:]),
            "nps_task_history": list(self.nps_task_history[-200:]),

            "recent_tasks": list(reversed(self.tasks_history[-100:]))
        }

    def clear_history(self):
        """Permanent preservation policy: logs and lifetime statistics are never cleared."""
        logger.info("Permanent preservation rule: USB logs and lifetime statistics cannot be cleared.")
        # Only refreshes listeners without deleting historical records
        self._notify_listeners()
