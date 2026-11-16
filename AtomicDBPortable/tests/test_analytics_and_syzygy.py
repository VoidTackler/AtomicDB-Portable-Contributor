"""
Automated Tests: Local USB Analytics Logging, Syzygy Tablebase Toggle, and Solver Fallback Probe
"""

import os
import sys
import tempfile
import shutil
import unittest

from AtomicDBPortable.src.analytics_logger import AnalyticsLogger, format_nodes_compact
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

    def test_session_statistics_tracking_and_logging(self):
        # Initial session metrics
        summary = self.logger.get_summary()
        self.assertEqual(summary["session_tasks_completed"], 0)
        self.assertEqual(summary["session_total_nodes"], 0)

        # Complete two tasks
        self.logger.parse_worker_line("[0] task 101 (2000000n, 1.00s) -> score cp 12")
        self.logger.parse_worker_line("[0] task 102 (3000000n, 1.50s) -> score cp 15")

        summary = self.logger.get_summary()
        self.assertEqual(summary["session_tasks_completed"], 2)
        self.assertEqual(summary["session_total_nodes"], 5000000)
        self.assertGreater(summary["current_nps"], 0)
        self.assertGreater(summary["session_average_nps"], 0)
        self.assertIn(":", summary["session_uptime_str"])

        # Check session_statistics.log file
        session_log = os.path.join(self.test_dir, "logs", "session_statistics.log")
        self.assertTrue(os.path.exists(session_log))
        with open(session_log, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Session Uptime", content)
            self.assertIn("Task 102 completed", content)

    def test_current_task_eta_calculation_and_line_logging(self):
        # Populate history with 3 tasks to establish known NPS average (2,000,000 NPS each)
        self.logger.parse_worker_line("[0] task 1 (2000000n, 1.00s) -> cp 10")
        self.logger.parse_worker_line("[0] task 2 (2000000n, 1.00s) -> cp 15")
        self.logger.parse_worker_line("[0] task 3 (2000000n, 1.00s) -> cp 20")

        # Start a task of 6,000,000 nodes calculating a specific position
        self.logger.parse_worker_line("[0] starting task 7115 (6000000n) calculating: r5k1/p3p3/2ppb1pb/Q2P4/5p1p/5P2/PPP3PP/R1B1R1K1 b - - 0 1")

        summary = self.logger.get_summary()
        self.assertEqual(summary["current_task_id"], "7115")
        self.assertEqual(summary["current_task_nodes"], 6000000)
        self.assertIn("r5k1", summary["current_task_line"])
        # With 6M nodes and 2M/s avg NPS, ETA should be integer 3s
        self.assertEqual(summary["current_task_eta_seconds"], 3)

        # Update PV line during search (kept in memory for UI)
        self.logger.parse_worker_line("task pv: e6d5 e1e8 g8g7 a5c3")
        summary = self.logger.get_summary()
        self.assertEqual(summary["current_task_line"], "e6d5 e1e8 g8g7 a5c3")

        # Simulate 1 second elapsed: ETA reduces by 1s/s
        self.logger.current_task_start_time -= 1.0
        summary = self.logger.get_summary()
        self.assertEqual(summary["current_task_eta_seconds"], 2)

        # Simulate task taking longer than initial estimate: ETA goes negative
        self.logger.current_task_start_time -= 4.0  # 5 seconds elapsed total vs 3s budget
        summary = self.logger.get_summary()
        self.assertEqual(summary["current_task_eta_seconds"], -2)
        self.assertEqual(summary["current_task_eta_str"], "-2s")

        # Check current_task.log
        cur_task_file = os.path.join(self.test_dir, "logs", "current_task.log")
        self.assertTrue(os.path.exists(cur_task_file))
        with open(cur_task_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Task ID:                  7115", content)
            self.assertIn("Budget Nodes:             6m (6,000,000)", content)

    def test_lifetime_statistics_txt_file_and_preservation(self):
        # Complete task and verify lifetime stats
        self.logger.parse_worker_line("[0] task 999 (4000000n, 2.00s) -> score cp 30")

        summary = self.logger.get_summary()
        self.assertEqual(summary["lifetime_tasks_completed"], 1)
        self.assertEqual(summary["lifetime_total_nodes"], 4000000)
        self.assertEqual(summary["lifetime_total_sessions"], 1)
        self.assertGreater(summary["lifetime_cpu_hours"], 0.0)

        # Verify lifetime_statistics.txt exists and is formatted
        txt_file = os.path.join(self.test_dir, "logs", "lifetime_statistics.txt")
        self.assertTrue(os.path.exists(txt_file))
        with open(txt_file, "r", encoding="utf-8") as f:
            txt_content = f.read()
            self.assertIn("LIFETIME STATISTICS", txt_content)
            self.assertIn("Total Tasks Completed:    1", txt_content)
            self.assertIn("Total Lifetime Nodes:     4,000,000", txt_content)
            self.assertIn("Total Number of Sessions: 1 sessions", txt_content)

        # Verify that clear_history DOES NOT wipe lifetime data or files
        self.logger.clear_history()
        summary_after = self.logger.get_summary()
        self.assertEqual(summary_after["lifetime_tasks_completed"], 1)
        self.assertTrue(os.path.exists(txt_file))

    def test_graphs_hardware_and_nps_series(self):
        # Record hardware samples
        self.logger.record_hardware_sample(sys_cpu=35.5, worker_cpu=22.1, worker_ram_mb=256, available_ram_mb=4096)
        self.logger.record_hardware_sample(sys_cpu=40.0, worker_cpu=25.0, worker_ram_mb=260, available_ram_mb=4090)

        # Record task completion
        self.logger.parse_worker_line("[0] task 50 (1000000n, 0.50s) -> cp 5")

        summary = self.logger.get_summary()
        self.assertEqual(len(summary["cpu_history"]), 2)
        self.assertEqual(summary["cpu_history"][-1]["system_cpu"], 40.0)
        self.assertEqual(len(summary["ram_history"]), 2)
        self.assertEqual(summary["ram_history"][-1]["worker_ram"], 260)
        self.assertEqual(len(summary["nps_task_history"]), 1)
        self.assertEqual(summary["nps_task_history"][0]["task_id"], "50")

    def test_eta_1s_countdown_through_zero_and_zero_node_tb_exclusion(self):
        # 3 search tasks at 2,000,000 NPS + 1 tablebase hit (0 nodes, 0 nps)
        self.logger.parse_worker_line("[0] task 1 (2000000n, 1.00s) -> cp 10")
        self.logger.parse_worker_line("[0] task 2 (2000000n, 1.00s) -> cp 15")
        self.logger.parse_worker_line("[0] task 3 (2000000n, 1.00s) -> cp 20")
        self.logger.parse_worker_line("[0] task 4 TB wdl=0 dtz=0 -> cp 0")

        # TB hit must be ignored by last-3-tasks NPS average
        self.assertAlmostEqual(self.logger.get_last_3_avg_nps(), 2_000_000.0, delta=10.0)

        # Start 2.4s raw budget (4.8M nodes @ 2M/s) -> rounded to whole 2s (no decimals)
        self.logger.parse_worker_line("[0] starting task 8001 (4800000n) calculating: e2e4")
        self.assertEqual(self.logger.current_task_initial_eta_seconds, 2)
        t0 = self.logger.current_task_start_time
        expected = ["2s", "1s", "0s", "-1s", "-2s"]
        for step_sec, exp_str in enumerate(expected):
            self.logger.current_task_start_time = t0 - float(step_sec)
            eta = self.logger.calculate_estimated_time_remaining()
            self.assertEqual(eta, 2 - step_sec)
            self.assertEqual(AnalyticsLogger.format_eta_str(eta), exp_str)

        # Check rounding and minute formatting with zero-padded seconds (never decimals)
        self.assertEqual(AnalyticsLogger.format_eta_str(-0.4), "0s")
        self.assertEqual(AnalyticsLogger.format_eta_str(-0.6), "-1s")
        self.assertEqual(AnalyticsLogger.format_eta_str(65), "1m 05s")
        self.assertEqual(AnalyticsLogger.format_eta_str(-65), "-1m 05s")

    def test_gui_button_contrast_and_eta_timer_configuration(self):
        gui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "gui.py")
        with open(gui_path, "r", encoding="utf-8") as f:
            gui_src = f.read()

        # Verify explicit high-contrast styling for Start/Pause/Emergency buttons and disabled states
        self.assertIn("QPushButton#btnStart", gui_src)
        self.assertIn("QPushButton#btnStart:disabled", gui_src)
        self.assertIn("QPushButton#btnStop", gui_src)
        self.assertIn("QPushButton#btnStop:disabled", gui_src)
        self.assertIn("QPushButton#btnLocalStop:checked", gui_src)
        # Ensure unscoped controlsContainer stylesheet does not override buttons
        self.assertIn("QWidget#controlsContainer {", gui_src)
        # Ensure dedicated 1000ms timer for ETA countdown & uptime alongside 800ms telemetry timer
        self.assertIn("self.timer.start(800)", gui_src)
        self.assertIn("self.eta_timer.start(1000)", gui_src)
        self.assertIn("_refresh_eta_1s", gui_src)

    def test_build_scripts_verify_exe_and_cleanup_temp_bin_files(self):
        root_dir = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root_dir, "build_exe.py"), "r", encoding="utf-8") as f:
            build_py = f.read()
        with open(os.path.join(root_dir, "build.bat"), "r", encoding="utf-8") as f:
            build_bat = f.read()
        with open(os.path.join(root_dir, "build.ps1"), "r", encoding="utf-8") as f:
            build_ps1 = f.read()

        # Verify exe existence/size checks before deleting setup/build/temp/.bin files
        self.assertIn("getsize(single_exe_path) <= 0", build_py)
        self.assertIn('".bin"', build_py)
        self.assertIn('BUILD_ERR=%errorlevel%', build_bat)
        self.assertIn('not exist "AtomicDB.exe"', build_bat)
        self.assertIn('*.bin', build_bat)
        self.assertIn('*.bin', build_ps1)
        # Ensure runtime directories are NOT listed for deletion
        for required_runtime in ('"logs"', '"config"', '"syzygy-345"'):
            self.assertNotIn(required_runtime, build_py.split("unnecessary_dirs")[1].split("]")[0])

    def test_compact_node_formatting(self):
        self.assertEqual(format_nodes_compact(128_000_000), "128m")
        self.assertEqual(format_nodes_compact(512_000_000), "512m")
        self.assertEqual(format_nodes_compact(2_000_000_000), "2b")
        self.assertEqual(format_nodes_compact(1_500_000_000), "1.5b")
        self.assertEqual(format_nodes_compact(500_000), "500k")
        self.assertEqual(format_nodes_compact(750), "750")

    def test_last_3_avg_with_only_1_or_2_tasks(self):
        # Prior history should NOT override once tasks complete in the new session
        self.logger.tasks_history = [{"task_id": "old", "nps": 10_000_000, "nodes": 10_000_000}]
        self.logger.nps_task_history = []

        # Complete 1 task -> average must equal exactly task 1 NPS (divided by 1)
        self.logger.parse_worker_line("[0] task 10 (1000000n, 1.00s) -> cp 5")
        self.assertAlmostEqual(self.logger.get_last_3_avg_nps(), 1_000_000.0, delta=10.0)

        # Complete 2nd task -> average must equal (1M + 3M) / 2 = 2M (divided by 2)
        self.logger.parse_worker_line("[0] task 11 (3000000n, 1.00s) -> cp 8")
        self.assertAlmostEqual(self.logger.get_last_3_avg_nps(), 2_000_000.0, delta=10.0)

        # Complete 3rd task -> average must equal (1M + 3M + 5M) / 3 = 3M
        self.logger.parse_worker_line("[0] task 12 (5000000n, 1.00s) -> cp 12")
        self.assertAlmostEqual(self.logger.get_last_3_avg_nps(), 3_000_000.0, delta=10.0)

        # Complete 4th task -> average uses last 3: (3M + 5M + 7M) / 3 = 5M
        self.logger.parse_worker_line("[0] task 13 (7000000n, 1.00s) -> cp 15")
        self.assertAlmostEqual(self.logger.get_last_3_avg_nps(), 5_000_000.0, delta=10.0)

    def test_device_name_logged_after_each_task(self):
        self.logger.parse_worker_line("[0] task 42 (128000000n, 32.00s) -> cp 20")
        device = self.logger.device_name
        self.assertTrue(bool(device))

        # Verify in memory summary & persisted task history
        summary = self.logger.get_summary()
        self.assertEqual(summary["device_name"], device)
        self.assertEqual(summary["recent_tasks"][0]["device"], device)

        # Verify activity.log, session_statistics.log, and lifetime_statistics.txt contain device name
        for fname in ("activity.log", "session_statistics.log", "lifetime_statistics.txt"):
            fpath = os.path.join(self.test_dir, "logs", fname)
            with open(fpath, "r", encoding="utf-8") as f:
                self.assertIn(device, f.read(), f"{fname} missing device name")

    def test_graph_timeframe_filtering_and_slider_config(self):
        import time as _t
        now = _t.time()
        series = [
            {"time": now - 550, "timestamp": "t1", "system_cpu": 10},  # within 10m
            {"time": now - 250, "timestamp": "t2", "system_cpu": 20},  # within 5m & 10m
            {"time": now - 45, "timestamp": "t3", "system_cpu": 30},   # within 1.5m, 5m & 10m
        ]
        self.assertEqual(len(AnalyticsLogger.filter_history_by_timeframe(series, 90, now)), 1)
        self.assertEqual(len(AnalyticsLogger.filter_history_by_timeframe(series, 300, now)), 2)
        self.assertEqual(len(AnalyticsLogger.filter_history_by_timeframe(series, 600, now)), 3)

        # Verify GUI slider dials, Fusion style, and explicit Start Worker button styling
        root_dir = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root_dir, "src", "gui.py"), "r", encoding="utf-8") as f:
            gui_src = f.read()
        with open(os.path.join(root_dir, "src", "main.py"), "r", encoding="utf-8") as f:
            main_src = f.read()

        self.assertIn('app.setStyle("Fusion")', main_src)
        self.assertIn("QSlider", gui_src)
        self.assertIn('"1.5 mins", 90', gui_src)
        self.assertIn('"5 mins", 300', gui_src)
        self.assertIn('"10 mins", 600', gui_src)
        self.assertIn("self.btn_start.setMinimumHeight(40)", gui_src)
        self.assertIn("self.btn_start.setStyleSheet", gui_src)


if __name__ == "__main__":
    unittest.main()

