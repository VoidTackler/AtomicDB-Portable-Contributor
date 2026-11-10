"""
AtomicDB Portable - PySide6 Native Windows GUI Application
Provides real-time telemetry meters, allocation controls, and strict local stop precedence.
Includes complete inputs, number spinners, and checkboxes for every variable in the open-source contributor API.
"""

import sys
import os
import time
import logging
from typing import Optional

logger = logging.getLogger("AtomicDB.GUI")

# PySide6 imports with graceful headless fallback
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
        QCheckBox, QProgressBar, QTextEdit, QGroupBox, QLineEdit, QTabWidget,
        QScrollArea, QSystemTrayIcon, QMenu, QMessageBox, QTableWidget,
        QTableWidgetItem, QHeaderView, QSplitter, QFrame, QSizePolicy
    )
    from PySide6.QtCore import Qt, QTimer, Signal, QObject
    from PySide6.QtGui import QIcon, QFont, QColor
    HAS_QT = True
except ImportError:
    HAS_QT = False

try:
    from .configuration import PortableConfig
    from .resource_manager import ResourceManager
    from .worker_manager import WorkerManager
    from .engine_manager import EngineManager
    from .security import SecurityManager
    from .analytics_logger import AnalyticsLogger
except (ImportError, ValueError):
    from configuration import PortableConfig
    from resource_manager import ResourceManager
    from worker_manager import WorkerManager
    from engine_manager import EngineManager
    from security import SecurityManager
    from analytics_logger import AnalyticsLogger

class WorkerSignals(QObject):
    log_received = Signal(str)
    stats_updated = Signal(dict)
    status_changed = Signal(str)
    analytics_updated = Signal(dict)

class MainWindow(QMainWindow if HAS_QT else object):
    """Main PySide6 Window for AtomicDB Portable Client."""

    def __init__(self, config: PortableConfig, resource_mgr: ResourceManager,
                 worker_mgr: WorkerManager, engine_mgr: EngineManager,
                 security: SecurityManager, analytics_logger=None):
        if not HAS_QT:
            raise RuntimeError("PySide6 is required to launch graphical interface.")
        super().__init__()

        self.config = config
        self.resource_mgr = resource_mgr
        self.worker_mgr = worker_mgr
        self.engine_mgr = engine_mgr
        self.security = security
        self.analytics_logger = analytics_logger or getattr(worker_mgr, 'analytics_logger', None)
        if not self.analytics_logger:
            self.analytics_logger = AnalyticsLogger(self.config.base_dir)
            self.worker_mgr.set_analytics_logger(self.analytics_logger)

        self.signals = WorkerSignals()
        self.worker_mgr.add_log_callback(self.signals.log_received.emit)
        self.analytics_logger.add_listener(lambda summary: self.signals.analytics_updated.emit(summary))
        self.signals.analytics_updated.connect(self._update_analytics_ui)

        self.setWindowTitle("AtomicDB Portable — Windows x64 Computing Client")
        self.setMinimumSize(700, 480)
        self.resize(1020, 820)

        self._apply_dark_style()
        self._init_ui()
        self._setup_timers()
        self._update_cmd_preview()

    def _apply_dark_style(self):
        """Applies a professional dark engineering palette matching fleet console."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b1120;
                color: #f1f5f9;
                font-family: 'Segoe UI', 'Plus Jakarta Sans', sans-serif;
            }
            QWidget {
                color: #e2e8f0;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #1e293b;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 16px;
                font-weight: 600;
                color: #38bdf8;
                background-color: #0f172a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #0284c7;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton#btnStop {
                background-color: #dc2626;
            }
            QPushButton#btnStop:hover {
                background-color: #b91c1c;
            }
            QPushButton#btnLocalStop {
                background-color: #e11d48;
                font-size: 13px;
                padding: 10px 18px;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                padding: 6px 10px;
                border-radius: 5px;
                color: #f8fafc;
                font-family: 'Consolas', 'JetBrains Mono', monospace;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 1px solid #38bdf8;
            }
            QCheckBox {
                spacing: 8px;
                color: #cbd5e1;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #475569;
                border-radius: 4px;
                background-color: #1e293b;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border-color: #38bdf8;
            }
            QProgressBar {
                border: 1px solid #1e293b;
                border-radius: 4px;
                text-align: center;
                background-color: #1e293b;
                color: #ffffff;
                font-family: 'Consolas', 'JetBrains Mono', monospace;
            }
            QProgressBar::chunk {
                background-color: #0284c7;
                border-radius: 3px;
            }
            QTextEdit {
                background-color: #020617;
                color: #38bdf8;
                border: 1px solid #1e293b;
                font-family: 'Consolas', 'JetBrains Mono', monospace;
                font-size: 12px;
                border-radius: 6px;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QSplitter::handle:vertical {
                background-color: #334155;
                height: 8px;
                border-radius: 4px;
                margin: 2px 24px;
            }
            QSplitter::handle:vertical:hover {
                background-color: #38bdf8;
            }
            QScrollBar:vertical {
                border: none;
                background: #0b1120;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                min-height: 24px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #38bdf8;
            }
            QScrollBar:horizontal {
                border: none;
                background: #0b1120;
                height: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #334155;
                min-width: 24px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #38bdf8;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                width: 0px;
                height: 0px;
            }
        """)

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        self.main_splitter = QSplitter(Qt.Vertical)

        # Upper pane: Scrollable controls container
        scroll_controls = QScrollArea()
        scroll_controls.setWidgetResizable(True)
        scroll_controls.setFrameShape(QFrame.NoFrame)
        scroll_controls.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_controls.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(4, 4, 4, 4)
        controls_layout.setSpacing(10)

        # Header bar
        header = QHBoxLayout()
        title_label = QLabel("ATOMICDB DISTRIBUTED CLIENT (USB PORTABLE)")
        title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc; letter-spacing: 0.5px;")
        header.addWidget(title_label)

        self.lbl_server_status = QLabel("Server: Fixed & Built-in (https://belzedar.duckdns.org)")
        self.lbl_server_status.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 11px;")
        header.addStretch()
        header.addWidget(self.lbl_server_status)
        controls_layout.addLayout(header)

        # Telemetry & Resource Monitor Box
        res_box = QGroupBox("HOST HARDWARE & REAL-TIME TELEMETRY")
        res_layout = QVBoxLayout(res_box)

        # CPU row
        cpu_row = QHBoxLayout()
        cpu_row.addWidget(QLabel("System CPU:"))
        self.bar_sys_cpu = QProgressBar()
        self.bar_sys_cpu.setRange(0, 100)
        cpu_row.addWidget(self.bar_sys_cpu)

        cpu_row.addWidget(QLabel("Worker CPU:"))
        self.bar_worker_cpu = QProgressBar()
        self.bar_worker_cpu.setRange(0, 100)
        cpu_row.addWidget(self.bar_worker_cpu)
        res_layout.addLayout(cpu_row)

        # RAM row
        ram_row = QHBoxLayout()
        ram_row.addWidget(QLabel("RAM Allocation:"))
        self.lbl_ram_details = QLabel("Detecting RAM...")
        self.lbl_ram_details.setStyleSheet("color: #38bdf8; font-family: monospace;")
        ram_row.addWidget(self.lbl_ram_details)
        ram_row.addStretch()
        self.lbl_cores = QLabel(f"Cores: {self.resource_mgr.physical_cores} Physical / {self.resource_mgr.logical_cores} Logical")
        self.lbl_cores.setStyleSheet("color: #94a3b8;")
        ram_row.addWidget(self.lbl_cores)
        res_layout.addLayout(ram_row)

        controls_layout.addWidget(res_box)

        # =========================================================================
        # COMPLETE OPENBENCH CONTRIBUTOR API VARIABLES (INPUTS, NUMBERS, CHECKBOXES)
        # =========================================================================
        cfg_box = QGroupBox("OPENBENCH CONTRIBUTOR API PARAMETERS (UPSTREAM VARIABLES)")
        cfg_layout = QVBoxLayout(cfg_box)

        # 1. Custom Engine & Syzygy paths (Credentials and Server URL are unadjustable & hidden)
        grid_top = QGridLayout()

        # --engine
        grid_top.addWidget(QLabel("Custom Engine (--engine):"), 0, 0)
        self.txt_engine = QLineEdit()
        self.txt_engine.setPlaceholderText("Optional path to custom engine binary (blank = default bundled engine)")
        self.txt_engine.setText(self.config.get("openbench", "engine_path", default=""))
        self.txt_engine.textChanged.connect(self._update_cmd_preview)
        grid_top.addWidget(self.txt_engine, 0, 1)

        # --syzygy
        grid_top.addWidget(QLabel("Syzygy TBs (--syzygy):"), 1, 0)
        self.txt_syzygy = QLineEdit()
        self.txt_syzygy.setPlaceholderText("Directories separated by ; (blank = auto-manage on USB)")
        self.txt_syzygy.setText(self.config.get("openbench", "syzygy_path", default=""))
        self.txt_syzygy.textChanged.connect(self._update_cmd_preview)
        grid_top.addWidget(self.txt_syzygy, 1, 1)

        cfg_layout.addLayout(grid_top)

        # 2. Number Spinners (Allocation & Engine updates)
        grid_num = QHBoxLayout()

        grid_num.addWidget(QLabel("CPU Mode:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Adaptive", "Balanced", "Maximum", "Custom"])
        current_mode = self.config.get("resources", "cpu_mode", default="Adaptive")
        self.combo_mode.setCurrentText(current_mode)
        self.combo_mode.currentTextChanged.connect(self._on_mode_changed)
        grid_num.addWidget(self.combo_mode)

        # -T / --threads
        grid_num.addWidget(QLabel("Threads (-T):"))
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, self.resource_mgr.logical_cores)
        self.spin_threads.setValue(self.config.get("resources", "threads", default=4))
        self.spin_threads.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(self.spin_threads)

        # --jobs
        grid_num.addWidget(QLabel("Jobs (--jobs):"))
        self.spin_jobs = QSpinBox()
        self.spin_jobs.setRange(1, 64)
        self.spin_jobs.setValue(self.config.get("openbench", "jobs", default=1))
        self.spin_jobs.setToolTip("Number of concurrent analyses to run, splitting -T threads")
        self.spin_jobs.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(self.spin_jobs)

        # --hash
        grid_num.addWidget(QLabel("Hash MB (--hash):"))
        self.spin_hash = QSpinBox()
        self.spin_hash.setRange(64, 65536)
        self.spin_hash.setSingleStep(128)
        self.spin_hash.setValue(self.config.get("resources", "hash_mb", default=1024))
        self.spin_hash.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(self.spin_hash)

        # --engine-update-minutes
        grid_num.addWidget(QLabel("Engine Check Min (--engine-update-minutes):"))
        self.spin_engine_update_min = QDoubleSpinBox()
        self.spin_engine_update_min.setRange(0.5, 1440.0)
        self.spin_engine_update_min.setSingleStep(5.0)
        self.spin_engine_update_min.setValue(float(self.config.get("openbench", "engine_update_minutes", default=15.0)))
        self.spin_engine_update_min.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(self.spin_engine_update_min)

        cfg_layout.addLayout(grid_num)

        # 3. Checkboxes (All OpenBench Boolean API flags)
        chk_layout = QHBoxLayout()

        self.chk_no_fetch_syzygy = QCheckBox("Disable Tablebases (--no-fetch-syzygy)")
        self.chk_no_fetch_syzygy.setToolTip("Checked: skip Syzygy tablebases (saves disk space/bandwidth)\nUnchecked: download and cache Syzygy 3-4-5 tablebases directly onto this USB drive (zero host C: trace)")
        self.chk_no_fetch_syzygy.setChecked(self.config.get("openbench", "no_fetch_syzygy", default=True))
        self.chk_no_fetch_syzygy.toggled.connect(self._update_cmd_preview)
        chk_layout.addWidget(self.chk_no_fetch_syzygy)

        self.chk_solve = QCheckBox("Solve Tasks (--solve)")
        self.chk_solve.setToolTip("Serve exhaustive proof solve tasks (gracefully auto-skips without failing tasks if engine lacks custom solve extension)")
        self.chk_solve.setChecked(self.config.get("openbench", "solve", default=False))
        self.chk_solve.toggled.connect(self._update_cmd_preview)
        chk_layout.addWidget(self.chk_solve)

        self.chk_no_auto_update = QCheckBox("No Worker Update (--no-auto-update)")
        self.chk_no_auto_update.setToolTip("Do not auto-update the official worker script from server")
        self.chk_no_auto_update.setChecked(self.config.get("openbench", "no_auto_update", default=False))
        self.chk_no_auto_update.toggled.connect(self._update_cmd_preview)
        chk_layout.addWidget(self.chk_no_auto_update)

        self.chk_no_engine_update = QCheckBox("No Engine Update (--no-engine-update)")
        self.chk_no_engine_update.setToolTip("Do not update/switch the engine binary during run")
        self.chk_no_engine_update.setChecked(self.config.get("openbench", "no_engine_update", default=False))
        self.chk_no_engine_update.toggled.connect(self._update_cmd_preview)
        chk_layout.addWidget(self.chk_no_engine_update)

        self.chk_once = QCheckBox("Run Once (--once)")
        self.chk_once.setToolTip("Run a single analysis pass/task and exit cleanly (useful for verification)")
        self.chk_once.setChecked(self.config.get("openbench", "once", default=False))
        self.chk_once.toggled.connect(self._update_cmd_preview)
        chk_layout.addWidget(self.chk_once)

        cfg_layout.addLayout(chk_layout)

        # 4. Command Line Live Preview
        cmd_preview_row = QHBoxLayout()
        cmd_preview_row.addWidget(QLabel("Command Preview:"))
        self.lbl_cmd_preview = QLabel("python atomicdb_worker.py ...")
        self.lbl_cmd_preview.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 11px;")
        cmd_preview_row.addWidget(self.lbl_cmd_preview)
        cmd_preview_row.addStretch()
        cfg_layout.addLayout(cmd_preview_row)

        controls_layout.addWidget(cfg_box)

        # Primary Control Bar with LOCAL STOP PRECEDENCE
        ctrl_layout = QHBoxLayout()

        self.btn_start = QPushButton("Start Contributing")
        self.btn_start.clicked.connect(self._start_worker)
        ctrl_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop Worker")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.clicked.connect(self._stop_worker)
        self.btn_stop.setEnabled(False)
        ctrl_layout.addWidget(self.btn_stop)

        # Emergency stop button
        self.btn_local_stop = QPushButton("EMERGENCY STOP (Instant Halt)")
        self.btn_local_stop.setObjectName("btnLocalStop")
        self.btn_local_stop.setCheckable(True)
        is_local_stopped = self.config.get("safety", "local_stop_active", default=False)
        self.btn_local_stop.setChecked(is_local_stopped)
        self._update_local_stop_button_text(is_local_stopped)
        self.btn_local_stop.toggled.connect(self._on_local_stop_toggled)
        ctrl_layout.addWidget(self.btn_local_stop)

        controls_layout.addLayout(ctrl_layout)
        scroll_controls.setWidget(controls_container)
        self.main_splitter.addWidget(scroll_controls)

        # Multi-tab view: 1. Live Analysis Console, 2. Local USB Analytics & History
        self.tab_widget = QTabWidget()
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #1e293b;
                background-color: #0b1120;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #0f172a;
                color: #94a3b8;
                padding: 8px 18px;
                border: 1px solid #1e293b;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #1e293b;
                color: #38bdf8;
                border-color: #38bdf8;
            }
        """)

        # Tab 1: Live Analysis Console
        tab_console = QWidget()
        tab_console_layout = QVBoxLayout(tab_console)
        tab_console_layout.setContentsMargins(8, 8, 8, 8)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(240)
        self.console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tab_console_layout.addWidget(self.console)

        console_bar = QHBoxLayout()
        btn_clear_console = QPushButton("Clear Console Screen")
        btn_clear_console.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-size: 11px; padding: 4px 10px;")
        btn_clear_console.clicked.connect(self.console.clear)
        console_bar.addWidget(btn_clear_console)

        self.chk_autoscroll = QCheckBox("Auto-scroll")
        self.chk_autoscroll.setChecked(True)
        self.chk_autoscroll.setStyleSheet("color: #94a3b8; font-size: 11px;")
        console_bar.addWidget(self.chk_autoscroll)

        console_bar.addStretch()
        lbl_console_hint = QLabel("Real-time worker stdout stream directly from USB runtime")
        lbl_console_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        console_bar.addWidget(lbl_console_hint)
        tab_console_layout.addLayout(console_bar)

        self.tab_widget.addTab(tab_console, "Live Analysis Console")

        # Tab 2: Local USB Analytics & History
        tab_analytics = QWidget()
        tab_analytics_layout = QVBoxLayout(tab_analytics)
        tab_analytics_layout.setContentsMargins(8, 8, 8, 8)

        # KPI Summary Grid Cards
        kpi_group = QGroupBox("LOCAL USB METRICS & HISTORICAL RUNTIME COUNTERS")
        kpi_layout = QGridLayout(kpi_group)

        self.lbl_tasks_completed = QLabel("0")
        self.lbl_tasks_completed.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")
        self.lbl_total_nodes = QLabel("0")
        self.lbl_total_nodes.setStyleSheet("font-size: 20px; font-weight: bold; color: #4ade80;")
        self.lbl_avg_nodes = QLabel("0")
        self.lbl_avg_nodes.setStyleSheet("font-size: 20px; font-weight: bold; color: #fbbf24;")
        self.lbl_avg_nps = QLabel("0")
        self.lbl_avg_nps.setStyleSheet("font-size: 20px; font-weight: bold; color: #a78bfa;")
        self.lbl_tb_hits = QLabel("0")
        self.lbl_tb_hits.setStyleSheet("font-size: 20px; font-weight: bold; color: #f472b6;")
        self.lbl_crashes = QLabel("0")
        self.lbl_crashes.setStyleSheet("font-size: 20px; font-weight: bold; color: #ef4444;")

        def make_card(title: str, widget: QLabel):
            box = QWidget()
            layout = QVBoxLayout(box)
            layout.setContentsMargins(4, 4, 4, 4)
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("color: #94a3b8; font-size: 11px; text-transform: uppercase;")
            layout.addWidget(lbl_title)
            layout.addWidget(widget)
            return box

        kpi_layout.addWidget(make_card("Tasks Completed", self.lbl_tasks_completed), 0, 0)
        kpi_layout.addWidget(make_card("Total Nodes", self.lbl_total_nodes), 0, 1)
        kpi_layout.addWidget(make_card("Avg Nodes / Task", self.lbl_avg_nodes), 0, 2)
        kpi_layout.addWidget(make_card("Avg NPS (Speed)", self.lbl_avg_nps), 0, 3)
        kpi_layout.addWidget(make_card("Tablebase Hits", self.lbl_tb_hits), 0, 4)
        kpi_layout.addWidget(make_card("Engine Failures / Crashes", self.lbl_crashes), 0, 5)

        tab_analytics_layout.addWidget(kpi_group)

        # Recent Tasks Table
        table_group = QGroupBox("PERSISTENT TASK EXECUTION HISTORY (Saved to USB /logs/history.json)")
        table_layout = QVBoxLayout(table_group)

        self.table_tasks = QTableWidget()
        self.table_tasks.setColumnCount(7)
        self.table_tasks.setHorizontalHeaderLabels(["Timestamp", "Task ID", "Type", "Nodes", "NPS", "TB WDL/DTZ", "Result / Score"])
        self.table_tasks.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_tasks.setAlternatingRowColors(True)
        self.table_tasks.setMinimumHeight(280)
        self.table_tasks.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_tasks.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_tasks.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_tasks.setStyleSheet("""
            QTableWidget {
                background-color: #0b1120;
                alternate-background-color: #0f172a;
                gridline-color: #1e293b;
                color: #e2e8f0;
                font-size: 12px;
                border: 1px solid #1e293b;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #38bdf8;
                font-weight: 600;
                padding: 6px;
                border: none;
            }
        """)
        table_layout.addWidget(self.table_tasks)

        # Local USB Storage path indicator
        storage_bar = QHBoxLayout()
        logs_path = os.path.join(self.config.base_dir, "logs")
        self.lbl_storage_info = QLabel(f"USB Storage: {logs_path} (history.json, analytics.json, crashes.log, activity.log)")
        self.lbl_storage_info.setStyleSheet("color: #64748b; font-size: 11px;")
        storage_bar.addWidget(self.lbl_storage_info)
        storage_bar.addStretch()

        btn_refresh_analytics = QPushButton("Refresh from Disk")
        btn_refresh_analytics.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 4px 10px;")
        btn_refresh_analytics.clicked.connect(self._refresh_analytics_from_disk)
        storage_bar.addWidget(btn_refresh_analytics)

        table_layout.addLayout(storage_bar)
        table_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tab_analytics_layout.addWidget(table_group)

        self.tab_widget.addTab(tab_analytics, "USB Analytics & Task History")
        self.main_splitter.addWidget(self.tab_widget)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([330, 470])
        main_layout.addWidget(self.main_splitter)

        # Initial load of analytics data into UI if logger present
        if self.analytics_logger:
            self._update_analytics_ui(self.analytics_logger.get_summary())

        # Signals
        self.signals.log_received.connect(self._append_log)

    def _update_cmd_preview(self):
        """Generates real-time preview of the exact invocation command (credentials & server URL hidden)."""
        t = self.spin_threads.value()
        h = self.spin_hash.value()
        j = self.spin_jobs.value()
        eng = self.txt_engine.text().strip()
        syz = self.txt_syzygy.text().strip()
        interval = self.spin_engine_update_min.value()

        parts = [
            "python atomicdb_worker.py",
            f"-T {t}",
            f"--hash {h}"
        ]
        if j > 1:
            parts.append(f"--jobs {j}")
        if eng:
            parts.append(f'--engine "{eng}"')
        if syz:
            parts.append(f'--syzygy "{syz}"')
        if self.chk_no_fetch_syzygy.isChecked():
            parts.append("--no-fetch-syzygy")
        else:
            parts.append("--fetch-syzygy")
        if self.chk_solve.isChecked():
            parts.append("--solve")
        if self.chk_no_auto_update.isChecked():
            parts.append("--no-auto-update")
        if self.chk_no_engine_update.isChecked():
            parts.append("--no-engine-update")
        if interval != 15.0:
            parts.append(f"--engine-update-minutes {interval}")
        if self.chk_once.isChecked():
            parts.append("--once")

        self.lbl_cmd_preview.setText(" ".join(parts))

    def _update_local_stop_button_text(self, stopped: bool):
        if stopped:
            self.btn_local_stop.setText("EMERGENCY STOP ENGAGED (Worker Halted)")
            self.btn_local_stop.setStyleSheet("background-color: #e11d48; font-weight: bold; border: 2px solid white;")
        else:
            self.btn_local_stop.setText("Emergency Stop (Instant Halt)")
            self.btn_local_stop.setStyleSheet("background-color: #475569;")

    def _on_local_stop_toggled(self, checked: bool):
        self.config.set("safety", "local_stop_active", checked)
        self._update_local_stop_button_text(checked)
        if checked:
            self._append_log("[SAFETY] Emergency Stop engaged. Worker halted.")
            self._stop_worker()
        else:
            self._append_log("[SAFETY] Emergency Stop disengaged.")

    def _on_mode_changed(self, mode: str):
        self.config.set("resources", "cpu_mode", mode)
        self.resource_mgr.mode = mode
        threads, hash_mb = self.resource_mgr.compute_allocation(mode)
        self.spin_threads.setValue(threads)
        self.spin_hash.setValue(hash_mb)
        self._append_log(f"[CONFIG] Switched CPU mode to {mode}. Recommended: {threads} threads, {hash_mb}MB hash.")
        self._update_cmd_preview()

    def _setup_timers(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_tick)
        self.timer.start(2500)

    def _poll_tick(self):
        snapshot = self.resource_mgr.get_system_snapshot(self.worker_mgr.current_pid)
        self.bar_sys_cpu.setValue(int(snapshot["system_cpu_pct"]))
        self.bar_worker_cpu.setValue(int(snapshot["worker_cpu_pct"]))

        # Check adaptive hysteresis
        allocation_changed = self.resource_mgr.update_adaptive_state(snapshot["system_cpu_pct"])
        if allocation_changed and self.worker_mgr.is_running:
            self._append_log("[ADAPTIVE] System load threshold triggered. Adjusting worker parameters gracefully...")

        ram_used = snapshot["worker_ram_mb"]
        avail_ram = snapshot["available_ram_mb"]
        self.lbl_ram_details.setText(f"Worker RSS: {ram_used} MB | Host Avail: {avail_ram} MB")

        status_str = "ACTIVE" if self.worker_mgr.is_running else "IDLE"
        if snapshot["is_throttled"]:
            status_str = "THROTTLED"

        # Auto-restore buttons if worker stopped
        if not self.worker_mgr.is_running and self.btn_stop.isEnabled():
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def _start_worker(self):
        user = "PortableExe"
        stored_enc = self.config.get("openbench", "password_encrypted", default="")
        pwd = self.security.caesar_decrypt(stored_enc) if stored_enc else "ExePassword"
        # Server URL is fixed, unadjustable and hidden from user interface
        server_url = "https://belzedar.duckdns.org"

        threads = self.spin_threads.value()
        hash_mb = self.spin_hash.value()
        jobs = self.spin_jobs.value()
        engine_path = self.txt_engine.text().strip()
        syzygy_path = self.txt_syzygy.text().strip()
        no_fetch_syzygy = self.chk_no_fetch_syzygy.isChecked()
        solve = self.chk_solve.isChecked()
        no_auto_update = self.chk_no_auto_update.isChecked()
        no_engine_update = self.chk_no_engine_update.isChecked()
        engine_update_min = self.spin_engine_update_min.value()
        once = self.chk_once.isChecked()

        # Save all settings into portable configuration (password encrypted with Caesar cipher)
        self.config.set("openbench", "server", server_url)
        self.config.set("openbench", "username", "PortableExe")
        self.config.set("openbench", "password_encrypted", self.security.caesar_encrypt(pwd))
        self.config.set("openbench", "jobs", jobs)
        self.config.set("openbench", "engine_path", engine_path)
        self.config.set("openbench", "syzygy_path", syzygy_path)
        self.config.set("openbench", "no_fetch_syzygy", no_fetch_syzygy)
        self.config.set("openbench", "solve", solve)
        self.config.set("openbench", "no_auto_update", no_auto_update)
        self.config.set("openbench", "no_engine_update", no_engine_update)
        self.config.set("openbench", "engine_update_minutes", engine_update_min)
        self.config.set("openbench", "once", once)
        self.config.set("resources", "threads", threads)
        self.config.set("resources", "hash_mb", hash_mb)

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.worker_mgr.start_worker(
            username=user,
            password=pwd,
            server_url=server_url,
            threads=threads,
            hash_mb=hash_mb,
            jobs=jobs,
            engine=engine_path,
            syzygy=syzygy_path,
            no_fetch_syzygy=no_fetch_syzygy,
            solve=solve,
            no_auto_update=no_auto_update,
            no_engine_update=no_engine_update,
            engine_update_minutes=engine_update_min,
            once=once
        )

    def _stop_worker(self):
        self.worker_mgr.stop_worker()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _append_log(self, text: str):
        self.console.append(text)
        if getattr(self, "chk_autoscroll", None) and self.chk_autoscroll.isChecked():
            cursor = self.console.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.console.setTextCursor(cursor)

    def _refresh_analytics_from_disk(self):
        """Reloads analytics and history directly from USB disk."""
        if self.analytics_logger:
            self.analytics_logger.load_persisted_data()
            self._update_analytics_ui(self.analytics_logger.get_summary())

    def _update_analytics_ui(self, summary: dict):
        """Updates KPI counters and tasks table on USB analytics signal."""
        try:
            total_tasks = summary.get("total_tasks_completed", 0)
            total_nodes = summary.get("total_nodes_analyzed", 0)
            avg_nodes = summary.get("average_nodes_per_task", 0)
            avg_nps = summary.get("average_nps", 0)
            tb_hits = summary.get("tablebase_hits", 0)
            crashes = summary.get("crashes", 0)

            self.lbl_tasks_completed.setText(f"{total_tasks:,}")
            if total_nodes >= 1_000_000_000:
                self.lbl_total_nodes.setText(f"{total_nodes / 1_000_000_000:.2f} B")
            elif total_nodes >= 1_000_000:
                self.lbl_total_nodes.setText(f"{total_nodes / 1_000_000:.2f} M")
            else:
                self.lbl_total_nodes.setText(f"{total_nodes:,}")

            if avg_nodes >= 1_000_000:
                self.lbl_avg_nodes.setText(f"{avg_nodes / 1_000_000:.2f} M")
            else:
                self.lbl_avg_nodes.setText(f"{avg_nodes:,}")

            if avg_nps >= 1_000_000:
                self.lbl_avg_nps.setText(f"{avg_nps / 1_000_000:.2f} M/s")
            elif avg_nps >= 1_000:
                self.lbl_avg_nps.setText(f"{avg_nps / 1_000:.1f} k/s")
            else:
                self.lbl_avg_nps.setText(f"{avg_nps:,}/s")

            self.lbl_tb_hits.setText(f"{tb_hits:,}")
            self.lbl_crashes.setText(f"{crashes:,}")

            recent = summary.get("recent_tasks", [])
            self.table_tasks.setRowCount(len(recent))
            for row_idx, task in enumerate(recent):
                ts = task.get("timestamp", "")
                if "T" in ts:
                    ts = ts.split("T")[1][:8]
                task_id = str(task.get("task_id", ""))
                task_type = str(task.get("type", "engine")).upper()
                nodes = f"{task.get('nodes', 0):,}"
                nps = f"{task.get('nps', 0):,}"
                tb_info = "-"
                if task.get("is_tb"):
                    tb_info = f"wdl={task.get('wdl')}"
                    if task.get("dtz") is not None:
                        tb_info += f" dtz={task.get('dtz')}"
                result = str(task.get("summary", ""))

                items = [
                    QTableWidgetItem(ts),
                    QTableWidgetItem(task_id),
                    QTableWidgetItem(task_type),
                    QTableWidgetItem(nodes),
                    QTableWidgetItem(nps),
                    QTableWidgetItem(tb_info),
                    QTableWidgetItem(result)
                ]
                for col_idx, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignCenter if col_idx < 6 else Qt.AlignLeft | Qt.AlignVCenter)
                    self.table_tasks.setItem(row_idx, col_idx, item)
        except Exception as e:
            logger.debug(f"Error updating analytics UI: {e}")

