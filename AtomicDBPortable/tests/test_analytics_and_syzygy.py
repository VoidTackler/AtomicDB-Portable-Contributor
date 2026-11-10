"""
Automated Tests: Local USB Analytics Logging, Syzygy Tablebase Toggle, and Solver Fallback Probe
"""

import os
import sys
import tempfile
import shutil
import unittest

from AtomicDBPortable.src.analytics_logger import AnalyticsLogger
from AtomicDBPortable.src.worker_manager import WorkerManager
from AtomicDBPortable.worker.atomicdb_worker import probe_solver_support, resolve_syzygy

class TestAnalyticsAndSyzygy(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.logger = AnalyticsLogger(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_analytics_directories_created_on_usb(self):
        logs_dir = os.path.join(self.test_dir, "logs")
        self.assertTrue(os.path.isdir(logs_dir))

    def test_parse_standard_analysis_line(self):
        line = "[0] task 1042 (5000000n, 2.50s) -> score cp 35 pv e2e4"
        self.logger.parse_worker_line(line)
        summary = self.logger.get_summary()

        self.assertEqual(summary["total_tasks_completed"], 1)
        self.assertEqual(summary["total_nodes_analyzed"], 5000000)
        self.assertEqual(summary["average_nodes_per_task"], 5000000)
        self.assertEqual(summary["engine_tasks"], 1)
        self.assertEqual(len(summary["recent_tasks"]), 1)
        self.assertEqual(summary["recent_tasks"][0]["task_id"], "1042")

    def test_parse_tablebase_hit(self):
        line = "[1] task 2048 TB wdl=1 dtz=3 -> mate 4"
        self.logger.parse_worker_line(line)
        summary = self.logger.get_summary()

        self.assertEqual(summary["total_tasks_completed"], 1)
        self.assertEqual(summary["tablebase_hits"], 1)
        self.assertEqual(summary["recent_tasks"][0]["wdl"], 1)
        self.assertEqual(summary["recent_tasks"][0]["dtz"], 3)

    def test_parse_solve_task(self):
        line = "solve task 7115 PROVEN_WIN (12000000n, 6.00s) -> 1. e4"
        self.logger.parse_worker_line(line)
        summary = self.logger.get_summary()

        self.assertEqual(summary["total_tasks_completed"], 1)
        self.assertEqual(summary["solve_tasks"], 1)
        self.assertEqual(summary["total_nodes_analyzed"], 12000000)

    def test_parse_engine_failure_and_crash_logging(self):
        fail_line = "[0] engine failure: [Errno 22] Invalid argument; restarting the engine"
        self.logger.parse_worker_line(fail_line)
        summary = self.logger.get_summary()

        self.assertEqual(summary["crashes"], 1)
        self.assertEqual(summary["engine_restarts"], 1)
        # Check that crashes.log contains the event
        crashes_path = os.path.join(self.test_dir, "logs", "crashes.log")
        self.assertTrue(os.path.exists(crashes_path))
        with open(crashes_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Invalid argument", content)

    def test_persistence_on_usb(self):
        # Record tasks and save
        self.logger.parse_worker_line("[0] task 500 (1000000n, 1.00s) -> cp 10")
        self.logger.save_persisted_data()

        # Create new instance pointing to same USB folder
        reloaded = AnalyticsLogger(self.test_dir)
        summary = reloaded.get_summary()
        self.assertEqual(summary["total_tasks_completed"], 1)
        self.assertEqual(summary["total_nodes_analyzed"], 1000000)

    def test_syzygy_toggle_arguments(self):
        wm = WorkerManager("python", "worker/atomicdb_worker.py")

        # When no_fetch_syzygy=True, --no-fetch-syzygy must be present
        cmd_no_tb = wm.build_command_args(
            username="PortableExe",
            password="ExePassword",
            server_url="https://belzedar.duckdns.org",
            no_fetch_syzygy=True
        )
        self.assertIn("--no-fetch-syzygy", cmd_no_tb)
        self.assertNotIn("--fetch-syzygy", cmd_no_tb)

        # When no_fetch_syzygy=False, --fetch-syzygy must be present
        cmd_tb = wm.build_command_args(
            username="PortableExe",
            password="ExePassword",
            server_url="https://belzedar.duckdns.org",
            no_fetch_syzygy=False
        )
        self.assertIn("--fetch-syzygy", cmd_tb)
        self.assertNotIn("--no-fetch-syzygy", cmd_tb)

    def test_resolve_syzygy_worker_logic(self):
        class DummyArgs:
            def __init__(self, syzygy='', no_fetch=False):
                self.syzygy = syzygy
                self.no_fetch_syzygy = no_fetch

        # When no_fetch_syzygy is True, resolve_syzygy returns empty string and logs disabled
        logs = []
        res = resolve_syzygy(DummyArgs(no_fetch=True), "http://server", log=logs.append)
        self.assertEqual(res, '')
        self.assertTrue(any("disabled" in m for m in logs))

        # Explicit path always wins
        res_custom = resolve_syzygy(DummyArgs(syzygy='D:/Custom/TB'), "http://server")
        self.assertEqual(res_custom, 'D:/Custom/TB')

    def test_probe_solver_support_nonexistent(self):
        # Nonexistent binary returns False safely without error
        res = probe_solver_support("/nonexistent/engine_binary.exe")
        self.assertFalse(res)

if __name__ == "__main__":
    unittest.main()
