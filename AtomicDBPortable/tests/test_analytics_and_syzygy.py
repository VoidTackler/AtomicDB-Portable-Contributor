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
        self.logger.enable_explore_lookup = False

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

        # Update PV line during search (converted to algebraic notation; no fake opening for non-book FEN)
        self.logger.parse_worker_line("task pv: e6d5 e1e8 g8g7 a5c3")
        summary = self.logger.get_summary()
        self.assertEqual(summary["current_task_line"], "1... Bxd5 2. Re8+ Kg7 3. Qc3+")

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

        # Verify explicit high-contrast styling & 30px height for Start / Stop After Finishing Current Task / Save and Stop buttons
        self.assertIn('_action_btn_qss("btnStart"', gui_src)
        self.assertIn('_action_btn_qss("btnStop"', gui_src)
        self.assertIn('_action_btn_qss("btnLocalStop"', gui_src)
        self.assertIn(":disabled", gui_src)
        self.assertIn('QPushButton("Start")', gui_src)
        self.assertIn('QPushButton("Stop After Finishing Current Task")', gui_src)
        self.assertIn('QPushButton("Save and Stop")', gui_src)
        # Ensure checkbox indicator is green when checked and gray when unchecked
        self.assertIn("QCheckBox::indicator", gui_src)
        self.assertIn("background-color: #4b5563", gui_src)
        self.assertIn("QCheckBox::indicator:checked { background-color: #16a34a;", gui_src)
        # Ensure unscoped controlsContainer stylesheet does not override buttons
        self.assertIn("self.setStyleSheet", gui_src)
        # Ensure unified 1000ms PreciseTimer for ETA, CPU, and RAM (no 0.8s polling)
        self.assertNotIn("start(800)", gui_src)
        self.assertNotIn("0.8s", gui_src)
        self.assertIn("self.timer.setTimerType(Qt.PreciseTimer)", gui_src)
        self.assertIn("self.timer.start(1000)", gui_src)
        self.assertIn("_refresh_eta_1s", gui_src)
        # Ensure responsive wrapping, larger aligned analytics subtitles, removed worker CPU bar, and rounded top System CPU bar
        self.assertIn("class _FlowLayout", gui_src)
        self.assertIn("Qt.ScrollBarAlwaysOff", gui_src)
        self.assertIn("font-size: 12px; font-weight: 500;", gui_src)
        self.assertIn("layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)", gui_src)
        self.assertIn('("Nodes Per Hour", self.lbl_session_nph, "Session NPH")', gui_src)
        self.assertIn('("Lifetime NPH", self.lbl_lt_nph, "Lifetime Nodes/Hr")', gui_src)
        self.assertNotIn("bar_worker_cpu", gui_src)
        self.assertIn("border-radius: 11px;", gui_src)
        self.assertIn("border-radius: 10px;", gui_src)
        self.assertLess(
            gui_src.index("tab_analytics_layout.addLayout(cpu_top_row)"),
            gui_src.index('grp_cur = QGroupBox("CURRENT TASK'),
        )

    def test_build_scripts_verify_exe_and_cleanup_temp_bin_files(self):
        root_dir = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root_dir, "build_exe.py"), "r", encoding="utf-8") as f:
            build_py = f.read()
        with open(os.path.join(root_dir, "build.bat"), "r", encoding="utf-8") as f:
            build_bat = f.read()
        with open(os.path.join(root_dir, "build.ps1"), "r", encoding="utf-8") as f:
            build_ps1 = f.read()

        # Verify exe existence/size checks and single-copy move (no duplicate copy in READY_TO_RUN_EXE)
        self.assertIn("getsize(single_exe_path) <= 0", build_py)
        self.assertIn("shutil.move(single_exe_path, root_exe_path)", build_py)
        self.assertNotIn("shutil.copy2(single_exe_path, ready_exe_path)", build_py)
        self.assertNotIn("Copy-Item $singleExe \"READY_TO_RUN_EXE/$exeName\"", build_ps1)
        self.assertIn("Move-Item $singleExe $exeName", build_ps1)
        self.assertIn('".bin"', build_py)
        self.assertIn('BUILD_ERR=%errorlevel%', build_bat)
        self.assertIn('not exist "Background Processing Utility.exe"', build_bat)
        self.assertIn('*.bin', build_bat)
        self.assertIn('*.bin', build_ps1)
        self.assertIn('account.txt', build_py)
        # Ensure runtime directories are NOT listed for deletion
        for required_runtime in ('"logs"', '"config"', '"syzygy-345"'):
            self.assertNotIn(required_runtime, build_py.split("unnecessary_dirs")[1].split("]")[0])

        # Verify spec excludes unused Qt/crypto bloat and builds fast
        with open(os.path.join(root_dir, "AtomicDBPortable.spec"), "r", encoding="utf-8") as f:
            spec_src = f.read()
        hidden_section = spec_src.split("hiddenimports=[")[1].split("]")[0]
        self.assertNotIn("'cryptography'", hidden_section)
        self.assertIn("'cryptography'", spec_src.split("_UNUSED_MODULES = [")[1].split("]")[0])
        self.assertIn("optimize=1", spec_src)
        self.assertIn("upx=False", spec_src)

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
            {"time": now - 3500, "timestamp": "t0", "system_cpu": 10},  # within 1h only
            {"time": now - 850, "timestamp": "t1", "system_cpu": 20},   # within 15m & 1h
            {"time": now - 250, "timestamp": "t2", "system_cpu": 30},   # within 5m, 15m & 1h
            {"time": now - 45, "timestamp": "t3", "system_cpu": 40},    # within 1m, 5m, 15m & 1h
        ]
        self.assertEqual(len(AnalyticsLogger.filter_history_by_timeframe(series, 60, now)), 1)
        self.assertEqual(len(AnalyticsLogger.filter_history_by_timeframe(series, 300, now)), 2)
        self.assertEqual(len(AnalyticsLogger.filter_history_by_timeframe(series, 900, now)), 3)
        self.assertEqual(len(AnalyticsLogger.filter_history_by_timeframe(series, 3600, now)), 4)

        # Verify 3 individual data points round/average into 1 for the 1h view, while shorter windows keep 1:1
        pts_1h = [
            {"time": now - 10, "timestamp": "00:01", "nps": 100, "avg_nps": 100},
            {"time": now - 9, "timestamp": "00:02", "nps": 200, "avg_nps": 150},
            {"time": now - 8, "timestamp": "00:03", "nps": 300, "avg_nps": 200},
            {"time": now - 7, "timestamp": "00:04", "nps": 400, "avg_nps": 250},
            {"time": now - 6, "timestamp": "00:05", "nps": 500, "avg_nps": 300},
            {"time": now - 5, "timestamp": "00:06", "nps": 600, "avg_nps": 350},
        ]
        self.assertEqual(len(AnalyticsLogger.aggregate_series_for_timeframe(pts_1h, 900, now)), 6)
        agg_1h = AnalyticsLogger.aggregate_series_for_timeframe(pts_1h, 3600, now)
        self.assertEqual(len(agg_1h), 2)
        self.assertEqual(agg_1h[0]["nps"], 200)
        self.assertEqual(agg_1h[0]["avg_nps"], 150)
        self.assertEqual(agg_1h[1]["nps"], 500)
        self.assertEqual(agg_1h[1]["avg_nps"], 300)

        # Verify GUI slider dials, timeframe options, LiveNPSChartWidget, Fusion style, and explicit button styling
        root_dir = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root_dir, "src", "gui.py"), "r", encoding="utf-8") as f:
            gui_src = f.read()
        with open(os.path.join(root_dir, "src", "main.py"), "r", encoding="utf-8") as f:
            main_src = f.read()

        self.assertIn('app.setStyle("Fusion")', main_src)
        self.assertIn("QSlider", gui_src)
        self.assertIn('[("1 min", 60), ("5 mins", 300), ("15 mins", 900), ("1 h", 3600)]', gui_src)
        self.assertIn("LiveNPSChartWidget", gui_src)
        self.assertNotIn("RAMChartWidget", gui_src)
        self.assertIn("self.btn_start.setFixedHeight(30)", gui_src)
        self.assertIn("self.btn_stop.setFixedHeight(30)", gui_src)
        self.assertIn("self.btn_local_stop.setFixedHeight(30)", gui_src)
        self.assertIn("self.btn_start.setStyleSheet", gui_src)

    def test_account_txt_credentials_defaults_and_overrides(self):
        from AtomicDBPortable.src.configuration import PortableConfig

        old_root = os.environ.get("ATOMICDB_PORTABLE_ROOT")
        os.environ["ATOMICDB_PORTABLE_ROOT"] = self.test_dir
        try:
            cfg = PortableConfig()
            acc_path = os.path.join(self.test_dir, "account.txt")
            self.assertTrue(os.path.exists(acc_path))

            # Blank variables default to PortableExe / ExePassword
            self.assertEqual(cfg.get_account_credentials(), ("PortableExe", "ExePassword"))

            # Override both USERNAME and PASSWORD
            with open(acc_path, "w", encoding="utf-8") as f:
                f.write("# Custom account\nUSERNAME=CustomUser\nPASSWORD=CustomPass123\n")
            self.assertEqual(cfg.get_account_credentials(), ("CustomUser", "CustomPass123"))

            # Partial override: custom username with blank password
            with open(acc_path, "w", encoding="utf-8") as f:
                f.write('USERNAME="QuotedUser"\nPASSWORD=\n')
            self.assertEqual(cfg.get_account_credentials(), ("QuotedUser", "ExePassword"))

            # Partial override: blank username with custom password
            with open(acc_path, "w", encoding="utf-8") as f:
                f.write("USERNAME=\nPASSWORD=OnlyPass\n")
            self.assertEqual(cfg.get_account_credentials(), ("PortableExe", "OnlyPass"))
        finally:
            if old_root is None:
                os.environ.pop("ATOMICDB_PORTABLE_ROOT", None)
            else:
                os.environ["ATOMICDB_PORTABLE_ROOT"] = old_root

    def test_application_name_and_default_win32_icon_config(self):
        root_dir = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root_dir, "src", "gui.py"), "r", encoding="utf-8") as f:
            gui_src = f.read()
        with open(os.path.join(root_dir, "src", "main.py"), "r", encoding="utf-8") as f:
            main_src = f.read()
        with open(os.path.join(root_dir, "AtomicDBPortable.spec"), "r", encoding="utf-8") as f:
            spec_src = f.read()

        self.assertIn('APP_NAME = "Background Processing Utility"', gui_src)
        self.assertIn("IDI_APPLICATION = 32512", gui_src)
        self.assertIn("make_int_resource(IDI_APPLICATION)", gui_src)
        self.assertIn("LoadIconW", gui_src)
        self.assertIn("self.config.get_account_credentials()", gui_src)

        self.assertIn("app.setApplicationName(APP_NAME)", main_src)
        self.assertIn("app.setApplicationDisplayName(APP_NAME)", main_src)
        self.assertIn("app.setWindowIcon(default_icon)", main_src)
        self.assertIn("config.get_account_credentials()", main_src)

        self.assertIn("name='Background Processing Utility'", spec_src)
        self.assertIn("icon='NONE'", spec_src)

    def test_eta_pauses_when_paused_and_resets_when_reset_or_stopped(self):
        from unittest.mock import patch

        fake_now = [1000.0]
        with patch("AtomicDBPortable.src.analytics_logger.time.time", side_effect=lambda: fake_now[0]):
            # Establish baseline 2,000,000 NPS
            self.logger.parse_worker_line("[0] task 1 (2000000n, 1.00s) -> cp 10")
            self.logger.parse_worker_line("[0] starting task 9001 (10000000n) calculating: e2e4")

            self.assertEqual(self.logger.current_task_initial_eta_seconds, 5)
            fake_now[0] += 2.0  # 2s elapsed -> ETA = 3s
            self.assertEqual(self.logger.calculate_estimated_time_remaining(), 3)

            # Pause worker at t=1002 -> advance wall clock by 10s -> ETA stays frozen at 3s
            self.logger.pause_current_task()
            self.assertTrue(self.logger.is_worker_paused)
            fake_now[0] += 10.0
            self.assertEqual(self.logger.calculate_estimated_time_remaining(), 3)

            # Resume worker at t=1012 -> still 3s immediately, then ticks down 1s/s to 2s, 1s, 0s, -1s
            self.logger.resume_current_task()
            self.assertFalse(self.logger.is_worker_paused)
            self.assertEqual(self.logger.calculate_estimated_time_remaining(), 3)
            fake_now[0] += 1.0
            self.assertEqual(self.logger.calculate_estimated_time_remaining(), 2)
            fake_now[0] += 3.0
            self.assertEqual(self.logger.calculate_estimated_time_remaining(), -1)

            # Reset when worker stops / interrupted / reset_current_task called
            self.logger.parse_worker_line("[0] task 9001 interrupted by the stop")
            summary = self.logger.get_summary()
            self.assertIsNone(summary["current_task_id"])
            self.assertIsNone(summary["current_task_eta_seconds"])
            self.assertEqual(summary["current_task_eta_str"], "-")

    def test_stop_after_finishing_current_task_sentinel_and_worker_hooks(self):
        from AtomicDBPortable.worker.atomicdb_worker import _is_stop_after_task_requested

        flag_file = os.path.join(self.test_dir, "stop_after_task.flag")
        old_env = os.environ.get("ATOMICDB_STOP_AFTER_TASK_FILE")
        os.environ["ATOMICDB_STOP_AFTER_TASK_FILE"] = flag_file
        try:
            self.assertFalse(_is_stop_after_task_requested())
            with open(flag_file, "w", encoding="utf-8") as f:
                f.write("stop_after_current_task\n")
            self.assertTrue(_is_stop_after_task_requested())
        finally:
            if old_env is None:
                os.environ.pop("ATOMICDB_STOP_AFTER_TASK_FILE", None)
            else:
                os.environ["ATOMICDB_STOP_AFTER_TASK_FILE"] = old_env

        # Verify WorkerManager has request_stop_after_current_task and resets ETA on stop
        self.logger.parse_worker_line("[0] task 1 (2000000n, 1.00s) -> cp 10")
        self.logger.parse_worker_line("[0] starting task 9002 (6000000n) calculating: e2e4")
        wm = WorkerManager("python", "worker/atomicdb_worker.py", analytics_logger=self.logger)
        self.assertFalse(wm.request_stop_after_current_task())
        wm.stop_worker()
        self.assertIsNone(self.logger.current_task_id)
        self.assertIsNone(self.logger.calculate_estimated_time_remaining())

    def test_no_readable_default_credentials_exposed(self):
        from AtomicDBPortable.src.configuration import PortableConfig

        root_dir = os.path.dirname(os.path.dirname(__file__))
        tmp_cfg = PortableConfig()
        expected_u, expected_p = tmp_cfg.get_account_credentials()

        # Verify generated/distributed account.txt stays strictly blank without readable secrets
        old_root = os.environ.get("ATOMICDB_PORTABLE_ROOT")
        os.environ["ATOMICDB_PORTABLE_ROOT"] = self.test_dir
        try:
            isolated = PortableConfig()
            with open(os.path.join(self.test_dir, "account.txt"), "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content, "USERNAME=\nPASSWORD=\n")
            self.assertNotIn(expected_u, content)
            self.assertNotIn(expected_p, content)
        finally:
            if old_root is None:
                os.environ.pop("ATOMICDB_PORTABLE_ROOT", None)
            else:
                os.environ["ATOMICDB_PORTABLE_ROOT"] = old_root

        # Check all shipping source, config, txt, and doc files have no readable credential strings
        paths_to_check = [
            os.path.join(root_dir, "account.txt"),
            os.path.join(root_dir, "READY_TO_RUN_EXE", "account.txt"),
            os.path.join(root_dir, "READY_TO_RUN_EXE", "README_USB.txt"),
            os.path.join(root_dir, "README.md"),
            os.path.join(root_dir, "config", "settings.json"),
            os.path.join(root_dir, "READY_TO_RUN_EXE", "config", "settings.json"),
            os.path.join(root_dir, "src", "configuration.py"),
            os.path.join(root_dir, "src", "worker_manager.py"),
            os.path.join(root_dir, "src", "main.py"),
            os.path.join(root_dir, "worker", "atomicdb_worker.py"),
        ]
        for p in paths_to_check:
            with open(p, "r", encoding="utf-8") as f:
                text = f.read()
            self.assertNotIn(expected_u, text, f"Readable username found in {p}")
            self.assertNotIn(expected_p, text, f"Readable password found in {p}")

        # Verify worker_manager logs redact both -U and -P
        with open(os.path.join(root_dir, "src", "worker_manager.py"), "r", encoding="utf-8") as f:
            wm_src = f.read()
        self.assertIn('("-U", "-P")', wm_src)

    def test_account_credentials_affect_worker_attribution_payload(self):
        import importlib.util
        import types
        from unittest.mock import patch
        from AtomicDBPortable.src.configuration import PortableConfig
        from AtomicDBPortable.src.worker_manager import WorkerManager

        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as cwd_dir:
            acct_path = os.path.join(tmp_dir, "account.txt")
            # UTF-16 LE BOM (e.g., PowerShell Out-File / Notepad) must still parse cleanly
            with open(acct_path, "wb") as fb:
                fb.write("USERNAME=CustomAttrUser\nPASSWORD=CustomAttrPass\n".encode("utf-16"))

            with patch.dict(os.environ, {"ATOMICDB_PORTABLE_ROOT": tmp_dir}):
                cfg = PortableConfig()
                u, p = cfg.get_account_credentials()
                self.assertEqual((u, p), ("CustomAttrUser", "CustomAttrPass"))

                # Verify WorkerManager puts exact credentials on CLI for both script and frozen exe modes
                wm = WorkerManager("/tmp/Background Processing Utility.exe", "AtomicDBPortable/worker/atomicdb_worker.py")
                cmd = wm.build_command_args(username=u, password=p)
                self.assertEqual(cmd[1], "--exec-worker")
                self.assertEqual(cmd[cmd.index("-U") + 1], "CustomAttrUser")
                self.assertEqual(cmd[cmd.index("-P") + 1], "CustomAttrPass")

            # Verify fallback to cwd/account.txt when base_dir/account.txt is blank
            with open(acct_path, "w", encoding="utf-8") as f:
                f.write("USERNAME=\nPASSWORD=\n")
            with open(os.path.join(cwd_dir, "account.txt"), "w", encoding="utf-8") as f:
                f.write("USERNAME=CwdUser\nPASSWORD=CwdPass\n")
            old_cwd = os.getcwd()
            try:
                os.chdir(cwd_dir)
                with patch.dict(os.environ, {"ATOMICDB_PORTABLE_ROOT": tmp_dir}):
                    cfg2 = PortableConfig()
                    self.assertEqual(cfg2.get_account_credentials(), ("CwdUser", "CwdPass"))
            finally:
                os.chdir(old_cwd)

            # Verify atomicdb_worker sends the custom username, password, and machine prefix in /api/lease & /api/submit
            captured_posts = []
            fake_requests = types.ModuleType("requests")
            fake_requests.RequestException = Exception

            class _StopLoop(BaseException):
                pass

            class _FakeSession:
                def mount(self, *a, **kw):
                    pass

                def post(self, url, data=None, **kw):
                    captured_posts.append((url, dict(data or {})))
                    raise _StopLoop()

            fake_requests.Session = _FakeSession
            fake_adapters = types.ModuleType("requests.adapters")
            fake_adapters.HTTPAdapter = lambda **kw: object()
            fake_urllib3 = types.ModuleType("urllib3")
            fake_urllib3_util = types.ModuleType("urllib3.util")
            fake_urllib3_retry = types.ModuleType("urllib3.util.retry")
            fake_urllib3_retry.Retry = lambda **kw: object()

            worker_path = os.path.abspath(
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "worker", "atomicdb_worker.py")
            )
            with patch.dict(sys.modules, {
                "requests": fake_requests,
                "requests.adapters": fake_adapters,
                "urllib3": fake_urllib3,
                "urllib3.util": fake_urllib3_util,
                "urllib3.util.retry": fake_urllib3_retry,
            }):
                spec = importlib.util.spec_from_file_location("test_atomicdb_worker_attr", worker_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.Engine = lambda *a, **kw: type("FakeEng", (), {"close": lambda self: None})()
                mod._file_sha256 = lambda path: "deadbeef"
                mod._net_sha256 = lambda path: ""
                with patch.object(sys, "argv", [
                    worker_path, "-U", "CustomAttrUser", "-P", "CustomAttrPass",
                    "--engine", sys.executable, "--no-fetch-syzygy", "--no-auto-update", "--once"
                ]):
                    with self.assertRaises(_StopLoop):
                        mod.main()

            self.assertEqual(len(captured_posts), 1)
            post_url, post_data = captured_posts[0]
            self.assertTrue(post_url.endswith("/atomicdb/api/lease"))
            self.assertEqual(post_data["username"], "CustomAttrUser")
            self.assertEqual(post_data["password"], "CustomAttrPass")
            self.assertTrue(post_data["machine"].startswith("CustomAttrUser-"))

    def test_nph_lifetime_nph_algebraic_line_and_three_tabs(self):
        from AtomicDBPortable.src.analytics_logger import format_nph
        from AtomicDBPortable.src.chess_notation import STANDARD_START_FEN

        # 1. Verify idle state shows no fake example line names
        self.assertEqual(self.logger.get_summary()["current_task_line"], "Idle (waiting for next task)")

        # 2. Verify algebraic notation + authentic opening name (Center Attack)
        self.logger.parse_worker_line(f"[0] starting task 8001 (128000000n) calculating: {STANDARD_START_FEN}")
        self.logger.parse_worker_line(
            "task pv: g1f3 f7f6 e2e4 d7d5 b1c3 e7e6 d2d4 f8b4 f1d3 g8e7 e1g1 b8c6 c1d2 e8g8 a2a3 b4c3 d2c3 d5e4"
        )
        line_8 = self.logger.get_summary()["current_task_line"]
        # Must output first 8 full moves (16 plies), not stop at 5 moves or include move 9
        self.assertEqual(
            line_8,
            "Center Attack: 1. Nf3 f6 2. e4 d5 3. Nc3 e6 4. d4 Bb4 5. Bd3 Ne7 6. O-O Nbc6 7. Bd2 O-O 8. a3 Bxc3",
        )
        self.assertNotIn("9.", line_8)

        # Verify mid-opening FEN (even with fullmove=1 '0 1') recovers moves 1..N instead of mislabeling continuation as 1..5
        self.logger.parse_worker_line(
            "[0] starting task 8002 (128000000n) calculating: rnbqkbnr/ppp1p1pp/5p2/3p4/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 1"
        )
        self.logger.parse_worker_line(
            "task pv: b1c3 e7e6 d2d4 f8b4 f1d3 g8e7 e1g1 b8c6 c1d2 e8g8 a2a3 b4c3 d2c3 d5e4"
        )
        self.assertEqual(
            self.logger.get_summary()["current_task_line"],
            "Center Attack: 1. Nf3 f6 2. e4 d5 3. Nc3 e6 4. d4 Bb4 5. Bd3 Ne7 6. O-O Nbc6 7. Bd2 O-O 8. a3 Bxc3",
        )

        # Verify explicit line_moves from task payload prints the exact chronological line from move 1
        self.logger.parse_worker_line(
            "[0] starting task 8003 (128000000n) calculating: rnbqkbnr/ppp1p1pp/5p2/3p4/4P3/2N2N2/PPPP1PPP/R1BQKB1R b KQkq - 0 1 | line_moves: g1f3 f7f6 e2e4 d7d5 b1c3"
        )
        self.logger.parse_worker_line(
            "task pv: e7e6 d2d4 f8b4 f1d3 g8e7 e1g1 b8c6 c1d2 e8g8 a2a3 b4c3 d2c3 d5e4"
        )
        self.assertEqual(
            self.logger.get_summary()["current_task_line"],
            "Center Attack: 1. Nf3 f6 2. e4 d5 3. Nc3",
        )

        # Verify atomicdb_worker emits pv[:20] (>= 8 full moves) rather than pv[:10] (5 moves)
        worker_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "worker", "atomicdb_worker.py")
        with open(worker_path, "r", encoding="utf-8") as f:
            worker_src = f.read()
        self.assertIn("pv[:20]", worker_src)
        self.assertNotIn("pv[:10]", worker_src)

        # 3. Verify Session NPH and Lifetime NPH calculation + formatting + lifetime_statistics.txt
        self.logger.parse_worker_line("[0] task 8003 (4000000n, 2.00s) -> cp 15")
        summary = self.logger.get_summary()
        # 4,000,000 nodes / 2.00s runtime = 2,000,000 NPS = 7,200,000,000 NPH (7.2b /hr)
        self.assertEqual(summary["lifetime_nph"], 7_200_000_000)
        self.assertEqual(format_nph(summary["lifetime_nph"]), "7.2b /hr")
        self.assertGreater(summary["session_nph"], 0)

        txt_file = os.path.join(self.test_dir, "logs", "lifetime_statistics.txt")
        with open(txt_file, "r", encoding="utf-8") as f:
            lt_txt = f.read()
        self.assertIn("Lifetime Nodes/Hour:", lt_txt)
        self.assertIn("7.2b /hr", lt_txt)

        # 4. Verify GUI has 3 full-screen tabs in exact order:
        #    API Parameters -> Live Analysis Console -> Graph and Analytics
        gui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "gui.py")
        with open(gui_path, "r", encoding="utf-8") as f:
            gui_src = f.read()
        self.assertNotIn("self.main_splitter", gui_src)
        idx_api = gui_src.index('self.tab_widget.addTab(tab_api_scroll, "API Parameters")')
        idx_console = gui_src.index('self.tab_widget.addTab(tab_console, "Live Analysis Console")')
        idx_graph = gui_src.index('self.tab_widget.addTab(tab_analytics_scroll, "Graph and Analytics")')
        self.assertLess(idx_api, idx_console)
        self.assertLess(idx_console, idx_graph)
        self.assertIn("self.lbl_session_nph", gui_src)
        self.assertIn("self.lbl_lt_nph", gui_src)

    def test_atomicdb_explore_chronological_line_and_hyperlink_button(self):
        from unittest.mock import patch
        from AtomicDBPortable.src.chess_notation import (
            build_atomicdb_explore_url,
            compute_atomicdb_position_key,
            parse_atomicdb_explore_html,
        )

        # Exact position and move path from AtomicDB example
        fen = "rnbqk2r/1pp3pp/p3pp1n/4N3/1b1P4/2N3P1/PPP2P1P/R1BQKB1R b KQkq - 0 1"
        expected_key = "5ab87694bf1e413b5985016a3b157c51069958dac94b31ff306d1d2c6a562e3f"
        self.assertEqual(compute_atomicdb_position_key(fen), expected_key)

        play_csv = "g1f3,f7f6,e2e4,d7d5,b1c3,a7a6,d2d4,e7e6,e4d5,g8h6,f3e5,f8b4,g2g3"
        expected_url = (
            f"https://belzedar.duckdns.org/atomicdb/explore/{expected_key}/"
            "?play=g1f3%2Cf7f6%2Ce2e4%2Cd7d5%2Cb1c3%2Ca7a6%2Cd2d4%2Ce7e6%2Ce4d5%2Cg8h6%2Cf3e5%2Cf8b4%2Cg2g3"
        )
        self.assertEqual(build_atomicdb_explore_url(fen, play_csv), expected_url)

        sample_html = (
            '<div class="opening-line"><h2 id="opening-name"><a href="/atomicdb/explore/123/">'
            'Center Attack</a></h2></div>'
            f'<input name="play" type="hidden" value="{play_csv}"/>'
        )
        parsed = parse_atomicdb_explore_html(sample_html)
        self.assertEqual(parsed["opening_name"], "Center Attack")
        self.assertEqual(parsed["play_uci"], play_csv)

        # Simulate AnalyticsLogger resolving explore info (synchronously via patch)
        self.logger.enable_explore_lookup = True
        mock_info = {
            "key": expected_key,
            "opening_name": "Center Attack",
            "play_uci": play_csv,
            "url": expected_url,
        }
        with patch("AtomicDBPortable.src.analytics_logger.fetch_atomicdb_explore_info", return_value=mock_info):
            self.logger.record_task_start("8500", 128000000, fen)
            # Wait briefly for daemon lookup thread to apply explore info
            import time as _t
            deadline = _t.time() + 2.0
            while _t.time() < deadline and self.logger.get_summary()["current_task_url"] != expected_url:
                _t.sleep(0.02)

        # Speculative PV after the leaf must NOT overwrite the chronological line from move 1
        self.logger.parse_worker_line("task pv: h6g4 e5g4 f6f5 g4e5")
        summary = self.logger.get_summary()
        self.assertEqual(
            summary["current_task_line"],
            "Center Attack: 1. Nf3 f6 2. e4 d5 3. Nc3 a6 4. d4 e6 5. exd5 Nh6 6. Ne5 Bb4 7. g3",
        )
        self.assertEqual(summary["current_task_url"], expected_url)

        # Verify GUI contains the clickable Open Line Link button wired to current_task_url
        gui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "gui.py")
        with open(gui_path, "r", encoding="utf-8") as f:
            gui_src = f.read()
        self.assertIn("self.btn_open_line_url", gui_src)
        self.assertIn("_open_current_line_url", gui_src)
        self.assertIn("QDesktopServices.openUrl(QUrl(self._current_line_url))", gui_src)
        self.assertIn('summary.get("current_task_url")', gui_src)

    def test_deep_line_and_elided_queue_line_organization_and_429_fallback(self):
        import urllib.error
        from unittest.mock import patch
        import AtomicDBPortable.src.chess_notation as cn

        deep_key = "9f243aae2a51" + "0" * 52
        elided_key = "322bba45f84a" + "a" * 52
        full_18_move_san = (
            "1. Nh3 f6 2. d4 c6 3. e4 d5 4. Nc3 e6 5. Bd3 Bb4 6. O-O Ne7 "
            "7. Bd2 O-O 8. Qe1 b6 9. a3 Ba5 10. b4 Bb7 11. Ne2 Nd7 12. Ng3 Qc7 "
            "13. Qe2 Rac8 14. Qg4 Rfe8 15. Rae1 Nf8 16. Re3 Kf7 17. Rfe1 Kg8 18. Rg3"
        )

        # Sample queue HTML matching AtomicDB's deep line & elided 18-move line
        queue_html = f"""
        <ul>
          <li>
            <a class="qline" href="/atomicdb/explore/{deep_key}/" title="deep line, ply ≥69 · … Kg6 c8=B Bxd3 h4">deep line, ply ≥69 · … Kg6 c8=B Bxd3 h4</a>
            <span title="Last named Atomic opening on this line">bijiy spam</span>
          </li>
          <li>
            <a class="qline" href="/atomicdb/explore/{elided_key}/" title="{full_18_move_san}">1. Nh3 f6 2. d4 c6 … 16. Re3 Kf7 17. Rfe1 Kg8 18. Rg3</a>
            <span title="Last named Atomic opening on this line">TrojanKnight, Old Defence, 2.d4</span>
          </li>
        </ul>
        """
        parsed_q = cn.parse_atomicdb_queue_html(queue_html)
        self.assertEqual(parsed_q[deep_key]["opening_name"], "bijiy spam")
        self.assertEqual(parsed_q[deep_key]["play_uci"], "")
        self.assertEqual(parsed_q[deep_key]["line_text"], "deep line, ply ≥69 · … Kg6 c8=B Bxd3 h4")

        self.assertEqual(parsed_q[elided_key]["opening_name"], "TrojanKnight, Old Defence, 2.d4")
        self.assertTrue(parsed_q[elided_key]["play_uci"].startswith("g1h3,f7f6,d2d4,c7c6"))

        self.assertEqual(
            cn.format_deep_or_elided_line("deep line, ply ≥69 · … Kg6 c8=B Bxd3 h4", "bijiy spam"),
            "bijiy spam (deep line, ply ≥69): … Kg6 c8=B Bxd3 h4",
        )

        # Verify HTTP 429 from /explore/ falls back cleanly to queue HTML index and locks deep line against PV overwrite
        cn._EXPLORE_CACHE.clear()
        cn._EXPLORE_429_UNTIL = 0.0
        cn._QUEUE_CACHE["ts"] = 0.0
        cn._QUEUE_CACHE["entries"] = {}

        class _FakeResp:
            def __init__(self, payload: str):
                self._payload = payload.encode("utf-8")

            def read(self):
                return self._payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(req, timeout=3.0):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "/atomicdb/explore/" in url:
                raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
            if url.endswith("/atomicdb/"):
                return _FakeResp(queue_html)
            raise AssertionError(f"Unexpected URL: {url}")

        fen = "rnbqk2r/1pp3pp/p3pp1n/4N3/1b1P4/2N3P1/PPP2P1P/R1BQKB1R b KQkq - 0 1"
        with patch("AtomicDBPortable.src.chess_notation.compute_atomicdb_position_key", return_value=deep_key):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                info = cn.fetch_atomicdb_explore_info(fen)
                self.assertIsNotNone(info)
                self.assertEqual(info["opening_name"], "bijiy spam")
                self.assertEqual(info["line_text"], "deep line, ply ≥69 · … Kg6 c8=B Bxd3 h4")

        self.logger.record_task_start("9001", 64000000, fen)
        self.logger._apply_explore_info("9001", fen, info)
        # Speculative PV arriving after deep-line resolution must NOT overwrite with "1... ..."
        self.logger.parse_worker_line("task pv: g6f5 c8d7")
        self.assertEqual(
            self.logger.get_summary()["current_task_line"],
            "bijiy spam (deep line, ply ≥69): … Kg6 c8=B Bxd3 h4",
        )

    def test_thread_dependent_eta_and_dark_combo_and_live_nps_history(self):
        # 1. Establish 2 tasks completed at 2 threads -> 1,000,000 NPS each (500k NPS per thread)
        self.logger.set_active_threads(2)
        self.logger.parse_worker_line("[0] task 1 (2000000n, 2.00s) -> cp 10")
        self.logger.parse_worker_line("[0] task 2 (2000000n, 2.00s) -> cp 15")
        self.assertAlmostEqual(self.logger.get_last_3_avg_nps(), 1_000_000.0, delta=10.0)

        # Doubling threads to 4 before starting a 4,000,000-node task should double expected NPS -> ETA = 2s (instead of 4s)
        self.logger.set_active_threads(4)
        self.assertAlmostEqual(self.logger.get_last_3_avg_nps(), 2_000_000.0, delta=10.0)
        self.logger.parse_worker_line("[0] starting task 9101 (4000000n) calculating: e2e4")
        self.assertEqual(self.logger.get_summary()["current_task_eta_seconds"], 2)

        # Halving threads mid-task from 4 -> 2 should double remaining ETA from 2s -> 4s
        self.logger.set_active_threads(2)
        self.assertEqual(self.logger.get_summary()["current_task_eta_seconds"], 4)

        # 2. Verify live NPS history records samples alongside hardware samples
        self.logger.record_hardware_sample(sys_cpu=42.0, worker_cpu=35.0, worker_ram_mb=128, available_ram_mb=4096)
        summary = self.logger.get_summary()
        self.assertEqual(len(summary["nps_history"]), 1)
        self.assertIn("nps", summary["nps_history"][0])
        self.assertIn("avg_nps", summary["nps_history"][0])

        # 3. Verify dark dropdown styling on combo_mode & spin_threads -> _on_threads_changed wiring in gui.py
        gui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "gui.py")
        with open(gui_path, "r", encoding="utf-8") as f:
            gui_src = f.read()
        self.assertIn("QComboBox QAbstractItemView", gui_src)
        self.assertIn("self.combo_mode.setView(combo_view)", gui_src)
        self.assertIn("#1e293b", gui_src)
        self.assertIn("#f8fafc", gui_src)
        self.assertIn("self.spin_threads.valueChanged.connect(self._on_threads_changed)", gui_src)
        self.assertIn("def _on_threads_changed(self, threads: int):", gui_src)


if __name__ == "__main__":
    unittest.main()


