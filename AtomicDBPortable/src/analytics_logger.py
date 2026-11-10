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
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("AtomicDB.Analytics")

class AnalyticsLogger:
    """Manages persistent USB-local task history, node analytics, and crash logs."""

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        self.logs_dir = os.path.join(self.base_dir, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)

        self.history_file = os.path.join(self.logs_dir, "history.json")
        self.analytics_file = os.path.join(self.logs_dir, "analytics.json")
        self.activity_log_file = os.path.join(self.logs_dir, "activity.log")
        self.crashes_log_file = os.path.join(self.logs_dir, "crashes.log")
        self.system_log_file = os.path.join(self.logs_dir, "system.log")

        self.listeners: List[Callable[[Dict[str, Any]], None]] = []
        self.tasks_history: List[Dict[str, Any]] = []

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
            "last_task_id": None
        }

        # Compiled regex matchers for official upstream worker stdout
        self._re_analysis = re.compile(r"\[\d+\] task (\d+) \((\d+)n, ([\d\.]+)s\) -> (.*)")
        self._re_tb = re.compile(r"\[\d+\] task (\d+) TB wdl=(-?\d+)(?: dtz=(-?\d+))? -> (.*)")
        self._re_solve = re.compile(r"solve task (\d+) (.*?) \((\d+)n, ([\d\.]+)s\) -> (.*)")
        self._re_engine_fail = re.compile(r"\[\d+\] engine failure: (.*)")
        self._re_process_err = re.compile(r"\[WORKER ERROR\] Process exited with error code (-?\d+)")
        self._re_tb_status = re.compile(r"syzygy: (.*)")

        self.load_persisted_data()

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

    def load_persisted_data(self):
        """Loads prior history and analytics from USB logs directory."""
        try:
            if os.path.exists(self.analytics_file):
                with open(self.analytics_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.analytics_data.update(data)
        except Exception as e:
            logger.warning(f"Could not load analytics.json from USB: {e}")

        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self.tasks_history = json.load(f)
                    # Keep memory capped at 5000 items
                    if len(self.tasks_history) > 5000:
                        self.tasks_history = self.tasks_history[-5000:]
        except Exception as e:
            logger.warning(f"Could not load history.json from USB: {e}")

    def save_persisted_data(self):
        """Atomically saves analytics and history to the USB drive."""
        try:
            temp_analytics = self.analytics_file + ".tmp"
            with open(temp_analytics, "w", encoding="utf-8") as f:
                json.dump(self.analytics_data, f, indent=2)
            if os.path.exists(self.analytics_file):
                os.remove(self.analytics_file)
            os.rename(temp_analytics, self.analytics_file)
        except Exception as e:
            logger.error(f"Error persisting analytics to USB: {e}")

        try:
            temp_hist = self.history_file + ".tmp"
            with open(temp_hist, "w", encoding="utf-8") as f:
                json.dump(self.tasks_history[-1000:], f, indent=2)
            if os.path.exists(self.history_file):
                os.remove(self.history_file)
            os.rename(temp_hist, self.history_file)
        except Exception as e:
            logger.error(f"Error persisting history to USB: {e}")

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

        task_type = "Tablebase" if is_tb else ("Solve" if is_solve else "Engine")

        item = {
            "task_id": str(task_id),
            "timestamp": timestamp,
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

        # Update running aggregates
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

        if is_tb:
            self.analytics_data["tablebase_hits"] += 1
        elif is_solve:
            self.analytics_data["solve_tasks"] += 1
        else:
            self.analytics_data["engine_tasks"] += 1

        self.analytics_data["last_task_at"] = timestamp
        self.analytics_data["last_task_id"] = str(task_id)

        # Append to human-readable activity.log on USB
        try:
            with open(self.activity_log_file, "a", encoding="utf-8") as f:
                f.write(
                    f"[{timestamp}] [TASK DONE] ID: {task_id} | Type: {task_type} | "
                    f"Nodes: {nodes:,} | Time: {elapsed_sec:.2f}s | NPS: {nps:,} | {summary}\n"
                )
        except Exception as e:
            logger.warning(f"Could not append to activity.log on USB: {e}")

        self.save_persisted_data()
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
            self.record_crash("WORKER_EXIT_ERROR", f"Exit code {m5.group(1)}")
            return

        # 6. Syzygy download status logging
        m6 = self._re_tb_status.search(clean)
        if m6:
            self.record_system_event(f"Syzygy status: {m6.group(1)}")

    def get_summary(self) -> Dict[str, Any]:
        """Returns consolidated analytics for display."""
        return {
            **self.analytics_data,
            "recent_tasks": list(reversed(self.tasks_history[-100:]))
        }

    def clear_history(self):
        """Clears local USB history and resets counters if requested."""
        self.tasks_history.clear()
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
            "last_task_id": None
        }
        self.save_persisted_data()
        self._notify_listeners()
