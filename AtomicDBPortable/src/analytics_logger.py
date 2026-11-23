"""
AtomicDB Portable - Local USB Analytics & History Logger
Records task executions, average nodes, NPS, NPH, system events, and crashes strictly on the USB drive.
"""

import os
import re
import json
import time
import socket
import platform
import logging
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("AtomicDB.Analytics")

try:
    from .chess_notation import (
        DEFAULT_ATOMICDB_SERVER,
        build_atomicdb_explore_url,
        fetch_atomicdb_explore_info,
        format_calculating_line,
        format_task_start_line,
    )
except (ImportError, ValueError):
    from chess_notation import (
        DEFAULT_ATOMICDB_SERVER,
        build_atomicdb_explore_url,
        fetch_atomicdb_explore_info,
        format_calculating_line,
        format_task_start_line,
    )


def _format_compact(value: int, unit_suffix: str = "", include_trillions: bool = False) -> str:
    try:
        n = max(0, int(value))
    except (TypeError, ValueError):
        return f"0{unit_suffix}"
    scales = [(1_000_000_000, "b"), (1_000_000, "m"), (1_000, "k")]
    if include_trillions:
        scales.insert(0, (1_000_000_000_000, "t"))
    for divisor, letter in scales:
        if n >= divisor:
            val = f"{n / divisor:.2f}".rstrip("0").rstrip(".")
            return f"{val}{letter}{unit_suffix}"
    return f"{n:,}{unit_suffix}" if unit_suffix else str(n)


def format_nodes_compact(nodes: int) -> str:
    """Formats node counts compactly (e.g. '128m', '512m', '2b', '500k')."""
    return _format_compact(nodes)


def format_nph(nph: int) -> str:
    """Formats nodes per hour compactly (e.g. '14.4b /hr', '512m /hr', '1.2t /hr')."""
    try:
        if int(nph) <= 0:
            return "0 /hr"
    except (TypeError, ValueError):
        return "0 /hr"
    return _format_compact(nph, " /hr", include_trillions=True)


def format_duration(seconds: float) -> str:
    """Formats seconds into human-readable duration (e.g. '14h 22m 30s', '45s')."""
    s = max(0, int(seconds))
    hours, rem = divmod(s, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def format_uptime_digital(seconds: float) -> str:
    """Formats seconds into 'HH:MM:SS'."""
    s = max(0, int(seconds))
    hours, rem = divmod(s, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class AnalyticsLogger:
    """Manages persistent USB-local task history, analytics, lifetime logs, and session graphs."""

    def __init__(self, base_dir: str, active_threads: int = 4):
        self.base_dir = os.path.abspath(base_dir)
        self.logs_dir = os.path.join(self.base_dir, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        self.active_threads = max(1, int(active_threads))
        self.device_name = (
            platform.node() or socket.gethostname() or os.environ.get("COMPUTERNAME")
            or os.environ.get("HOSTNAME") or "Unknown-Device"
        ).strip()

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

        self.session_start_time = time.time()
        self.session_tasks_completed = 0
        self.session_total_nodes = 0
        self.current_nps = 0
        self.session_average_nps = 0

        self.current_task_id: Optional[str] = None
        self.current_task_nodes: int = 0
        self.current_task_nodes_done: int = 0
        self.current_task_fen: Optional[str] = None
        self.current_task_line_moves: Optional[str] = None
        self.current_task_opening: Optional[str] = None
        self.current_task_url: Optional[str] = None
        self._current_task_last_pv: Optional[str] = None
        self.current_task_line: str = "Idle (waiting for next task)"
        self.current_task_start_time: Optional[float] = None
        self.current_task_initial_eta_seconds: Optional[int] = None
        self.current_task_eta_seconds: Optional[int] = None
        self.is_worker_paused: bool = False
        self.current_task_paused_at: Optional[float] = None
        self.current_task_paused_duration: float = 0.0
        self.server_url: str = DEFAULT_ATOMICDB_SERVER
        self.enable_explore_lookup: bool = True

        self.cpu_history: List[Dict[str, Any]] = []
        self.ram_history: List[Dict[str, Any]] = []
        self.nps_task_history: List[Dict[str, Any]] = []

        self.analytics_data = {
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
            "lifetime_tasks_completed": 0,
            "lifetime_total_nodes": 0,
            "lifetime_average_nps": 0,
            "lifetime_nph": 0,
            "lifetime_total_runtime_seconds": 0.0,
            "lifetime_cpu_hours": 0.0,
            "lifetime_total_sessions": 0,
        }

        self._re_analysis = re.compile(r"\[\d+\] task (\d+) \((\d+)n, ([\d\.]+)s\) -> (.*)")
        self._re_tb = re.compile(r"\[\d+\] task (\d+) TB wdl=(-?\d+)(?: dtz=(-?\d+))? -> (.*)")
        self._re_solve = re.compile(r"solve task (\d+) (.*?) \((\d+)n, ([\d\.]+)s\) -> (.*)")
        self._re_engine_fail = re.compile(r"\[\d+\] engine failure: (.*)")
        self._re_process_err = re.compile(r"\[WORKER ERROR\] Process exited with error code (-?\d+)")
        self._re_tb_status = re.compile(r"syzygy: (.*)")
        self._re_start_task = re.compile(r"(?:\[\d+\] )?starting (?:solve )?task (\d+) \((\d+)n\) calculating: (.*)")
        self._re_pv_line = re.compile(r"task pv: (.*)")
        self._re_task_progress = re.compile(r"task progress: nodes=(\d+) nps=(\d+)")

        self.load_persisted_data()

    def set_active_threads(self, threads: int):
        self.active_threads = max(1, int(threads))

    def add_listener(self, callback: Callable[[Dict[str, Any]], None]):
        self.listeners.append(callback)

    def _notify_listeners(self):
        summary = self.get_summary()
        for cb in self.listeners:
            try:
                cb(summary)
            except Exception as e:
                logger.debug(f"Listener error: {e}")

    def get_session_uptime(self) -> float:
        return max(0.0, time.time() - self.session_start_time)

    def get_session_uptime_str(self) -> str:
        return format_uptime_digital(self.get_session_uptime())

    def get_last_3_avg_nps(self) -> float:
        """Average NPS of up to the last 3 completed search tasks (divides by 1 or 2 when fewer done)."""
        session_recent = [t["nps"] for t in self.nps_task_history if t.get("nps", 0) > 0][-3:]
        if session_recent:
            return sum(session_recent) / len(session_recent)
        recent_nps = [t["nps"] for t in self.tasks_history if t.get("nps", 0) > 0][-3:]
        if recent_nps:
            return sum(recent_nps) / len(recent_nps)
        if self.current_nps > 0:
            return float(self.current_nps)
        uptime = self.get_session_uptime()
        if self.session_total_nodes > 0 and uptime > 0:
            return self.session_total_nodes / uptime
        lt_avg = self.analytics_data.get("lifetime_average_nps", 0)
        return float(lt_avg) if lt_avg > 0 else 0.0

    @staticmethod
    def filter_history_by_timeframe(
        series: List[Dict[str, Any]], timeframe_seconds: float, now: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        if not series:
            return []
        cutoff = (time.time() if now is None else float(now)) - float(timeframe_seconds)
        return [pt for pt in series if float(pt.get("time", 0.0)) >= cutoff]

    def calculate_estimated_time_remaining(self) -> Optional[int]:
        """Whole-second ETA stepping down 1s/s, pausing when worker is paused, negative when overdue."""
        if not self.current_task_id or self.current_task_initial_eta_seconds is None or self.current_task_start_time is None:
            return None
        ref_now = (
            self.current_task_paused_at
            if (self.is_worker_paused and self.current_task_paused_at is not None)
            else time.time()
        )
        elapsed_sec = int(round(max(0.0, ref_now - self.current_task_start_time - self.current_task_paused_duration)))
        return int(self.current_task_initial_eta_seconds) - elapsed_sec

    def pause_current_task(self):
        if not self.is_worker_paused:
            self.is_worker_paused = True
            self.current_task_paused_at = time.time()
            self.current_task_eta_seconds = self.calculate_estimated_time_remaining()
            self.write_current_task_log()
            self._notify_listeners()

    def resume_current_task(self):
        if self.is_worker_paused:
            if self.current_task_paused_at is not None:
                self.current_task_paused_duration += max(0.0, time.time() - self.current_task_paused_at)
            self.current_task_paused_at = None
            self.is_worker_paused = False
            self.current_task_eta_seconds = self.calculate_estimated_time_remaining()
            self.write_current_task_log()
            self._notify_listeners()

    def _clear_current_task_fields(self):
        self.current_task_id = None
        self.current_task_nodes = 0
        self.current_task_nodes_done = 0
        self.current_task_fen = None
        self.current_task_line_moves = None
        self.current_task_opening = None
        self.current_task_url = None
        self._current_task_last_pv = None
        self.current_task_line = "Idle (waiting for next task)"
        self.current_task_initial_eta_seconds = None
        self.current_task_eta_seconds = None
        self.current_task_start_time = None
        self.is_worker_paused = False
        self.current_task_paused_at = None
        self.current_task_paused_duration = 0.0

    def reset_current_task(self):
        self._clear_current_task_fields()
        self.write_current_task_log()
        self._notify_listeners()

    @staticmethod
    def format_eta_str(eta: Optional[float]) -> str:
        if eta is None:
            return "Calculating..."
        whole = int(round(eta))
        if whole == 0:
            return "0s"
        sign = "-" if whole < 0 else ""
        abs_eta = abs(whole)
        if abs_eta < 60:
            return f"{sign}{abs_eta}s"
        return f"{sign}{abs_eta // 60}m {abs_eta % 60:02d}s"

    def _atomic_write(self, dest_path: str, content: str):
        tmp_path = dest_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(tmp_path, dest_path)

    def load_persisted_data(self):
        try:
            if os.path.exists(self.analytics_file):
                with open(self.analytics_file, "r", encoding="utf-8") as f:
                    self.analytics_data.update(json.load(f))
        except Exception as e:
            logger.warning(f"Could not load analytics.json from USB: {e}")

        if self.analytics_data["lifetime_tasks_completed"] == 0 and self.analytics_data["total_tasks_completed"] > 0:
            self.analytics_data["lifetime_tasks_completed"] = self.analytics_data["total_tasks_completed"]
            self.analytics_data["lifetime_total_nodes"] = self.analytics_data["total_nodes_analyzed"]
            self.analytics_data["lifetime_total_runtime_seconds"] = self.analytics_data["total_time_seconds"]
            self.analytics_data["lifetime_average_nps"] = self.analytics_data["average_nps"]
            self.analytics_data["lifetime_cpu_hours"] = round(
                (self.analytics_data["lifetime_total_runtime_seconds"] * self.active_threads) / 3600.0, 4
            )

        lt_runtime = self.analytics_data.get("lifetime_total_runtime_seconds", 0.0)
        lt_nodes = self.analytics_data.get("lifetime_total_nodes", 0)
        self.analytics_data["lifetime_nph"] = int(round((lt_nodes * 3600.0) / lt_runtime)) if lt_runtime > 0 else 0
        self.analytics_data["lifetime_total_sessions"] += 1

        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self.tasks_history = json.load(f)[-5000:]
        except Exception as e:
            logger.warning(f"Could not load history.json from USB: {e}")

        self.save_persisted_data()
        self.write_lifetime_statistics_txt()
        self.log_session_event("Client session initialized")

    def save_persisted_data(self):
        try:
            self._atomic_write(self.analytics_file, json.dumps(self.get_summary(), indent=2))
        except Exception as e:
            logger.error(f"Error persisting analytics to USB: {e}")
        try:
            self._atomic_write(self.history_file, json.dumps(self.tasks_history[-2000:], indent=2))
        except Exception as e:
            logger.error(f"Error persisting history to USB: {e}")

    def write_lifetime_statistics_txt(self):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tasks = self.analytics_data.get("lifetime_tasks_completed", 0)
            nodes = self.analytics_data.get("lifetime_total_nodes", 0)
            avg_nps = self.analytics_data.get("lifetime_average_nps", 0)
            runtime_sec = self.analytics_data.get("lifetime_total_runtime_seconds", 0.0)
            lt_nph = self.analytics_data.get(
                "lifetime_nph", int(round((nodes * 3600.0) / runtime_sec)) if runtime_sec > 0 else 0
            )
            cpu_hrs = self.analytics_data.get("lifetime_cpu_hours", 0.0)
            sessions = self.analytics_data.get("lifetime_total_sessions", 1)
            cpu_hrs_str = f"{cpu_hrs:.4f}" if (0 < cpu_hrs < 0.1) else f"{cpu_hrs:.2f}"

            content = (
                "===================================================================\n"
                "   ATOMICDB PORTABLE — LIFETIME STATISTICS (PERMANENT USB LOG)     \n"
                "===================================================================\n"
                f"Last Updated:             {ts}\n"
                f"Last Device:              {self.device_name}\n"
                f"Total Tasks Completed:    {tasks:,}\n"
                f"Total Lifetime Nodes:     {nodes:,} ({format_nodes_compact(nodes)})\n"
                f"Lifetime Average NPS:     {avg_nps:,} nodes/sec\n"
                f"Lifetime Nodes/Hour:      {format_nph(lt_nph)} ({lt_nph:,} nodes/hr)\n"
                f"Total Accumulated Time:   {format_duration(runtime_sec)} ({int(runtime_sec):,} seconds)\n"
                f"Total CPU Hours:          {cpu_hrs_str} CPU hours\n"
                f"Total Number of Sessions: {sessions:,} sessions\n"
                "===================================================================\n"
                "NOTICE: This log records all historical analysis performed from\n"
                "this portable drive. Logs and metrics are preserved permanently.\n"
                "===================================================================\n"
            )
            self._atomic_write(self.lifetime_txt_file, content)
        except Exception as e:
            logger.error(f"Error writing lifetime_statistics.txt: {e}")

    def write_current_task_log(self):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            eta_str = self.format_eta_str(self.calculate_estimated_time_remaining()) if self.current_task_id else "-"
            content = (
                f"[{ts}] [CURRENT TASK]\n"
                f"Device Name:              {self.device_name}\n"
                f"Task ID:                  {self.current_task_id or 'IDLE'}\n"
                f"Budget Nodes:             {format_nodes_compact(self.current_task_nodes)} ({self.current_task_nodes:,})\n"
                f"Nodes Done So Far:        {format_nodes_compact(self.current_task_nodes_done)} ({self.current_task_nodes_done:,})\n"
                f"Estimated Time Remaining: {eta_str}\n"
                f"Calculating Line:         {self.current_task_line or 'None'}\n"
                f"Explorer URL:             {self.current_task_url or 'None'}\n"
            )
            with open(self.current_task_file, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.debug(f"Error writing current_task.log: {e}")

    def log_session_event(self, event_note: str = ""):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            nodes = self.session_total_nodes
            log_line = (
                f"[{ts}] Device: {self.device_name} | Session Uptime: {self.get_session_uptime_str()} | "
                f"Tasks: {self.session_tasks_completed} | Nodes: {format_nodes_compact(nodes)} ({nodes:,}) | "
                f"Current NPS: {self.current_nps:,} | Avg NPS: {self.session_average_nps:,} | Note: {event_note}\n"
            )
            with open(self.session_log_file, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            logger.debug(f"Error appending to session_statistics.log: {e}")

    def record_hardware_sample(self, sys_cpu: float, worker_cpu: float, worker_ram_mb: int, available_ram_mb: int):
        """Records a real-time CPU & RAM sample for session graphs (retained >10m at 1s refresh)."""
        now = time.time()
        ts_str = datetime.now().strftime("%H:%M:%S")

        self.cpu_history.append({
            "time": now, "timestamp": ts_str,
            "system_cpu": round(float(sys_cpu), 1), "worker_cpu": round(float(worker_cpu), 1),
        })
        if len(self.cpu_history) > 700:
            self.cpu_history.pop(0)

        self.ram_history.append({
            "time": now, "timestamp": ts_str,
            "worker_ram": int(worker_ram_mb), "available_ram": int(available_ram_mb),
        })
        if len(self.ram_history) > 700:
            self.ram_history.pop(0)

        uptime = self.get_session_uptime()
        if uptime > 0 and self.session_total_nodes > 0:
            self.session_average_nps = int(self.session_total_nodes / uptime)

    def _apply_explore_info(self, task_id: str, fen: str, info: Optional[Dict[str, str]]):
        if not info or self.current_task_id != task_id or self.current_task_fen != fen:
            return
        opening = (info.get("opening_name") or "").strip()
        play_uci = (info.get("play_uci") or "").strip()
        if opening:
            self.current_task_opening = opening
        if play_uci and not self.current_task_line_moves:
            self.current_task_line_moves = play_uci
        self.current_task_url = info.get("url") or build_atomicdb_explore_url(
            fen, self.current_task_line_moves, self.server_url
        )
        if self.current_task_line_moves:
            self.current_task_line = format_calculating_line(
                fen,
                "",
                prefix_moves=self.current_task_line_moves,
                max_moves=None,
                opening_name=self.current_task_opening,
            )
        elif self._current_task_last_pv:
            self.current_task_line = format_calculating_line(
                fen,
                self._current_task_last_pv,
                max_moves=8,
                opening_name=self.current_task_opening,
            )
        elif self.current_task_opening:
            self.current_task_line = format_task_start_line(
                fen,
                prefix_moves=self.current_task_line_moves,
                max_moves=None,
                opening_name=self.current_task_opening,
            )
        self.write_current_task_log()
        self._notify_listeners()

    def _resolve_explore_async(self, task_id: str, fen: str):
        info = fetch_atomicdb_explore_info(fen, self.server_url)
        self._apply_explore_info(task_id, fen, info)

    def record_task_start(self, task_id: str, budget_nodes: int, line_info: str):
        self.current_task_id = str(task_id)
        self.current_task_nodes = int(budget_nodes)
        self.current_task_nodes_done = 0
        self.current_task_opening = None
        self._current_task_last_pv = None
        raw_info = str(line_info).strip()
        if " | line_moves: " in raw_info:
            fen_part, moves_part = raw_info.split(" | line_moves: ", 1)
            self.current_task_fen = fen_part.strip()
            self.current_task_line_moves = moves_part.strip() or None
        else:
            self.current_task_fen = raw_info
            self.current_task_line_moves = None

        self.current_task_url = build_atomicdb_explore_url(
            self.current_task_fen, self.current_task_line_moves, self.server_url
        )
        self.current_task_line = format_task_start_line(
            self.current_task_fen,
            prefix_moves=self.current_task_line_moves,
            max_moves=None,
            opening_name=self.current_task_opening,
        )
        self.current_task_start_time = time.time()
        self.is_worker_paused = False
        self.current_task_paused_at = None
        self.current_task_paused_duration = 0.0

        avg_3 = self.get_last_3_avg_nps()
        self.current_task_initial_eta_seconds = (
            int(round(float(self.current_task_nodes) / float(avg_3)))
            if (avg_3 > 0 and self.current_task_nodes > 0)
            else None
        )
        self.current_task_eta_seconds = self.current_task_initial_eta_seconds
        self.write_current_task_log()
        self._notify_listeners()

        if (
            self.enable_explore_lookup
            and not self.current_task_line_moves
            and self.current_task_fen
            and "/" in self.current_task_fen
            and not self.current_task_fen.lower().startswith("solve ")
        ):
            threading.Thread(
                target=self._resolve_explore_async,
                args=(self.current_task_id, self.current_task_fen),
                daemon=True,
            ).start()

    def update_task_progress(self, nodes_done: int, current_nps: int):
        self.current_task_nodes_done = max(self.current_task_nodes_done, int(nodes_done))
        self.current_nps = int(current_nps)
        self._notify_listeners()

    def update_task_pv(self, pv_line: str):
        self._current_task_last_pv = pv_line
        if self.current_task_line_moves:
            # Chronological move line from move 1 to the task position is already known;
            # keep displaying it rather than overwriting with post-FEN search PV.
            return
        self.current_task_line = format_calculating_line(
            self.current_task_fen,
            pv_line,
            prefix_moves=None,
            max_moves=8,
            opening_name=self.current_task_opening,
        )
        self._notify_listeners()

    def record_task(
        self, task_id: str, nodes: int, elapsed_sec: float, summary: str,
        is_tb: bool = False, wdl: Optional[int] = None, dtz: Optional[int] = None, is_solve: bool = False
    ):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nps = int(nodes / elapsed_sec) if elapsed_sec > 0 else 0
        self.current_nps = nps
        task_type = "Tablebase" if is_tb else ("Solve" if is_solve else "Engine")

        item: Dict[str, Any] = {
            "task_id": str(task_id), "timestamp": timestamp, "device": self.device_name,
            "type": task_type, "nodes": int(nodes), "elapsed_sec": round(float(elapsed_sec), 2),
            "nps": nps, "summary": str(summary).strip(),
        }
        if wdl is not None:
            item["wdl"] = item["tb_wdl"] = int(wdl)
        if dtz is not None:
            item["dtz"] = item["tb_dtz"] = int(dtz)

        self.tasks_history.append(item)
        if len(self.tasks_history) > 5000:
            self.tasks_history.pop(0)

        self.session_tasks_completed += 1
        self.session_total_nodes += int(nodes)
        self.session_average_nps = int(self.session_total_nodes / max(1.0, self.get_session_uptime()))

        self.nps_task_history.append({
            "task_id": str(task_id), "nps": nps, "nodes": int(nodes),
            "elapsed": round(float(elapsed_sec), 2), "device": self.device_name,
            "timestamp": datetime.now().strftime("%H:%M:%S"), "time": time.time(),
        })
        if len(self.nps_task_history) > 500:
            self.nps_task_history.pop(0)

        ad = self.analytics_data
        ad["total_tasks_completed"] += 1
        ad["total_nodes_analyzed"] += int(nodes)
        ad["total_time_seconds"] = round(ad["total_time_seconds"] + float(elapsed_sec), 2)
        ad["average_nodes_per_task"] = ad["total_nodes_analyzed"] // ad["total_tasks_completed"]
        ad["average_nps"] = int(ad["total_nodes_analyzed"] / ad["total_time_seconds"]) if ad["total_time_seconds"] > 0 else 0

        ad["lifetime_tasks_completed"] += 1
        ad["lifetime_total_nodes"] += int(nodes)
        ad["lifetime_total_runtime_seconds"] = round(ad.get("lifetime_total_runtime_seconds", 0.0) + float(elapsed_sec), 2)
        lt_rt = ad["lifetime_total_runtime_seconds"]
        ad["lifetime_average_nps"] = int(ad["lifetime_total_nodes"] / lt_rt) if lt_rt > 0 else 0
        ad["lifetime_nph"] = int(round((ad["lifetime_total_nodes"] * 3600.0) / lt_rt)) if lt_rt > 0 else 0
        ad["lifetime_cpu_hours"] = round(ad.get("lifetime_cpu_hours", 0.0) + (float(elapsed_sec) * self.active_threads) / 3600.0, 4)

        type_key = "tablebase_hits" if is_tb else ("solve_tasks" if is_solve else "engine_tasks")
        ad[type_key] += 1
        ad["last_task_at"] = timestamp
        ad["last_task_id"] = str(task_id)
        ad["last_device"] = self.device_name

        self._clear_current_task_fields()

        try:
            with open(self.activity_log_file, "a", encoding="utf-8") as f:
                f.write(
                    f"[{timestamp}] [TASK DONE] Device: {self.device_name} | ID: {task_id} | Type: {task_type} | "
                    f"Nodes: {format_nodes_compact(nodes)} ({nodes:,}) | Time: {elapsed_sec:.2f}s | NPS: {nps:,} | {summary}\n"
                )
        except Exception as e:
            logger.warning(f"Could not append to activity.log on USB: {e}")

        self.write_current_task_log()
        self.log_session_event(f"Task {task_id} completed ({format_nodes_compact(nodes)} nodes, {nps:,} NPS)")
        self.save_persisted_data()
        self.write_lifetime_statistics_txt()
        self._notify_listeners()

    def record_crash(self, event_type: str, details: str):
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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.system_log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [SYSTEM] {message}\n")
        except Exception:
            pass

    def parse_worker_line(self, line: str):
        if not line:
            return
        clean = line.strip()

        if m := self._re_start_task.search(clean):
            task_id, budget_n, line_info = m.groups()
            self.record_task_start(task_id, int(budget_n), line_info)
        elif m := self._re_pv_line.search(clean):
            self.update_task_pv(m.group(1))
        elif m := self._re_task_progress.search(clean):
            nodes_val, nps_val = m.groups()
            self.update_task_progress(int(nodes_val), int(nps_val))
        elif m := self._re_analysis.search(clean):
            task_id, nodes_s, elapsed_s, summary = m.groups()
            self.record_task(task_id, int(nodes_s), float(elapsed_s), summary, is_tb=False)
        elif m := self._re_tb.search(clean):
            task_id, wdl_s, dtz_s, summary = m.groups()
            self.record_task(
                task_id, 0, 0.01, summary, is_tb=True,
                wdl=int(wdl_s) if wdl_s is not None else None,
                dtz=int(dtz_s) if dtz_s is not None else None,
            )
        elif m := self._re_solve.search(clean):
            task_id, outcome, nodes_s, elapsed_s, summary = m.groups()
            self.record_task(task_id, int(nodes_s), float(elapsed_s), f"{outcome}: {summary}", is_solve=True)
        elif m := self._re_engine_fail.search(clean):
            self.record_crash("ENGINE_FAILURE", m.group(1))
        elif m := self._re_process_err.search(clean):
            self.reset_current_task()
            self.record_crash("WORKER_EXIT_ERROR", f"Exit code {m.group(1)}")
        elif (
            "interrupted by the stop" in clean
            or "[SUPERVISOR] Process ended cleanly" in clean
            or "[SUPERVISOR] Worker process terminated cleanly" in clean
        ):
            self.reset_current_task()
        elif m := self._re_tb_status.search(clean):
            self.record_system_event(f"Syzygy status: {m.group(1)}")

    def get_summary(self) -> Dict[str, Any]:
        uptime_sec = self.get_session_uptime()
        eta = self.calculate_estimated_time_remaining()

        session_avg_nps = int(self.session_total_nodes / uptime_sec) if (uptime_sec > 0 and self.session_total_nodes > 0) else self.session_average_nps
        if self.session_total_nodes > 0:
            session_nph = int(round((self.session_total_nodes * 3600.0) / max(1.0, uptime_sec)))
        elif self.current_nps > 0:
            session_nph = int(self.current_nps * 3600)
        else:
            session_nph = 0

        lt_runtime = self.analytics_data.get("lifetime_total_runtime_seconds", 0.0)
        lt_nodes = self.analytics_data.get("lifetime_total_nodes", 0)
        lifetime_nph = int(round((lt_nodes * 3600.0) / lt_runtime)) if lt_runtime > 0 else 0

        return {
            **self.analytics_data,
            "device_name": self.device_name,
            "is_worker_paused": self.is_worker_paused,
            "session_tasks_completed": self.session_tasks_completed,
            "session_total_nodes": self.session_total_nodes,
            "current_nps": self.current_nps,
            "session_average_nps": session_avg_nps,
            "session_nph": session_nph,
            "session_uptime_seconds": round(uptime_sec, 1),
            "session_uptime_str": self.get_session_uptime_str(),
            "current_task_id": self.current_task_id,
            "current_task_nodes": self.current_task_nodes,
            "current_task_nodes_done": self.current_task_nodes_done,
            "current_task_line": self.current_task_line,
            "current_task_url": self.current_task_url,
            "current_task_eta_seconds": int(eta) if eta is not None else None,
            "current_task_eta_str": self.format_eta_str(eta) if self.current_task_id else "-",
            "lifetime_tasks_completed": self.analytics_data.get("lifetime_tasks_completed", 0),
            "lifetime_total_nodes": lt_nodes,
            "lifetime_average_nps": self.analytics_data.get("lifetime_average_nps", 0),
            "lifetime_nph": lifetime_nph,
            "lifetime_total_runtime_seconds": lt_runtime,
            "lifetime_total_runtime_str": format_duration(lt_runtime),
            "lifetime_cpu_hours": round(self.analytics_data.get("lifetime_cpu_hours", 0.0), 4),
            "lifetime_total_sessions": self.analytics_data.get("lifetime_total_sessions", 1),
            # Graph series (this session, retaining >10 minutes at 1s refresh)
            "cpu_history": list(self.cpu_history[-700:]),
            "ram_history": list(self.ram_history[-700:]),
            "nps_task_history": list(self.nps_task_history[-200:]),
            "recent_tasks": list(reversed(self.tasks_history[-100:])),
        }

    def clear_history(self):
        """Permanent preservation policy: logs and lifetime statistics are never cleared."""
        logger.info("Permanent preservation rule: USB logs and lifetime statistics cannot be cleared.")
        self._notify_listeners()
