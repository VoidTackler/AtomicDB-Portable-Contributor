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
        QScrollArea, QSystemTrayIcon, QMenu, QMessageBox
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
except (ImportError, ValueError):
    from configuration import PortableConfig
    from resource_manager import ResourceManager
    from worker_manager import WorkerManager
    from engine_manager import EngineManager
    from security import SecurityManager

class WorkerSignals(QObject):
    log_received = Signal(str)
    stats_updated = Signal(dict)
    status_changed = Signal(str)

class MainWindow(QMainWindow if HAS_QT else object):
    """Main PySide6 Window for AtomicDB Portable Client."""

    def __init__(self, config: PortableConfig, resource_mgr: ResourceManager,
                 worker_mgr: WorkerManager, engine_mgr: EngineManager,
                 security: SecurityManager):
        if not HAS_QT:
            raise RuntimeError("PySide6 is required to launch graphical interface.")
        super().__init__()

        self.config = config
        self.resource_mgr = resource_mgr
        self.worker_mgr = worker_mgr
        self.engine_mgr = engine_mgr
        self.security = security

        self.signals = WorkerSignals()
        self.worker_mgr.add_log_callback(self.signals.log_received.emit)

        self.setWindowTitle("AtomicDB Portable — Windows x64 Computing Client")
        self.setMinimumSize(940, 780)

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
        """)

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header bar
        header = QHBoxLayout()
        title_label = QLabel("ATOMICDB DISTRIBUTED CLIENT (USB PORTABLE)")
        title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc; letter-spacing: 0.5px;")
        header.addWidget(title_label)

        self.lbl_server_status = QLabel("Mode: Standalone Client (Zero Remote Server Required)")
        self.lbl_server_status.setStyleSheet("color: #38bdf8; font-family: monospace;")
        header.addStretch()
        header.addWidget(self.lbl_server_status)
        main_layout.addLayout(header)

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

        main_layout.addWidget(res_box)

        # =========================================================================
        # COMPLETE OPENBENCH CONTRIBUTOR API VARIABLES (INPUTS, NUMBERS, CHECKBOXES)
        # =========================================================================
        cfg_box = QGroupBox("OPENBENCH CONTRIBUTOR API PARAMETERS (UPSTREAM VARIABLES)")
        cfg_layout = QVBoxLayout(cfg_box)

        # 1. Credentials & Server (Text Inputs)
        grid_top = QGridLayout()

        # -S / --server
        grid_top.addWidget(QLabel("Server URL (-S):"), 0, 0)
        self.txt_server = QLineEdit()
        self.txt_server.setPlaceholderText("https://belzedar.duckdns.org")
        self.txt_server.setText(self.config.get("openbench", "server", default="https://belzedar.duckdns.org"))
        self.txt_server.textChanged.connect(self._update_cmd_preview)
        grid_top.addWidget(self.txt_server, 0, 1)

        # -U / --user (Fixed to "PortableExe")
        grid_top.addWidget(QLabel("Username (-U):"), 0, 2)
        self.txt_user = QLineEdit()
        self.txt_user.setText("PortableExe")
        self.txt_user.setReadOnly(True)
        self.txt_user.setStyleSheet("background-color: #0f172a; color: #38bdf8; font-weight: bold;")
        self.txt_user.setToolTip("Fixed OpenBench contributor username: PortableExe")
        self.txt_user.textChanged.connect(self._update_cmd_preview)
        grid_top.addWidget(self.txt_user, 0, 3)

        # -P / --password (Fixed to "ExePassword", encrypted in configuration)
        grid_top.addWidget(QLabel("Password (-P):"), 0, 4)
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.Password)
        stored_enc = self.config.get("openbench", "password_encrypted", default="")
        decrypted_pwd = self.security.caesar_decrypt(stored_enc) if stored_enc else "ExePassword"
        self.txt_pass.setText(decrypted_pwd or "ExePassword")
        self.txt_pass.setReadOnly(True)
        self.txt_pass.setStyleSheet("background-color: #0f172a; color: #94a3b8;")
        self.txt_pass.setToolTip("Fixed OpenBench contributor password (encrypted via Caesar cipher in config)")
        self.txt_pass.textChanged.connect(self._update_cmd_preview)
        grid_top.addWidget(self.txt_pass, 0, 5)

        # --engine
        grid_top.addWidget(QLabel("Custom Engine (--engine):"), 1, 0)
        self.txt_engine = QLineEdit()
        self.txt_engine.setPlaceholderText("Optional path to custom engine binary (blank = default)")
        self.txt_engine.setText(self.config.get("openbench", "engine_path", default=""))
        self.txt_engine.textChanged.connect(self._update_cmd_preview)
        grid_top.addWidget(self.txt_engine, 1, 1, 1, 2)

        # --syzygy
        grid_top.addWidget(QLabel("Syzygy TBs (--syzygy):"), 1, 3)
        self.txt_syzygy = QLineEdit()
        self.txt_syzygy.setPlaceholderText("Directories separated by ; (e.g. C:\\syzygy;D:\\tb)")
        self.txt_syzygy.setText(self.config.get("openbench", "syzygy_path", default=""))
        self.txt_syzygy.textChanged.connect(self._update_cmd_preview)
        grid_top.addWidget(self.txt_syzygy, 1, 4, 1, 2)

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

        self.chk_no_fetch_syzygy = QCheckBox("No Tablebase (--no-fetch-syzygy, Zero C: Trace)")
        self.chk_no_fetch_syzygy.setToolTip("Always enabled by default to prevent downloading 1.3 GB tablebases to disk")
        self.chk_no_fetch_syzygy.setChecked(self.config.get("openbench", "no_fetch_syzygy", default=True))
        self.chk_no_fetch_syzygy.toggled.connect(self._update_cmd_preview)
        chk_layout.addWidget(self.chk_no_fetch_syzygy)

        self.chk_solve = QCheckBox("Solve Tasks (--solve)")
        self.chk_solve.setToolTip("Serve exhaustive proof solve tasks besides normal position analysis")
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

        main_layout.addWidget(cfg_box)

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

        # CRITICAL REQUIREMENT: Local stop takes precedence over remote resume!
        self.btn_local_stop = QPushButton("EMERGENCY LOCAL STOP (Precedence Over Remote)")
        self.btn_local_stop.setObjectName("btnLocalStop")
        self.btn_local_stop.setCheckable(True)
        is_local_stopped = self.config.get("safety", "local_stop_active", default=False)
        self.btn_local_stop.setChecked(is_local_stopped)
        self._update_local_stop_button_text(is_local_stopped)
        self.btn_local_stop.toggled.connect(self._on_local_stop_toggled)
        ctrl_layout.addWidget(self.btn_local_stop)

        main_layout.addLayout(ctrl_layout)

        # Live Console Output Box
        log_box = QGroupBox("OFFICIAL WORKER STDOUT / ANALYSIS LOG")
        log_layout = QVBoxLayout(log_box)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        log_layout.addWidget(self.console)
        main_layout.addWidget(log_box)

        # Signals
        self.signals.log_received.connect(self._append_log)

    def _update_cmd_preview(self):
        """Generates real-time preview of the exact invocation command."""
        user = self.txt_user.text().strip() or "USER"
        pwd = "********" if self.txt_pass.text() else "PASSWORD"
        srv = self.txt_server.text().strip() or "https://belzedar.duckdns.org"
        t = self.spin_threads.value()
        h = self.spin_hash.value()
        j = self.spin_jobs.value()
        eng = self.txt_engine.text().strip()
        syz = self.txt_syzygy.text().strip()
        interval = self.spin_engine_update_min.value()

        parts = [
            "python atomicdb_worker.py",
            f"-U {user}",
            f"-P {pwd}",
            f"-S {srv}",
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
            self.btn_local_stop.setText("LOCAL STOP ACTIVE (Remote Commands Locked Out)")
            self.btn_local_stop.setStyleSheet("background-color: #e11d48; font-weight: bold; border: 2px solid white;")
        else:
            self.btn_local_stop.setText("Engage Local Stop Override")
            self.btn_local_stop.setStyleSheet("background-color: #475569;")

    def _on_local_stop_toggled(self, checked: bool):
        self.config.set("safety", "local_stop_active", checked)
        self._update_local_stop_button_text(checked)
        if checked:
            self._append_log("[SAFETY] Local host operator engaged Local Stop. Worker stopped. Remote RESUME commands are strictly disabled.")
            self._stop_worker()
        else:
            self._append_log("[SAFETY] Local Stop Override disengaged by host operator.")

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

        # Telemetry to central management server
        status_str = "ACTIVE" if self.worker_mgr.is_running else "IDLE"
        status_str = "ACTIVE" if self.worker_mgr.is_running else "IDLE"
        if snapshot["is_throttled"]:
            status_str = "THROTTLED"

    def _start_worker(self):
        user = "PortableExe"
        pwd = self.txt_pass.text().strip() or "ExePassword"
        server_url = self.txt_server.text().strip() or "https://belzedar.duckdns.org"

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
