"""
AtomicDB Portable - PySide6 Native Windows GUI Application
Provides real-time telemetry meters, allocation controls, and strict local stop precedence.
Includes complete inputs, number spinners, checkboxes, session metrics, current task monitor with ETA,
permanent lifetime statistics, and interactive real-time time-series graphs.
"""

import sys
import os
import time
import ctypes
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger("AtomicDB.GUI")

APP_NAME = "Background Processing Utility"
IDI_APPLICATION = 32512  # Win32 MAKEINTRESOURCE(32512)

def make_int_resource(resource_id: int) -> ctypes.c_void_p:
    """Equivalent to Win32 MAKEINTRESOURCE(id)."""
    return ctypes.c_void_p(int(resource_id) & 0xFFFF)

# PySide6 imports with graceful headless fallback
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
        QCheckBox, QProgressBar, QTextEdit, QGroupBox, QLineEdit, QTabWidget,
        QScrollArea, QSystemTrayIcon, QMenu, QMessageBox, QTableWidget,
        QTableWidgetItem, QHeaderView, QSplitter, QFrame, QSizePolicy, QSlider, QStyle
    )
    from PySide6.QtCore import Qt, QTimer, Signal, QObject, QPointF, QRectF
    from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPen, QBrush, QPolygonF, QImage, QPixmap
    HAS_QT = True
except ImportError:
    HAS_QT = False

def get_default_windows_app_icon():
    """
    Returns the default Windows application icon:
    IDI_APPLICATION = MAKEINTRESOURCE(32512).
    """
    if not HAS_QT:
        return None
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            user32.LoadIconW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            user32.LoadIconW.restype = ctypes.c_void_p
            hicon = user32.LoadIconW(None, make_int_resource(IDI_APPLICATION))
            if hicon:
                img = QImage.fromHICON(int(hicon))
                if not img.isNull():
                    return QIcon(QPixmap.fromImage(img))
        except Exception as exc:
            logger.debug(f"Could not load Win32 IDI_APPLICATION (32512): {exc}")
    try:
        style = QApplication.style()
        if style is not None:
            return style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    except Exception:
        pass
    return QIcon()

try:
    from .configuration import PortableConfig
    from .resource_manager import ResourceManager
    from .worker_manager import WorkerManager
    from .engine_manager import EngineManager
    from .security import SecurityManager
    from .analytics_logger import AnalyticsLogger, format_nodes_compact
except (ImportError, ValueError):
    from configuration import PortableConfig
    from resource_manager import ResourceManager
    from worker_manager import WorkerManager
    from engine_manager import EngineManager
    from security import SecurityManager
    from analytics_logger import AnalyticsLogger, format_nodes_compact

class WorkerSignals(QObject if HAS_QT else object):
    if HAS_QT:
        log_received = Signal(str)
        stats_updated = Signal(dict)
        status_changed = Signal(str)
        analytics_updated = Signal(dict)

# =============================================================================
# REAL-TIME CANVAS CHART WIDGETS (THIS SESSION)
# =============================================================================

class CPUChartWidget(QWidget if HAS_QT else object):
    """Real-time Canvas/Painter chart for System CPU % vs Worker CPU % over time."""

    def __init__(self, parent=None):
        if not HAS_QT:
            return
        super().__init__(parent)
        self.history: List[Dict[str, Any]] = []
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def update_data(self, history: List[Dict[str, Any]]):
        self.history = history or []
        if HAS_QT:
            self.update()

    def paintEvent(self, event):
        if not HAS_QT:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        # Dark surface background & border
        painter.fillRect(0, 0, w, h, QColor("#020617"))
        painter.setPen(QPen(QColor("#1e293b"), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        # Title & legend
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(10, 18, "CPU USAGE OVER TIME (%)")

        sys_val = self.history[-1].get("system_cpu", 0) if self.history else 0
        wrk_val = self.history[-1].get("worker_cpu", 0) if self.history else 0
        txt = f"Sys: {sys_val:.1f}% | Wrk: {wrk_val:.1f}%"
        painter.setPen(QColor("#38bdf8"))
        painter.drawText(max(10, w - 180), 18, txt)

        pad_l, pad_r, pad_t, pad_b = 35, 10, 26, 18
        pw = max(10, w - pad_l - pad_r)
        ph = max(10, h - pad_t - pad_b)

        # Horizontal gridlines
        painter.setPen(QPen(QColor("#1e293b"), 1, Qt.DotLine))
        for pct in (0.25, 0.5, 0.75):
            y = pad_t + ph * (1.0 - pct)
            painter.drawLine(pad_l, int(y), pad_l + pw, int(y))

        # Y Axis labels
        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor("#64748b"))
        painter.drawText(4, int(pad_t + 10), "100%")
        painter.drawText(10, int(pad_t + ph * 0.5 + 4), "50%")
        painter.drawText(16, int(pad_t + ph), "0%")

        if len(self.history) < 2:
            painter.setPen(QColor("#475569"))
            painter.drawText(pad_l + pw // 4, pad_t + ph // 2, "Collecting CPU telemetry (0.8s)...")
            return

        n = len(self.history)
        step = pw / max(1, n - 1)

        # Draw System CPU line (Amber #fbbf24)
        sys_poly = QPolygonF()
        for i, pt in enumerate(self.history):
            val = min(100.0, max(0.0, float(pt.get("system_cpu", 0))))
            x = pad_l + i * step
            y = pad_t + ph * (1.0 - val / 100.0)
            sys_poly.append(QPointF(x, y))

        painter.setPen(QPen(QColor("#fbbf24"), 1.8))
        painter.drawPolyline(sys_poly)

        # Draw Worker CPU line (Sky Blue #38bdf8)
        wrk_poly = QPolygonF()
        for i, pt in enumerate(self.history):
            val = min(100.0, max(0.0, float(pt.get("worker_cpu", 0))))
            x = pad_l + i * step
            y = pad_t + ph * (1.0 - val / 100.0)
            wrk_poly.append(QPointF(x, y))

        painter.setPen(QPen(QColor("#38bdf8"), 2.0))
        painter.drawPolyline(wrk_poly)

        # Draw X-axis timestamps
        painter.setFont(QFont("Consolas", 7))
        painter.setPen(QColor("#64748b"))
        t_start = self.history[0].get("timestamp", "")
        t_end = self.history[-1].get("timestamp", "")
        t_mid = self.history[len(self.history) // 2].get("timestamp", "")
        painter.drawText(pad_l, h - 3, t_start)
        if len(self.history) > 4:
            painter.drawText(pad_l + pw // 2 - 25, h - 3, t_mid)
        painter.drawText(max(pad_l + pw // 2 + 10, pad_l + pw - 55), h - 3, t_end)


class RAMChartWidget(QWidget if HAS_QT else object):
    """Real-time Canvas/Painter chart for Worker RAM (RSS) vs Host Available RAM over time."""

    def __init__(self, parent=None):
        if not HAS_QT:
            return
        super().__init__(parent)
        self.history: List[Dict[str, Any]] = []
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def update_data(self, history: List[Dict[str, Any]]):
        self.history = history or []
        if HAS_QT:
            self.update()

    def paintEvent(self, event):
        if not HAS_QT:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        painter.fillRect(0, 0, w, h, QColor("#020617"))
        painter.setPen(QPen(QColor("#1e293b"), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(10, 18, "RAM USAGE OVER TIME (MB)")

        wrk_ram = self.history[-1].get("worker_ram", 0) if self.history else 0
        avail_ram = self.history[-1].get("available_ram", 0) if self.history else 0
        txt = f"RSS: {wrk_ram} MB | Avail: {avail_ram} MB"
        painter.setPen(QColor("#a78bfa"))
        painter.drawText(max(10, w - 210), 18, txt)

        pad_l, pad_r, pad_t, pad_b = 40, 10, 26, 18
        pw = max(10, w - pad_l - pad_r)
        ph = max(10, h - pad_t - pad_b)

        max_val = max([pt.get("worker_ram", 0) for pt in self.history] + [1024])
        max_val = max(max_val * 1.3, 2048)

        # Horizontal gridlines
        painter.setPen(QPen(QColor("#1e293b"), 1, Qt.DotLine))
        for pct in (0.33, 0.66):
            y = pad_t + ph * (1.0 - pct)
            painter.drawLine(pad_l, int(y), pad_l + pw, int(y))

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor("#64748b"))
        painter.drawText(4, int(pad_t + 10), f"{int(max_val)}M")
        painter.drawText(10, int(pad_t + ph), "0M")

        if len(self.history) < 2:
            painter.setPen(QColor("#475569"))
            painter.drawText(pad_l + pw // 4, pad_t + ph // 2, "Collecting RAM telemetry (0.8s)...")
            return

        n = len(self.history)
        step = pw / max(1, n - 1)

        wrk_poly = QPolygonF()
        for i, pt in enumerate(self.history):
            val = min(max_val, max(0.0, float(pt.get("worker_ram", 0))))
            x = pad_l + i * step
            y = pad_t + ph * (1.0 - val / max_val)
            wrk_poly.append(QPointF(x, y))

        painter.setPen(QPen(QColor("#a78bfa"), 2.0))
        painter.drawPolyline(wrk_poly)

        # Draw X-axis timestamps
        painter.setFont(QFont("Consolas", 7))
        painter.setPen(QColor("#64748b"))
        t_start = self.history[0].get("timestamp", "")
        t_end = self.history[-1].get("timestamp", "")
        t_mid = self.history[len(self.history) // 2].get("timestamp", "")
        painter.drawText(pad_l, h - 3, t_start)
        if len(self.history) > 4:
            painter.drawText(pad_l + pw // 2 - 25, h - 3, t_mid)
        painter.drawText(max(pad_l + pw // 2 + 10, pad_l + pw - 55), h - 3, t_end)


class NPSChartWidget(QWidget if HAS_QT else object):
    """Real-time Canvas/Painter chart for Nodes Per Second across completed tasks this session."""

    def __init__(self, parent=None):
        if not HAS_QT:
            return
        super().__init__(parent)
        self.history: List[Dict[str, Any]] = []
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def update_data(self, history: List[Dict[str, Any]]):
        self.history = history or []
        if HAS_QT:
            self.update()

    def paintEvent(self, event):
        if not HAS_QT:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        painter.fillRect(0, 0, w, h, QColor("#020617"))
        painter.setPen(QPen(QColor("#1e293b"), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(10, 18, "NPS PER TASK (THIS SESSION)")

        latest_nps = self.history[-1].get("nps", 0) if self.history else 0
        if latest_nps >= 1_000_000:
            txt = f"Latest: {latest_nps / 1_000_000:.2f} M/s"
        elif latest_nps >= 1_000:
            txt = f"Latest: {latest_nps / 1_000:.1f} k/s"
        else:
            txt = f"Latest: {latest_nps:,}/s"
        painter.setPen(QColor("#4ade80"))
        painter.drawText(max(10, w - 180), 18, txt)

        pad_l, pad_r, pad_t, pad_b = 40, 10, 26, 18
        pw = max(10, w - pad_l - pad_r)
        ph = max(10, h - pad_t - pad_b)

        if not self.history:
            painter.setPen(QColor("#475569"))
            painter.drawText(pad_l + pw // 4, pad_t + ph // 2, "No completed tasks this session yet")
            return

        max_nps = max([pt.get("nps", 0) for pt in self.history] + [100_000])
        max_nps = max(max_nps * 1.2, 500_000)

        # Horizontal gridline
        painter.setPen(QPen(QColor("#1e293b"), 1, Qt.DotLine))
        mid_y = pad_t + ph * 0.5
        painter.drawLine(pad_l, int(mid_y), pad_l + pw, int(mid_y))

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor("#64748b"))
        if max_nps >= 1_000_000:
            painter.drawText(4, int(pad_t + 10), f"{max_nps/1_000_000:.1f}M")
        else:
            painter.drawText(4, int(pad_t + 10), f"{int(max_nps/1000)}k")
        painter.drawText(10, int(pad_t + ph), "0")

        n = len(self.history)
        spacing = pw / max(1, n)
        bar_w = max(4.0, min(24.0, spacing - 4.0))

        painter.setFont(QFont("Consolas", 7))
        painter.setPen(QColor("#64748b"))
        for i, pt in enumerate(self.history):
            val = float(pt.get("nps", 0))
            bh = min(ph, (val / max_nps) * ph)
            bx = pad_l + i * spacing + (spacing - bar_w) / 2.0
            by = pad_t + ph - bh
            painter.fillRect(int(bx), int(by), int(bar_w), int(bh), QColor("#38bdf8"))
            ts = pt.get("timestamp", "")
            if ts and (n <= 5 or i == 0 or i == n - 1 or i == n // 2):
                painter.drawText(max(0, int(bx - 12)), h - 3, ts)


# =============================================================================
# MAIN WINDOW IMPLEMENTATION
# =============================================================================

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

        self.setWindowTitle(APP_NAME)
        default_icon = get_default_windows_app_icon()
        if default_icon and not default_icon.isNull():
            self.setWindowIcon(default_icon)
        self.setMinimumSize(700, 480)
        self.resize(1020, 840)

        # Graph timeframe options (3 set dials: 1.5 mins, 5 mins, 10 mins)
        self._timeframe_options = [
            ("1.5 mins", 90),
            ("5 mins", 300),
            ("10 mins", 600),
        ]
        self.graph_timeframe_seconds = 300  # Default: 5 mins dial
        self._last_eta_task_id: Optional[str] = None

        self._apply_dark_style()
        self._init_ui()
        self._setup_timers()
        self._update_cmd_preview()

    def _apply_dark_style(self):
        """Applies a professional dark engineering palette matching fleet console."""
        self.setStyleSheet("""
            QMainWindow, QWidget#centralWidget, QWidget#controlsContainer, QScrollArea, QScrollArea > QWidget {
                background-color: #0b1120;
            }
            QWidget {
                background-color: #0b1120;
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
            QGroupBox QWidget, QGroupBox QLabel, QGroupBox QCheckBox {
                background-color: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                background-color: #0f172a;
            }
            QPushButton {
                background-color: #0369a1;
                color: #ffffff;
                border: 1px solid #38bdf8;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #0284c7;
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
            }
            QPushButton#btnStart {
                background-color: #059669;
                color: #ffffff;
                border: 2px solid #34d399;
                font-size: 12px;
                font-weight: 700;
                min-height: 26px;
                padding: 4px 14px;
                border-radius: 6px;
            }
            QPushButton#btnStart:hover {
                background-color: #047857;
                border-color: #6ee7b7;
            }
            QPushButton#btnStart:pressed {
                background-color: #065f46;
            }
            QPushButton#btnStart:disabled {
                background-color: #334155;
                color: #cbd5e1;
                border: 1px solid #475569;
            }
            QPushButton#btnStop {
                background-color: #dc2626;
                color: #ffffff;
                border: 2px solid #f87171;
                font-size: 12px;
                font-weight: 700;
                min-height: 26px;
                padding: 4px 14px;
                border-radius: 6px;
            }
            QPushButton#btnStop:hover {
                background-color: #b91c1c;
                border-color: #fca5a5;
            }
            QPushButton#btnStop:pressed {
                background-color: #991b1b;
            }
            QPushButton#btnStop:disabled {
                background-color: #334155;
                color: #cbd5e1;
                border: 1px solid #475569;
            }
            QPushButton#btnLocalStop {
                background-color: #d97706;
                color: #ffffff;
                border: 2px solid #fbbf24;
                font-size: 12px;
                font-weight: 700;
                min-height: 26px;
                padding: 4px 14px;
                border-radius: 6px;
            }
            QPushButton#btnLocalStop:hover {
                background-color: #b45309;
                border-color: #fde68a;
            }
            QPushButton#btnLocalStop:pressed {
                background-color: #92400e;
            }
            QPushButton#btnLocalStop:disabled {
                background-color: #334155;
                color: #cbd5e1;
                border: 1px solid #475569;
            }
            QSlider::groove:horizontal {
                border: 1px solid #334155;
                height: 6px;
                background: #0f172a;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #0284c7;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #38bdf8;
                border: 2px solid #f8fafc;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 9px;
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
        main_widget.setObjectName("centralWidget")
        main_widget.setStyleSheet("QWidget#centralWidget { background-color: #0b1120; }")
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)

        # Upper pane: Scrollable controls container
        scroll_controls = QScrollArea()
        scroll_controls.setObjectName("scrollControls")
        scroll_controls.setWidgetResizable(True)
        scroll_controls.setFrameShape(QFrame.NoFrame)
        scroll_controls.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_controls.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_controls.setMinimumHeight(120)
        scroll_controls.setStyleSheet("QScrollArea#scrollControls { background-color: #0b1120; border: none; }")
        if scroll_controls.viewport():
            scroll_controls.viewport().setStyleSheet("background-color: #0b1120; border: none;")

        controls_container = QWidget()
        controls_container.setObjectName("controlsContainer")
        controls_container.setStyleSheet("QWidget#controlsContainer { background-color: #0b1120; color: #e2e8f0; }")
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(4, 4, 4, 4)
        controls_layout.setSpacing(10)

        # Header bar
        header = QHBoxLayout()
        title_label = QLabel("BACKGROUND PROCESSING UTILITY")
        title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc; letter-spacing: 0.5px;")
        header.addWidget(title_label)

        self.lbl_server_status = QLabel("Server: Fixed & Built-in (https://belzedar.duckdns.org)")
        self.lbl_server_status.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 11px;")
        header.addStretch()
        header.addWidget(self.lbl_server_status)
        controls_layout.addLayout(header)

        # Telemetry & Resource Monitor Box
        res_box = QGroupBox("HOST HARDWARE & REAL-TIME TELEMETRY (0.8s REFRESH)")
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

        # Upstream parameters
        cfg_box = QGroupBox("OPENBENCH CONTRIBUTOR API PARAMETERS (UPSTREAM VARIABLES)")
        cfg_layout = QVBoxLayout(cfg_box)

        grid_top = QGridLayout()
        grid_top.addWidget(QLabel("Custom Engine (--engine):"), 0, 0)
        self.txt_engine = QLineEdit()
        self.txt_engine.setPlaceholderText("Optional path to custom engine binary (blank = default bundled engine)")
        self.txt_engine.setText(self.config.get("openbench", "engine_path", default=""))
        self.txt_engine.textChanged.connect(self._update_cmd_preview)
        grid_top.addWidget(self.txt_engine, 0, 1)

        grid_top.addWidget(QLabel("Syzygy TBs (--syzygy):"), 1, 0)
        self.txt_syzygy = QLineEdit()
        self.txt_syzygy.setPlaceholderText("Directories separated by ; (blank = auto-manage on USB)")
        self.txt_syzygy.setText(self.config.get("openbench", "syzygy_path", default=""))
        self.txt_syzygy.textChanged.connect(self._update_cmd_preview)
        grid_top.addWidget(self.txt_syzygy, 1, 1)
        cfg_layout.addLayout(grid_top)

        grid_num = QHBoxLayout()
        grid_num.addWidget(QLabel("CPU Mode:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Adaptive", "Balanced", "Maximum", "Custom"])
        current_mode = self.config.get("resources", "cpu_mode", default="Adaptive")
        self.combo_mode.setCurrentText(current_mode)
        self.combo_mode.currentTextChanged.connect(self._on_mode_changed)
        grid_num.addWidget(self.combo_mode)

        grid_num.addWidget(QLabel("Threads (-T):"))
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, self.resource_mgr.logical_cores)
        self.spin_threads.setValue(self.config.get("resources", "threads", default=4))
        self.spin_threads.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(self.spin_threads)

        grid_num.addWidget(QLabel("Jobs (--jobs):"))
        self.spin_jobs = QSpinBox()
        self.spin_jobs.setRange(1, 64)
        self.spin_jobs.setValue(self.config.get("openbench", "jobs", default=1))
        self.spin_jobs.setToolTip("Number of concurrent analyses to run, splitting -T threads")
        self.spin_jobs.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(self.spin_jobs)

        grid_num.addWidget(QLabel("Hash MB (--hash):"))
        self.spin_hash = QSpinBox()
        self.spin_hash.setRange(64, 65536)
        self.spin_hash.setSingleStep(128)
        self.spin_hash.setValue(self.config.get("resources", "hash_mb", default=1024))
        self.spin_hash.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(self.spin_hash)

        grid_num.addWidget(QLabel("Engine Check Min (--engine-update-minutes):"))
        self.spin_engine_update_min = QDoubleSpinBox()
        self.spin_engine_update_min.setRange(0.5, 1440.0)
        self.spin_engine_update_min.setSingleStep(5.0)
        self.spin_engine_update_min.setValue(float(self.config.get("openbench", "engine_update_minutes", default=15.0)))
        self.spin_engine_update_min.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(self.spin_engine_update_min)
        cfg_layout.addLayout(grid_num)

        chk_layout = QHBoxLayout()
        self.chk_no_fetch_syzygy = QCheckBox("Disable Tablebases (--no-fetch-syzygy)")
        self.chk_no_fetch_syzygy.setToolTip("Checked: skip Syzygy tablebases (saves disk/bandwidth)\nUnchecked: auto-manage tablebases on USB")
        self.chk_no_fetch_syzygy.setChecked(self.config.get("openbench", "no_fetch_syzygy", default=True))
        self.chk_no_fetch_syzygy.toggled.connect(self._update_cmd_preview)
        chk_layout.addWidget(self.chk_no_fetch_syzygy)

        self.chk_solve = QCheckBox("Solve Tasks (--solve)")
        self.chk_solve.setToolTip("Serve exhaustive proof solve tasks")
        self.chk_solve.setChecked(self.config.get("openbench", "solve", default=False))
        self.chk_solve.toggled.connect(self._update_cmd_preview)
        chk_layout.addWidget(self.chk_solve)

        self.chk_no_auto_update = QCheckBox("No Worker Update (--no-auto-update)")
        self.chk_no_auto_update.setChecked(self.config.get("openbench", "no_auto_update", default=False))
        self.chk_no_auto_update.toggled.connect(self._update_cmd_preview)
        chk_layout.addWidget(self.chk_no_auto_update)

        self.chk_no_engine_update = QCheckBox("No Engine Update (--no-engine-update)")
        self.chk_no_engine_update.setChecked(self.config.get("openbench", "no_engine_update", default=False))
        self.chk_no_engine_update.toggled.connect(self._update_cmd_preview)
        chk_layout.addWidget(self.chk_no_engine_update)

        self.chk_once = QCheckBox("Run Once (--once)")
        self.chk_once.setChecked(self.config.get("openbench", "once", default=False))
        self.chk_once.toggled.connect(self._update_cmd_preview)
        chk_layout.addWidget(self.chk_once)
        cfg_layout.addLayout(chk_layout)

        cmd_preview_row = QHBoxLayout()
        cmd_preview_row.addWidget(QLabel("Command Preview:"))
        self.lbl_cmd_preview = QLabel("python atomicdb_worker.py ...")
        self.lbl_cmd_preview.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 11px;")
        cmd_preview_row.addWidget(self.lbl_cmd_preview)
        cmd_preview_row.addStretch()
        cfg_layout.addLayout(cmd_preview_row)

        controls_layout.addWidget(cfg_box)

        # Primary Control Bar
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(10)

        self.btn_start = QPushButton("Start")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.setMinimumHeight(30)
        self.btn_start.setMaximumHeight(30)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton#btnStart {
                background-color: #059669;
                color: #ffffff;
                border: 2px solid #34d399;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 700;
                padding: 4px 14px;
            }
            QPushButton#btnStart:hover { background-color: #047857; border-color: #6ee7b7; }
            QPushButton#btnStart:pressed { background-color: #065f46; }
            QPushButton#btnStart:disabled { background-color: #334155; color: #cbd5e1; border: 1px solid #475569; }
        """)
        self.btn_start.clicked.connect(self._start_worker)
        ctrl_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop After Finishing Current Task")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setMinimumHeight(30)
        self.btn_stop.setMaximumHeight(30)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setStyleSheet("""
            QPushButton#btnStop {
                background-color: #dc2626;
                color: #ffffff;
                border: 2px solid #f87171;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 700;
                padding: 4px 14px;
            }
            QPushButton#btnStop:hover { background-color: #b91c1c; border-color: #fca5a5; }
            QPushButton#btnStop:pressed { background-color: #991b1b; }
            QPushButton#btnStop:disabled { background-color: #334155; color: #cbd5e1; border: 1px solid #475569; }
        """)
        self.btn_stop.clicked.connect(self._stop_after_current_task)
        self.btn_stop.setEnabled(False)
        ctrl_layout.addWidget(self.btn_stop)

        self.btn_local_stop = QPushButton("Save and Stop")
        self.btn_local_stop.setObjectName("btnLocalStop")
        self.btn_local_stop.setMinimumHeight(30)
        self.btn_local_stop.setMaximumHeight(30)
        self.btn_local_stop.setCursor(Qt.PointingHandCursor)
        self.btn_local_stop.setStyleSheet("""
            QPushButton#btnLocalStop {
                background-color: #d97706;
                color: #ffffff;
                border: 2px solid #fbbf24;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 700;
                padding: 4px 14px;
            }
            QPushButton#btnLocalStop:hover { background-color: #b45309; border-color: #fde68a; }
            QPushButton#btnLocalStop:pressed { background-color: #92400e; }
            QPushButton#btnLocalStop:disabled { background-color: #334155; color: #cbd5e1; border: 1px solid #475569; }
        """)
        self.btn_local_stop.setCheckable(False)
        self.btn_local_stop.clicked.connect(self._save_and_stop)
        ctrl_layout.addWidget(self.btn_local_stop)

        controls_layout.addLayout(ctrl_layout)
        scroll_controls.setWidget(controls_container)
        self.main_splitter.addWidget(scroll_controls)

        # Multi-tab view: 1. Live Analysis Console, 2. Local USB Diagnostic Dashboard & Graphs
        self.tab_widget = QTabWidget()
        self.tab_widget.setMinimumHeight(120)
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
        self.console.setMinimumHeight(90)
        self.console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tab_console_layout.addWidget(self.console)

        console_bar = QHBoxLayout()
        btn_clear_console = QPushButton("Clear Console Screen")
        btn_clear_console.setStyleSheet("background-color: #1e293b; color: #e2e8f0; border: 1px solid #475569; font-size: 11px; padding: 4px 10px;")
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

        # Tab 2: Diagnostic Data Dashboard & Real-Time Graphs
        tab_analytics_scroll = QScrollArea()
        tab_analytics_scroll.setObjectName("scrollAnalytics")
        tab_analytics_scroll.setWidgetResizable(True)
        tab_analytics_scroll.setFrameShape(QFrame.NoFrame)
        tab_analytics_scroll.setStyleSheet("QScrollArea#scrollAnalytics { background-color: #0b1120; border: none; }")
        if tab_analytics_scroll.viewport():
            tab_analytics_scroll.viewport().setStyleSheet("background-color: #0b1120; border: none;")

        tab_analytics_content = QWidget()
        tab_analytics_layout = QVBoxLayout(tab_analytics_content)
        tab_analytics_layout.setContentsMargins(8, 8, 8, 8)
        tab_analytics_layout.setSpacing(10)

        def make_card(title: str, widget: QLabel, subtext: str = ""):
            box = QWidget()
            layout = QVBoxLayout(box)
            layout.setContentsMargins(4, 4, 4, 4)
            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("color: #94a3b8; font-size: 10px; text-transform: uppercase; font-weight: 600;")
            layout.addWidget(lbl_t)
            layout.addWidget(widget)
            if subtext:
                lbl_sub = QLabel(subtext)
                lbl_sub.setStyleSheet("color: #64748b; font-size: 10px;")
                layout.addWidget(lbl_sub)
            return box

        # =========================================================================
        # 1. CURRENT TASK (REAL-TIME EXECUTION & ESTIMATED COMPLETION)
        # =========================================================================
        grp_cur = QGroupBox("CURRENT TASK (REAL-TIME EXECUTION & ESTIMATED COMPLETION)")
        grp_cur_layout = QVBoxLayout(grp_cur)

        cur_kpi_layout = QGridLayout()
        self.lbl_cur_task_id = QLabel("IDLE")
        self.lbl_cur_task_id.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8; font-family: monospace;")
        self.lbl_cur_task_nodes = QLabel("-")
        self.lbl_cur_task_nodes.setStyleSheet("font-size: 18px; font-weight: bold; color: #4ade80;")
        self.lbl_cur_task_eta = QLabel("Calculating...")
        self.lbl_cur_task_eta.setStyleSheet("font-size: 18px; font-weight: bold; color: #fbbf24;")
        self.lbl_cur_nps = QLabel("0 /s")
        self.lbl_cur_nps.setStyleSheet("font-size: 18px; font-weight: bold; color: #a78bfa;")

        cur_kpi_layout.addWidget(make_card("Task ID", self.lbl_cur_task_id, "Active worker slot"), 0, 0)
        cur_kpi_layout.addWidget(make_card("Nodes in Task", self.lbl_cur_task_nodes, "Target search budget"), 0, 1)
        cur_kpi_layout.addWidget(make_card("Est. Time Remaining", self.lbl_cur_task_eta, "Based on avg NPS of last 3 tasks"), 0, 2)
        cur_kpi_layout.addWidget(make_card("Current NPS", self.lbl_cur_nps, "Live engine speed"), 0, 3)
        grp_cur_layout.addLayout(cur_kpi_layout)

        # Calculating Line (Monospace display)
        line_box = QHBoxLayout()
        line_box.addWidget(QLabel("Calculating Line:"))
        self.lbl_cur_line = QLabel("Idle (waiting for next task from server)")
        self.lbl_cur_line.setStyleSheet(
            "background-color: #020617; color: #38bdf8; border: 1px solid #1e293b; "
            "padding: 6px 10px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 11px;"
        )
        self.lbl_cur_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        line_box.addWidget(self.lbl_cur_line)
        grp_cur_layout.addLayout(line_box)

        lbl_cur_hint = QLabel("Saved automatically to /logs/current_task.log and /logs/activity.log on this USB drive")
        lbl_cur_hint.setStyleSheet("color: #64748b; font-size: 10px;")
        grp_cur_layout.addWidget(lbl_cur_hint)
        tab_analytics_layout.addWidget(grp_cur)

        # =========================================================================
        # 2. SESSION STATISTICS (THIS SESSION)
        # =========================================================================
        grp_session = QGroupBox("SESSION STATISTICS (SAVED TO /logs/session_statistics.log)")
        grp_session_layout = QVBoxLayout(grp_session)
        session_kpi_layout = QGridLayout()

        self.lbl_session_tasks = QLabel("0")
        self.lbl_session_tasks.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        self.lbl_session_nodes = QLabel("0")
        self.lbl_session_nodes.setStyleSheet("font-size: 18px; font-weight: bold; color: #4ade80;")
        self.lbl_session_nps = QLabel("0 /s")
        self.lbl_session_nps.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        self.lbl_session_avg_nps = QLabel("0 /s")
        self.lbl_session_avg_nps.setStyleSheet("font-size: 18px; font-weight: bold; color: #a78bfa;")
        self.lbl_session_uptime = QLabel("00:00:00")
        self.lbl_session_uptime.setStyleSheet("font-size: 18px; font-weight: bold; color: #f472b6; font-family: monospace;")

        session_kpi_layout.addWidget(make_card("Tasks This Session", self.lbl_session_tasks), 0, 0)
        session_kpi_layout.addWidget(make_card("Total Nodes This Session", self.lbl_session_nodes), 0, 1)
        session_kpi_layout.addWidget(make_card("Current NPS", self.lbl_session_nps), 0, 2)
        session_kpi_layout.addWidget(make_card("Average NPS This Session", self.lbl_session_avg_nps), 0, 3)
        session_kpi_layout.addWidget(make_card("Session Uptime", self.lbl_session_uptime), 0, 4)
        grp_session_layout.addLayout(session_kpi_layout)
        tab_analytics_layout.addWidget(grp_session)

        # =========================================================================
        # 3. LIFETIME STATISTICS (PERMANENT USB REPORT — NEVER CLEARED)
        # =========================================================================
        grp_lt = QGroupBox("LIFETIME STATISTICS (SAVED TO /logs/lifetime_statistics.txt — PERMANENTLY PRESERVED)")
        grp_lt_layout = QVBoxLayout(grp_lt)
        lt_kpi_layout = QGridLayout()

        self.lbl_lt_tasks = QLabel("0")
        self.lbl_lt_tasks.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        self.lbl_lt_nodes = QLabel("0")
        self.lbl_lt_nodes.setStyleSheet("font-size: 18px; font-weight: bold; color: #4ade80;")
        self.lbl_lt_avg_nps = QLabel("0 /s")
        self.lbl_lt_avg_nps.setStyleSheet("font-size: 18px; font-weight: bold; color: #fbbf24;")
        self.lbl_lt_runtime = QLabel("0s")
        self.lbl_lt_runtime.setStyleSheet("font-size: 18px; font-weight: bold; color: #a78bfa;")
        self.lbl_lt_cpu_hours = QLabel("0.00 hrs")
        self.lbl_lt_cpu_hours.setStyleSheet("font-size: 18px; font-weight: bold; color: #f472b6;")
        self.lbl_lt_sessions = QLabel("1")
        self.lbl_lt_sessions.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")

        lt_kpi_layout.addWidget(make_card("Total Tasks Completed", self.lbl_lt_tasks), 0, 0)
        lt_kpi_layout.addWidget(make_card("Total Lifetime Nodes", self.lbl_lt_nodes), 0, 1)
        lt_kpi_layout.addWidget(make_card("Lifetime Average NPS", self.lbl_lt_avg_nps), 0, 2)
        lt_kpi_layout.addWidget(make_card("Total Accumulated Runtime", self.lbl_lt_runtime), 0, 3)
        lt_kpi_layout.addWidget(make_card("Total CPU Hours", self.lbl_lt_cpu_hours), 0, 4)
        lt_kpi_layout.addWidget(make_card("Total Number of Sessions", self.lbl_lt_sessions), 0, 5)
        grp_lt_layout.addLayout(lt_kpi_layout)

        lbl_lt_hint = QLabel("Lifetime statistics are recorded permanently on this USB thumb drive and are strictly preserved across sessions.")
        lbl_lt_hint.setStyleSheet("color: #64748b; font-size: 10px;")
        grp_lt_layout.addWidget(lbl_lt_hint)
        tab_analytics_layout.addWidget(grp_lt)

        # =========================================================================
        # 4. GRAPHS (THIS SESSION — 0.8s TELEMETRY + TIMEFRAME SLIDER)
        # =========================================================================
        grp_graphs = QGroupBox("REAL-TIME SESSION GRAPHS (0.8s HARDWARE REFRESH)")
        grp_graphs_outer = QVBoxLayout(grp_graphs)
        grp_graphs_outer.setSpacing(8)

        # Timeframe slider bar with set dials at 1.5 mins, 5 mins, and 10 mins
        tf_bar = QHBoxLayout()
        tf_bar.setSpacing(8)
        lbl_tf_title = QLabel("Graph Timeframe:")
        lbl_tf_title.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 11px;")
        tf_bar.addWidget(lbl_tf_title)

        self.slider_timeframe = QSlider(Qt.Horizontal)
        self.slider_timeframe.setObjectName("sliderTimeframe")
        self.slider_timeframe.setRange(0, len(self._timeframe_options) - 1)
        self.slider_timeframe.setSingleStep(1)
        self.slider_timeframe.setPageStep(1)
        self.slider_timeframe.setTickInterval(1)
        self.slider_timeframe.setTickPosition(QSlider.TicksBelow)
        self.slider_timeframe.setFixedWidth(160)
        self.slider_timeframe.setValue(1)  # 5 mins default
        self.slider_timeframe.valueChanged.connect(self._on_timeframe_slider_changed)
        tf_bar.addWidget(self.slider_timeframe)

        self._tf_dial_buttons: List[QPushButton] = []
        for idx, (label_txt, _secs) in enumerate(self._timeframe_options):
            dial_btn = QPushButton(label_txt)
            dial_btn.setCursor(Qt.PointingHandCursor)
            dial_btn.clicked.connect(lambda _checked=False, i=idx: self.slider_timeframe.setValue(i))
            self._tf_dial_buttons.append(dial_btn)
            tf_bar.addWidget(dial_btn)

        tf_bar.addStretch()
        self.lbl_graph_timeframe = QLabel("Window: 5 mins")
        self.lbl_graph_timeframe.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 11px; font-weight: 600;")
        tf_bar.addWidget(self.lbl_graph_timeframe)
        self._update_timeframe_dial_styles(1)

        grp_graphs_outer.addLayout(tf_bar)

        grp_graphs_layout = QHBoxLayout()
        grp_graphs_layout.setSpacing(8)

        self.chart_cpu = CPUChartWidget()
        self.chart_ram = RAMChartWidget()
        self.chart_nps = NPSChartWidget()

        grp_graphs_layout.addWidget(self.chart_cpu)
        grp_graphs_layout.addWidget(self.chart_ram)
        grp_graphs_layout.addWidget(self.chart_nps)
        grp_graphs_outer.addLayout(grp_graphs_layout)
        tab_analytics_layout.addWidget(grp_graphs)

        # =========================================================================
        # 5. PERSISTENT TASK EXECUTION HISTORY
        # =========================================================================
        table_group = QGroupBox("PERSISTENT TASK EXECUTION HISTORY (Saved to USB /logs/history.json)")
        table_layout = QVBoxLayout(table_group)

        self.table_tasks = QTableWidget()
        self.table_tasks.setColumnCount(7)
        self.table_tasks.setHorizontalHeaderLabels(["Timestamp", "Task ID", "Type", "Nodes", "NPS", "TB WDL/DTZ", "Result / Score"])
        self.table_tasks.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_tasks.setAlternatingRowColors(True)
        self.table_tasks.setMinimumHeight(120)
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

        storage_bar = QHBoxLayout()
        logs_path = os.path.join(self.config.base_dir, "logs")
        self.lbl_storage_info = QLabel(f"USB Storage: {logs_path} (lifetime_statistics.txt, session_statistics.log, current_task.log, history.json)")
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

        tab_analytics_scroll.setWidget(tab_analytics_content)
        self.tab_widget.addTab(tab_analytics_scroll, "USB Diagnostic Dashboard & Graphs")
        self.main_splitter.addWidget(self.tab_widget)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([380, 460])
        main_layout.addWidget(self.main_splitter)

        if self.analytics_logger:
            self._update_analytics_ui(self.analytics_logger.get_summary())

        self.signals.log_received.connect(self._append_log)

    def _update_cmd_preview(self):
        """Generates real-time preview of the exact invocation command."""
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

    def _save_ui_settings(self):
        """Persists current UI configuration inputs to config/settings.json."""
        self.config.set("resources", "cpu_mode", self.combo_mode.currentText())
        self.config.set("resources", "threads", self.spin_threads.value())
        self.config.set("resources", "hash_mb", self.spin_hash.value())
        self.config.set("openbench", "jobs", self.spin_jobs.value())
        self.config.set("openbench", "engine_path", self.txt_engine.text().strip())
        self.config.set("openbench", "syzygy_path", self.txt_syzygy.text().strip())
        self.config.set("openbench", "no_fetch_syzygy", self.chk_no_fetch_syzygy.isChecked())
        self.config.set("openbench", "solve", self.chk_solve.isChecked())
        self.config.set("openbench", "no_auto_update", self.chk_no_auto_update.isChecked())
        self.config.set("openbench", "no_engine_update", self.chk_no_engine_update.isChecked())
        self.config.set("openbench", "engine_update_minutes", self.spin_engine_update_min.value())
        self.config.set("openbench", "once", self.chk_once.isChecked())
        self.config.save()

    def _on_mode_changed(self, mode: str):
        self.config.set("resources", "cpu_mode", mode)
        self.resource_mgr.mode = mode
        threads, hash_mb = self.resource_mgr.compute_allocation(mode)
        self.spin_threads.setValue(threads)
        self.spin_hash.setValue(hash_mb)
        if self.analytics_logger:
            self.analytics_logger.set_active_threads(threads)
        self._append_log(f"[CONFIG] Switched CPU mode to {mode}. Recommended: {threads} threads, {hash_mb}MB hash.")
        self._update_cmd_preview()

    def _setup_timers(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_tick)
        self.timer.start(800)  # High-frequency hardware telemetry refresh every 0.8 seconds

        self.eta_timer = QTimer(self)
        self.eta_timer.setTimerType(Qt.PreciseTimer)
        self.eta_timer.timeout.connect(self._refresh_eta_1s)
        self.eta_timer.start(1000)  # Exact 1-second refresh for ETA countdown & session uptime

    def _refresh_eta_1s(self):
        """Refreshes ETA every 1s, freezes when paused, and resets when worker is stopped/reset."""
        if not self.analytics_logger:
            return
        self.lbl_session_uptime.setText(self.analytics_logger.get_session_uptime_str())

        # If worker stopped cleanly or died unexpectedly, ensure active task ETA resets
        if self.analytics_logger.current_task_id and not self.worker_mgr.is_running and not self.analytics_logger.is_worker_paused:
            self.analytics_logger.reset_current_task()

        if self.analytics_logger.current_task_id:
            eta = self.analytics_logger.calculate_estimated_time_remaining()
            self.analytics_logger.current_task_eta_seconds = eta
            eta_str = self.analytics_logger.format_eta_str(eta)
            self.lbl_cur_task_eta.setText(eta_str)
            if eta is not None and eta < 0:
                self.lbl_cur_task_eta.setStyleSheet("font-size: 18px; font-weight: bold; color: #fb7185; font-family: monospace;")
            else:
                self.lbl_cur_task_eta.setStyleSheet("font-size: 18px; font-weight: bold; color: #fbbf24; font-family: monospace;")
        else:
            self.lbl_cur_task_eta.setText("-")
            self.lbl_cur_task_eta.setStyleSheet("font-size: 18px; font-weight: bold; color: #fbbf24;")

    def _poll_tick(self):
        snapshot = self.resource_mgr.get_system_snapshot(self.worker_mgr.current_pid)
        sys_cpu = snapshot["system_cpu_pct"]
        worker_cpu = snapshot["worker_cpu_pct"]
        worker_ram = snapshot["worker_ram_mb"]
        avail_ram = snapshot["available_ram_mb"]

        self.bar_sys_cpu.setValue(int(sys_cpu))
        self.bar_worker_cpu.setValue(int(worker_cpu))
        self.lbl_ram_details.setText(f"Worker RSS: {worker_ram} MB | Host Avail: {avail_ram} MB")

        # Feed real-time hardware sample to analytics_logger for session graphs (0.8s cadence)
        if self.analytics_logger:
            self.analytics_logger.set_active_threads(self.spin_threads.value())
            self.analytics_logger.record_hardware_sample(
                sys_cpu=sys_cpu,
                worker_cpu=worker_cpu,
                worker_ram_mb=worker_ram,
                available_ram_mb=avail_ram
            )
            self._update_graph_views()

        # Check adaptive hysteresis (evaluates every 20 seconds internally)
        allocation_changed = self.resource_mgr.update_adaptive_state(sys_cpu)
        if allocation_changed and self.worker_mgr.is_running:
            self._append_log("[ADAPTIVE] System load threshold triggered. Adjusting worker parameters gracefully...")

        # Auto-restore buttons when worker finishes or stops
        if not self.worker_mgr.is_running and (self.btn_stop.isEnabled() or not self.btn_start.isEnabled()):
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("Stop After Finishing Current Task")
            self._refresh_eta_1s()

    def _start_worker(self):
        self.config.set("safety", "local_stop_active", False)
        user, pwd = self.config.get_account_credentials()
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

        if self.analytics_logger:
            self.analytics_logger.set_active_threads(threads)
            self.analytics_logger.reset_current_task()

        self.btn_stop.setText("Stop After Finishing Current Task")
        started = self.worker_mgr.start_worker(
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
        self.btn_start.setEnabled(not started)
        self.btn_stop.setEnabled(bool(started))
        self._refresh_eta_1s()

    def _stop_after_current_task(self):
        """Stops the worker cleanly right after completing and submitting the current task."""
        if self.worker_mgr.request_stop_after_current_task():
            self.btn_stop.setText("Stopping After Current Task...")
            self.btn_stop.setEnabled(False)
        else:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("Stop After Finishing Current Task")

    def _save_and_stop(self):
        """Saves configuration, analytics, and lifetime logs to disk, then stops the worker."""
        self._save_ui_settings()
        if self.analytics_logger:
            self.analytics_logger.log_session_event("Save and Stop triggered by user")
            self.analytics_logger.save_persisted_data()
            self.analytics_logger.write_lifetime_statistics_txt()
            self.analytics_logger.reset_current_task()
        self.worker_mgr.stop_worker()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setText("Stop After Finishing Current Task")
        self._refresh_eta_1s()
        self._append_log("[SAVE & STOP] Configuration and statistics saved to portable drive; worker stopped.")

    def _stop_worker(self):
        self.worker_mgr.stop_worker()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setText("Stop After Finishing Current Task")
        self._refresh_eta_1s()

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

    def _update_timeframe_dial_styles(self, active_idx: int):
        """Highlights the active timeframe dial button (1.5 mins, 5 mins, 10 mins)."""
        for idx, btn in enumerate(getattr(self, "_tf_dial_buttons", [])):
            if idx == active_idx:
                btn.setStyleSheet(
                    "background-color: #0284c7; color: #ffffff; border: 1px solid #38bdf8; "
                    "border-radius: 4px; font-size: 11px; font-weight: 700; padding: 3px 10px;"
                )
            else:
                btn.setStyleSheet(
                    "background-color: #1e293b; color: #cbd5e1; border: 1px solid #475569; "
                    "border-radius: 4px; font-size: 11px; font-weight: 600; padding: 3px 10px;"
                )

    def _on_timeframe_slider_changed(self, idx: int):
        """Handles timeframe slider dial switches across 1.5 mins, 5 mins, and 10 mins."""
        idx = max(0, min(len(self._timeframe_options) - 1, int(idx)))
        label_txt, secs = self._timeframe_options[idx]
        self.graph_timeframe_seconds = secs
        if hasattr(self, "lbl_graph_timeframe"):
            self.lbl_graph_timeframe.setText(f"Window: {label_txt}")
        self._update_timeframe_dial_styles(idx)
        self._update_graph_views()

    def _update_graph_views(self, summary: Optional[dict] = None):
        """Updates CPU, RAM, and NPS charts filtered by the active graph timeframe dial."""
        now = time.time()
        window = getattr(self, "graph_timeframe_seconds", 300)
        if summary is not None:
            cpu_src = summary.get("cpu_history", [])
            ram_src = summary.get("ram_history", [])
            nps_src = summary.get("nps_task_history", [])
        elif self.analytics_logger:
            cpu_src = self.analytics_logger.cpu_history
            ram_src = self.analytics_logger.ram_history
            nps_src = self.analytics_logger.nps_task_history
        else:
            cpu_src, ram_src, nps_src = [], [], []

        self.chart_cpu.update_data(AnalyticsLogger.filter_history_by_timeframe(cpu_src, window, now))
        self.chart_ram.update_data(AnalyticsLogger.filter_history_by_timeframe(ram_src, window, now))
        self.chart_nps.update_data(AnalyticsLogger.filter_history_by_timeframe(nps_src, window, now))

    def _format_nodes(self, n: int) -> str:
        return format_nodes_compact(n)

    def _format_nps(self, n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.2f} M/s"
        elif n >= 1_000:
            return f"{n / 1_000:.1f} k/s"
        return f"{n:,} /s"

    def _update_analytics_ui(self, summary: dict):
        """Updates all dashboard sections (Current Task, Session, Lifetime, and Graphs)."""
        try:
            # 1. CURRENT TASK
            cur_id = summary.get("current_task_id")
            if cur_id != self._last_eta_task_id:
                self._last_eta_task_id = cur_id
                if cur_id and hasattr(self, "eta_timer"):
                    self.eta_timer.start(1000)  # Align 1s countdown phase cleanly to new task start
            if cur_id:
                self.lbl_cur_task_id.setText(str(cur_id))
                self.lbl_cur_task_nodes.setText(self._format_nodes(summary.get('current_task_nodes', 0)))
                eta_val = summary.get("current_task_eta_seconds")
                self.lbl_cur_task_eta.setText(summary.get("current_task_eta_str", "Calculating..."))
                if eta_val is not None and eta_val < 0:
                    self.lbl_cur_task_eta.setStyleSheet("font-size: 18px; font-weight: bold; color: #fb7185; font-family: monospace;")
                else:
                    self.lbl_cur_task_eta.setStyleSheet("font-size: 18px; font-weight: bold; color: #fbbf24; font-family: monospace;")
                self.lbl_cur_nps.setText(self._format_nps(summary.get("current_nps", 0)))
                self.lbl_cur_line.setText(summary.get("current_task_line", "Processing search moves..."))
            else:
                self.lbl_cur_task_id.setText("IDLE")
                self.lbl_cur_task_nodes.setText("-")
                self.lbl_cur_task_eta.setText("-")
                self.lbl_cur_task_eta.setStyleSheet("font-size: 18px; font-weight: bold; color: #fbbf24;")
                self.lbl_cur_nps.setText("0 /s")
                self.lbl_cur_line.setText("Idle (waiting for next task from server)")

            # 2. SESSION STATISTICS
            self.lbl_session_tasks.setText(f"{summary.get('session_tasks_completed', 0):,}")
            self.lbl_session_nodes.setText(self._format_nodes(summary.get("session_total_nodes", 0)))
            self.lbl_session_nps.setText(self._format_nps(summary.get("current_nps", 0)))
            self.lbl_session_avg_nps.setText(self._format_nps(summary.get("session_average_nps", 0)))
            self.lbl_session_uptime.setText(summary.get("session_uptime_str", "00:00:00"))

            # 3. LIFETIME STATISTICS
            self.lbl_lt_tasks.setText(f"{summary.get('lifetime_tasks_completed', 0):,}")
            self.lbl_lt_nodes.setText(self._format_nodes(summary.get("lifetime_total_nodes", 0)))
            self.lbl_lt_avg_nps.setText(self._format_nps(summary.get("lifetime_average_nps", 0)))
            self.lbl_lt_runtime.setText(summary.get("lifetime_total_runtime_str", "0s"))
            ch = summary.get('lifetime_cpu_hours', 0.0)
            self.lbl_lt_cpu_hours.setText(f"{ch:.4f} hrs" if (0 < ch < 0.1) else f"{ch:.2f} hrs")
            self.lbl_lt_sessions.setText(f"{summary.get('lifetime_total_sessions', 1):,}")

            # 4. GRAPHS (THIS SESSION, filtered by active timeframe slider)
            self._update_graph_views(summary)

            # 5. RECENT TASKS TABLE
            recent = summary.get("recent_tasks", [])
            self.table_tasks.setRowCount(len(recent))
            for row_idx, task in enumerate(recent):
                ts = task.get("timestamp", "")
                if " " in ts:
                    ts = ts.split(" ")[1]
                task_id = str(task.get("task_id", ""))
                task_type = str(task.get("type", "engine")).upper()
                nodes = self._format_nodes(task.get('nodes', 0))
                nps = f"{task.get('nps', 0):,}"
                tb_info = "-"
                if task.get("wdl") is not None or task.get("tb_wdl") is not None:
                    w = task.get("wdl") if task.get("wdl") is not None else task.get("tb_wdl")
                    tb_info = f"wdl={w}"
                    d = task.get("dtz") if task.get("dtz") is not None else task.get("tb_dtz")
                    if d is not None:
                        tb_info += f" dtz={d}"
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
