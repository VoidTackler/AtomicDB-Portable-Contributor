"""
AtomicDB Portable - PySide6 Native Windows GUI Application
Provides API configuration, live console, and real-time analytics/graphs.
"""

import os
import sys
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


try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLayout, QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
        QCheckBox, QProgressBar, QTextEdit, QGroupBox, QLineEdit, QTabWidget,
        QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
        QSizePolicy, QSlider, QStyle,
    )
    from PySide6.QtCore import Qt, QTimer, Signal, QObject, QPoint, QPointF, QRect, QSize
    from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPen, QPolygonF, QImage, QPixmap
    HAS_QT = True
except ImportError:
    HAS_QT = False


def get_default_windows_app_icon():
    """Returns the default Windows application icon: IDI_APPLICATION = MAKEINTRESOURCE(32512)."""
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
    from .analytics_logger import AnalyticsLogger, format_nodes_compact, format_nph
except (ImportError, ValueError):
    from configuration import PortableConfig
    from resource_manager import ResourceManager
    from worker_manager import WorkerManager
    from engine_manager import EngineManager
    from analytics_logger import AnalyticsLogger, format_nodes_compact, format_nph


class WorkerSignals(QObject if HAS_QT else object):
    if HAS_QT:
        log_received = Signal(str)
        analytics_updated = Signal(dict)


def _action_btn_qss(obj_name: str, bg: str, border: str, hover_bg: str, hover_border: str, pressed_bg: str) -> str:
    return (
        f"QPushButton#{obj_name} {{ background-color: {bg}; color: #ffffff; border: 2px solid {border}; "
        f"border-radius: 6px; font-size: 12px; font-weight: 700; padding: 4px 14px; }}\n"
        f"QPushButton#{obj_name}:hover {{ background-color: {hover_bg}; border-color: {hover_border}; }}\n"
        f"QPushButton#{obj_name}:pressed {{ background-color: {pressed_bg}; }}\n"
        f"QPushButton#{obj_name}:disabled {{ background-color: #334155; color: #cbd5e1; border: 1px solid #475569; }}"
    )


def _format_nps_rate(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f} M/s"
    if n >= 1_000:
        return f"{n / 1_000:.1f} k/s"
    return f"{n:,} /s"


class _FlowLayout(QLayout if HAS_QT else object):
    """Responsive wrapping layout that starts a new line when horizontal space runs out."""

    def __init__(self, parent=None, spacing: int = 8, expand_rows: bool = False):
        if not HAS_QT:
            return
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self._expand_rows = expand_rows
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        l, t, r, b = self.getContentsMargins()
        return size + QSize(l + r, t + b)

    def _do_layout(self, rect: "QRect", test_only: bool) -> int:
        l, t, r, b = self.getContentsMargins()
        eff = rect.adjusted(l, t, -r, -b)
        max_w = max(1, eff.width())
        rows = []
        cur_row = []
        cur_w = 0
        row_h = 0

        for item in self._items:
            sz = item.sizeHint()
            if cur_row and cur_w + self._spacing + sz.width() > max_w:
                rows.append((cur_row, row_h))
                cur_row = []
                cur_w = 0
                row_h = 0
            cur_row.append((item, sz))
            cur_w += (self._spacing if len(cur_row) > 1 else 0) + sz.width()
            row_h = max(row_h, sz.height())
        if cur_row:
            rows.append((cur_row, row_h))

        y = eff.y()
        for row_idx, (row_items, r_h) in enumerate(rows):
            x = eff.x()
            total_base_w = sum(sz.width() for _, sz in row_items) + self._spacing * max(0, len(row_items) - 1)
            extra = max(0, max_w - total_base_w) if (self._expand_rows and row_items) else 0
            per_item_extra = extra // len(row_items) if row_items else 0
            remainder = extra % len(row_items) if row_items else 0

            for col_idx, (item, sz) in enumerate(row_items):
                w = sz.width() + per_item_extra + (1 if col_idx < remainder else 0)
                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y), QSize(w, r_h)))
                x += w + self._spacing
            y += r_h + (self._spacing if row_idx < len(rows) - 1 else 0)
        return (y - eff.y()) + t + b


# =============================================================================
# REAL-TIME CANVAS CHART WIDGETS
# =============================================================================

class _BaseChartWidget(QWidget if HAS_QT else object):
    """Shared canvas chart renderer for session telemetry charts."""

    def __init__(self, parent=None):
        if not HAS_QT:
            return
        super().__init__(parent)
        self.history: List[Dict[str, Any]] = []
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def update_data(self, history: List[Dict[str, Any]]):
        self.history = history or []
        if HAS_QT:
            self.update()

    def _begin_frame(self, title: str, right_txt: str, right_color: str, pad_l: int = 40):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(0, 0, w, h, QColor("#020617"))
        painter.setPen(QPen(QColor("#1e293b"), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(10, 18, title)

        painter.setPen(QColor(right_color))
        painter.drawText(max(10, w - 210 if len(right_txt) > 18 else w - 180), 18, right_txt)

        pad_r, pad_t, pad_b = 10, 26, 18
        pw = max(10, w - pad_l - pad_r)
        ph = max(10, h - pad_t - pad_b)
        return painter, w, h, pad_l, pad_t, pw, ph

    def _draw_x_timestamps(self, painter, h: int, pad_l: int, pw: int):
        if not self.history:
            return
        painter.setFont(QFont("Consolas", 7))
        painter.setPen(QColor("#64748b"))
        painter.drawText(pad_l, h - 3, self.history[0].get("timestamp", ""))
        if len(self.history) > 4:
            painter.drawText(pad_l + pw // 2 - 25, h - 3, self.history[len(self.history) // 2].get("timestamp", ""))
        painter.drawText(max(pad_l + pw // 2 + 10, pad_l + pw - 55), h - 3, self.history[-1].get("timestamp", ""))

    def _draw_polyline(self, painter, key: str, max_val: float, pad_l: int, pad_t: int, pw: int, ph: int, color: str, width: float):
        step = pw / max(1, len(self.history) - 1)
        poly = QPolygonF()
        for i, pt in enumerate(self.history):
            val = min(max_val, max(0.0, float(pt.get(key, 0))))
            poly.append(QPointF(pad_l + i * step, pad_t + ph * (1.0 - val / max_val)))
        painter.setPen(QPen(QColor(color), width))
        painter.drawPolyline(poly)


class CPUChartWidget(_BaseChartWidget):
    """Real-time chart for System CPU % vs Worker CPU % over time."""

    def paintEvent(self, event):
        if not HAS_QT:
            return
        sys_val = self.history[-1].get("system_cpu", 0) if self.history else 0
        wrk_val = self.history[-1].get("worker_cpu", 0) if self.history else 0
        painter, _w, h, pad_l, pad_t, pw, ph = self._begin_frame(
            "CPU USAGE OVER TIME (%)", f"Sys: {sys_val:.1f}% | Wrk: {wrk_val:.1f}%", "#38bdf8", pad_l=35
        )
        painter.setPen(QPen(QColor("#1e293b"), 1, Qt.DotLine))
        for pct in (0.25, 0.5, 0.75):
            y = int(pad_t + ph * (1.0 - pct))
            painter.drawLine(pad_l, y, pad_l + pw, y)

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor("#64748b"))
        painter.drawText(4, int(pad_t + 10), "100%")
        painter.drawText(10, int(pad_t + ph * 0.5 + 4), "50%")
        painter.drawText(16, int(pad_t + ph), "0%")

        if len(self.history) < 2:
            painter.setPen(QColor("#475569"))
            painter.drawText(pad_l + pw // 4, pad_t + ph // 2, "Collecting CPU telemetry (1s)...")
            return

        self._draw_polyline(painter, "system_cpu", 100.0, pad_l, pad_t, pw, ph, "#fbbf24", 1.8)
        self._draw_polyline(painter, "worker_cpu", 100.0, pad_l, pad_t, pw, ph, "#38bdf8", 2.0)
        self._draw_x_timestamps(painter, h, pad_l, pw)


class RAMChartWidget(_BaseChartWidget):
    """Real-time chart for Worker RAM (RSS) vs Host Available RAM over time."""

    def paintEvent(self, event):
        if not HAS_QT:
            return
        wrk_ram = self.history[-1].get("worker_ram", 0) if self.history else 0
        avail_ram = self.history[-1].get("available_ram", 0) if self.history else 0
        painter, _w, h, pad_l, pad_t, pw, ph = self._begin_frame(
            "RAM USAGE OVER TIME (MB)", f"RSS: {wrk_ram} MB | Avail: {avail_ram} MB", "#a78bfa"
        )
        max_val = max(max([pt.get("worker_ram", 0) for pt in self.history] + [1024]) * 1.3, 2048)

        painter.setPen(QPen(QColor("#1e293b"), 1, Qt.DotLine))
        for pct in (0.33, 0.66):
            y = int(pad_t + ph * (1.0 - pct))
            painter.drawLine(pad_l, y, pad_l + pw, y)

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor("#64748b"))
        painter.drawText(4, int(pad_t + 10), f"{int(max_val)}M")
        painter.drawText(10, int(pad_t + ph), "0M")

        if len(self.history) < 2:
            painter.setPen(QColor("#475569"))
            painter.drawText(pad_l + pw // 4, pad_t + ph // 2, "Collecting RAM telemetry (1s)...")
            return

        self._draw_polyline(painter, "worker_ram", max_val, pad_l, pad_t, pw, ph, "#a78bfa", 2.0)
        self._draw_x_timestamps(painter, h, pad_l, pw)


class NPSChartWidget(_BaseChartWidget):
    """Real-time chart for Nodes Per Second across completed tasks this session."""

    def paintEvent(self, event):
        if not HAS_QT:
            return
        latest_nps = self.history[-1].get("nps", 0) if self.history else 0
        painter, _w, h, pad_l, pad_t, pw, ph = self._begin_frame(
            "NPS PER TASK (THIS SESSION)", f"Latest: {_format_nps_rate(latest_nps)}", "#4ade80"
        )
        if not self.history:
            painter.setPen(QColor("#475569"))
            painter.drawText(pad_l + pw // 4, pad_t + ph // 2, "No completed tasks this session yet")
            return

        max_nps = max(max([pt.get("nps", 0) for pt in self.history] + [100_000]) * 1.2, 500_000)
        painter.setPen(QPen(QColor("#1e293b"), 1, Qt.DotLine))
        mid_y = int(pad_t + ph * 0.5)
        painter.drawLine(pad_l, mid_y, pad_l + pw, mid_y)

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor("#64748b"))
        top_lbl = f"{max_nps / 1_000_000:.1f}M" if max_nps >= 1_000_000 else f"{int(max_nps / 1000)}k"
        painter.drawText(4, int(pad_t + 10), top_lbl)
        painter.drawText(10, int(pad_t + ph), "0")

        n = len(self.history)
        spacing = pw / max(1, n)
        bar_w = max(4.0, min(24.0, spacing - 4.0))
        painter.setFont(QFont("Consolas", 7))
        for i, pt in enumerate(self.history):
            bh = min(ph, (float(pt.get("nps", 0)) / max_nps) * ph)
            bx = pad_l + i * spacing + (spacing - bar_w) / 2.0
            by = pad_t + ph - bh
            painter.fillRect(int(bx), int(by), int(bar_w), int(bh), QColor("#38bdf8"))
            ts = pt.get("timestamp", "")
            if ts and (n <= 5 or i in (0, n - 1, n // 2)):
                painter.drawText(max(0, int(bx - 12)), h - 3, ts)


# =============================================================================
# MAIN WINDOW
# =============================================================================

class MainWindow(QMainWindow if HAS_QT else object):
    """Main PySide6 Window for Background Processing Utility."""

    def __init__(self, config: PortableConfig, resource_mgr: ResourceManager,
                 worker_mgr: WorkerManager, engine_mgr: EngineManager,
                 security=None, analytics_logger=None):
        if not HAS_QT:
            raise RuntimeError("PySide6 is required to launch graphical interface.")
        super().__init__()

        self.config = config
        self.resource_mgr = resource_mgr
        self.worker_mgr = worker_mgr
        self.engine_mgr = engine_mgr
        self.analytics_logger = analytics_logger or getattr(worker_mgr, "analytics_logger", None) or AnalyticsLogger(self.config.base_dir)
        self.worker_mgr.set_analytics_logger(self.analytics_logger)

        self.signals = WorkerSignals()
        self.worker_mgr.add_log_callback(self.signals.log_received.emit)
        self.analytics_logger.add_listener(self.signals.analytics_updated.emit)
        self.signals.analytics_updated.connect(self._update_analytics_ui)

        self.setWindowTitle(APP_NAME)
        default_icon = get_default_windows_app_icon()
        if default_icon and not default_icon.isNull():
            self.setWindowIcon(default_icon)
        self.setMinimumSize(520, 420)
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            self.resize(min(1020, max(560, avail.width() - 40)), min(820, max(460, avail.height() - 40)))
        else:
            self.resize(1020, 820)

        self._timeframe_options = [("1.5 mins", 90), ("5 mins", 300), ("10 mins", 600)]
        self.graph_timeframe_seconds = 300
        self._last_eta_task_id: Optional[str] = None

        self._apply_dark_style()
        self._init_ui()
        self._setup_timers()
        self._update_cmd_preview()

    def _apply_dark_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget#centralWidget, QWidget#controlsContainer, QScrollArea, QScrollArea > QWidget {
                background-color: #0b1120;
            }
            QWidget { background-color: #0b1120; color: #e2e8f0; font-size: 13px; }
            QGroupBox {
                border: 1px solid #1e293b; border-radius: 8px; margin-top: 14px;
                padding-top: 16px; font-weight: 600; color: #38bdf8; background-color: #0f172a;
            }
            QGroupBox QWidget, QGroupBox QLabel, QGroupBox QCheckBox { background-color: transparent; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; background-color: #0f172a; }
            QPushButton {
                background-color: #0369a1; color: #ffffff; border: 1px solid #38bdf8;
                padding: 8px 16px; border-radius: 6px; font-weight: 700;
            }
            QPushButton:hover { background-color: #0284c7; }
            QPushButton:disabled { background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; }
            QSlider::groove:horizontal { border: 1px solid #334155; height: 6px; background: #0f172a; border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #0284c7; border-radius: 3px; }
            QSlider::handle:horizontal {
                background: #38bdf8; border: 2px solid #f8fafc;
                width: 16px; height: 16px; margin: -6px 0; border-radius: 9px;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #1e293b; border: 1px solid #334155; padding: 6px 10px;
                border-radius: 5px; color: #f8fafc; font-family: 'Consolas', 'JetBrains Mono', monospace;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid #38bdf8; }
            QCheckBox { spacing: 8px; color: #cbd5e1; }
            QCheckBox::indicator {
                width: 16px; height: 16px; border: 1px solid #64748b;
                border-radius: 4px; background-color: #4b5563;
            }
            QCheckBox::indicator:hover { background-color: #6b7280; }
            QCheckBox::indicator:checked { background-color: #16a34a; border-color: #22c55e; }
            QCheckBox::indicator:checked:hover { background-color: #15803d; }
            QProgressBar {
                border: 1px solid #334155; border-radius: 11px; text-align: center;
                background-color: #1e293b; color: #ffffff; font-weight: 700;
                font-family: 'Consolas', 'JetBrains Mono', monospace;
            }
            QProgressBar::chunk { background-color: #0284c7; border-radius: 10px; }
            QTextEdit {
                background-color: #020617; color: #38bdf8; border: 1px solid #1e293b;
                font-family: 'Consolas', 'JetBrains Mono', monospace; font-size: 12px; border-radius: 6px;
            }
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical { border: none; background: #0b1120; width: 10px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #334155; min-height: 24px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #38bdf8; }
            QScrollBar:horizontal { border: none; background: #0b1120; height: 10px; border-radius: 5px; }
            QScrollBar::handle:horizontal { background: #334155; min-width: 24px; border-radius: 5px; }
            QScrollBar::handle:horizontal:hover { background: #38bdf8; }
            QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
        """)

    @staticmethod
    def _make_kpi(color: str, initial: str = "0", mono: bool = False) -> QLabel:
        lbl = QLabel(initial)
        font_family = " font-family: monospace;" if mono else ""
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color};{font_family}")
        return lbl

    @staticmethod
    def _make_card(title: str, widget: QLabel, subtext: str = "") -> QWidget:
        box = QWidget()
        box.setMinimumWidth(145)
        layout = QVBoxLayout(box)
        layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        lbl_t = QLabel(title)
        lbl_t.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl_t.setStyleSheet("color: #94a3b8; font-size: 11px; text-transform: uppercase; font-weight: 600;")
        layout.addWidget(lbl_t)
        layout.addWidget(widget)
        lbl_sub = QLabel(subtext if subtext else " ")
        lbl_sub.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl_sub.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500;")
        layout.addWidget(lbl_sub)
        return box

    def _init_ui(self):
        main_widget = QWidget()
        main_widget.setObjectName("centralWidget")
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 8, 10, 10)
        main_layout.setSpacing(8)

        # Header + 3 control buttons bar
        header = _FlowLayout(spacing=12)
        title_label = QLabel("BACKGROUND PROCESSING UTILITY")
        title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc; letter-spacing: 0.5px;")
        header.addWidget(title_label)
        self.lbl_server_status = QLabel("Server: Fixed & Built-in (https://belzedar.duckdns.org)")
        self.lbl_server_status.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 11px;")
        header.addWidget(self.lbl_server_status)
        main_layout.addLayout(header)

        ctrl_layout = _FlowLayout(spacing=10)

        self.btn_start = QPushButton("Start")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.setFixedHeight(30)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet(_action_btn_qss("btnStart", "#059669", "#34d399", "#047857", "#6ee7b7", "#065f46"))
        self.btn_start.clicked.connect(self._start_worker)
        ctrl_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop After Finishing Current Task")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setFixedHeight(30)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setStyleSheet(_action_btn_qss("btnStop", "#dc2626", "#f87171", "#b91c1c", "#fca5a5", "#991b1b"))
        self.btn_stop.clicked.connect(self._stop_after_current_task)
        self.btn_stop.setEnabled(False)
        ctrl_layout.addWidget(self.btn_stop)

        self.btn_local_stop = QPushButton("Save and Stop")
        self.btn_local_stop.setObjectName("btnLocalStop")
        self.btn_local_stop.setFixedHeight(30)
        self.btn_local_stop.setCursor(Qt.PointingHandCursor)
        self.btn_local_stop.setStyleSheet(_action_btn_qss("btnLocalStop", "#d97706", "#fbbf24", "#b45309", "#fde68a", "#92400e"))
        self.btn_local_stop.clicked.connect(self._save_and_stop)
        ctrl_layout.addWidget(self.btn_local_stop)
        main_layout.addLayout(ctrl_layout)

        # Full-screen 3-tab view: 1. API Parameters, 2. Live Analysis Console, 3. Graph and Analytics
        self.tab_widget = QTabWidget()
        self.tab_widget.setMinimumHeight(200)
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #1e293b; background-color: #0b1120; border-radius: 6px; }
            QTabBar::tab {
                background: #0f172a; color: #94a3b8; padding: 9px 20px; border: 1px solid #1e293b;
                border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px;
                font-weight: 600; font-size: 12px;
            }
            QTabBar::tab:selected { background: #1e293b; color: #38bdf8; border-color: #38bdf8; }
        """)

        # TAB 1: API PARAMETERS
        tab_api_scroll = QScrollArea()
        tab_api_scroll.setObjectName("scrollControls")
        tab_api_scroll.setWidgetResizable(True)
        tab_api_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tab_api_scroll.setFrameShape(QFrame.NoFrame)

        api_container = QWidget()
        api_container.setObjectName("controlsContainer")
        api_layout = QVBoxLayout(api_container)
        api_layout.setContentsMargins(10, 10, 10, 10)
        api_layout.setSpacing(12)

        cfg_box = QGroupBox("OPENBENCH CONTRIBUTOR API PARAMETERS (UPSTREAM VARIABLES)")
        cfg_layout = QVBoxLayout(cfg_box)
        cfg_layout.setSpacing(12)

        grid_top = QGridLayout()
        grid_top.setSpacing(10)
        grid_top.addWidget(QLabel("Custom Engine (--engine):"), 0, 0)
        self.txt_engine = QLineEdit(self.config.get("openbench", "engine_path", default=""))
        self.txt_engine.setPlaceholderText("Optional path to custom engine binary (blank = default bundled engine)")
        self.txt_engine.textChanged.connect(self._update_cmd_preview)
        grid_top.addWidget(self.txt_engine, 0, 1)

        grid_top.addWidget(QLabel("Syzygy TBs (--syzygy):"), 1, 0)
        self.txt_syzygy = QLineEdit(self.config.get("openbench", "syzygy_path", default=""))
        self.txt_syzygy.setPlaceholderText("Directories separated by ; (blank = auto-manage on USB)")
        self.txt_syzygy.textChanged.connect(self._update_cmd_preview)
        grid_top.addWidget(self.txt_syzygy, 1, 1)
        cfg_layout.addLayout(grid_top)

        def wrap_pair(label_txt: str, field: QWidget) -> QWidget:
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(0, 0, 6, 0)
            hl.setSpacing(6)
            hl.addWidget(QLabel(label_txt))
            hl.addWidget(field)
            return w

        grid_num = _FlowLayout(spacing=10)
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Adaptive", "Balanced", "Maximum", "Custom"])
        self.combo_mode.setCurrentText(self.config.get("resources", "cpu_mode", default="Adaptive"))
        self.combo_mode.currentTextChanged.connect(self._on_mode_changed)
        grid_num.addWidget(wrap_pair("CPU Mode:", self.combo_mode))

        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, self.resource_mgr.logical_cores)
        self.spin_threads.setValue(self.config.get("resources", "threads", default=4))
        self.spin_threads.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(wrap_pair("Threads (-T):", self.spin_threads))

        self.spin_jobs = QSpinBox()
        self.spin_jobs.setRange(1, 64)
        self.spin_jobs.setValue(self.config.get("openbench", "jobs", default=1))
        self.spin_jobs.setToolTip("Number of concurrent analyses to run, splitting -T threads")
        self.spin_jobs.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(wrap_pair("Jobs (--jobs):", self.spin_jobs))

        self.spin_hash = QSpinBox()
        self.spin_hash.setRange(64, 65536)
        self.spin_hash.setSingleStep(128)
        self.spin_hash.setValue(self.config.get("resources", "hash_mb", default=1024))
        self.spin_hash.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(wrap_pair("Hash MB (--hash):", self.spin_hash))

        self.spin_engine_update_min = QDoubleSpinBox()
        self.spin_engine_update_min.setRange(0.5, 1440.0)
        self.spin_engine_update_min.setSingleStep(5.0)
        self.spin_engine_update_min.setValue(float(self.config.get("openbench", "engine_update_minutes", default=15.0)))
        self.spin_engine_update_min.valueChanged.connect(self._update_cmd_preview)
        grid_num.addWidget(wrap_pair("Engine Check Min (--engine-update-minutes):", self.spin_engine_update_min))
        cfg_layout.addLayout(grid_num)

        chk_layout = _FlowLayout(spacing=14)

        def make_chk(label: str, key: str, default: bool, tip: str = "") -> QCheckBox:
            cb = QCheckBox(label)
            if tip:
                cb.setToolTip(tip)
            cb.setChecked(self.config.get("openbench", key, default=default))
            cb.toggled.connect(self._update_cmd_preview)
            return cb

        self.chk_no_fetch_syzygy = make_chk(
            "Disable Tablebases (--no-fetch-syzygy)", "no_fetch_syzygy", True,
            "Checked: skip Syzygy tablebases (saves disk/bandwidth)\nUnchecked: auto-manage tablebases on USB",
        )
        self.chk_solve = make_chk("Solve Tasks (--solve)", "solve", False, "Serve exhaustive proof solve tasks")
        self.chk_no_auto_update = make_chk("No Worker Update (--no-auto-update)", "no_auto_update", False)
        self.chk_no_engine_update = make_chk("No Engine Update (--no-engine-update)", "no_engine_update", False)
        self.chk_once = make_chk("Run Once (--once)", "once", False)

        for cb in (
            self.chk_no_fetch_syzygy, self.chk_solve, self.chk_no_auto_update,
            self.chk_no_engine_update, self.chk_once,
        ):
            chk_layout.addWidget(cb)
        cfg_layout.addLayout(chk_layout)

        cmd_preview_row = QHBoxLayout()
        cmd_preview_row.addWidget(QLabel("Command Preview:"))
        self.lbl_cmd_preview = QLabel("python atomicdb_worker.py ...")
        self.lbl_cmd_preview.setWordWrap(True)
        self.lbl_cmd_preview.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 11px;")
        cmd_preview_row.addWidget(self.lbl_cmd_preview, 1)
        cfg_layout.addLayout(cmd_preview_row)

        api_layout.addWidget(cfg_box)
        api_layout.addStretch()
        tab_api_scroll.setWidget(api_container)
        self.tab_widget.addTab(tab_api_scroll, "API Parameters")

        # TAB 2: LIVE ANALYSIS CONSOLE
        tab_console = QWidget()
        tab_console_layout = QVBoxLayout(tab_console)
        tab_console_layout.setContentsMargins(8, 8, 8, 8)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(160)
        self.console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tab_console_layout.addWidget(self.console)

        console_bar = _FlowLayout(spacing=10)
        btn_clear_console = QPushButton("Clear Console Screen")
        btn_clear_console.setStyleSheet("background-color: #1e293b; color: #e2e8f0; border: 1px solid #475569; font-size: 11px; padding: 4px 10px;")
        btn_clear_console.clicked.connect(self.console.clear)
        console_bar.addWidget(btn_clear_console)

        self.chk_autoscroll = QCheckBox("Auto-scroll")
        self.chk_autoscroll.setChecked(True)
        self.chk_autoscroll.setStyleSheet("color: #94a3b8; font-size: 11px;")
        console_bar.addWidget(self.chk_autoscroll)
        lbl_hint = QLabel("Real-time worker stdout stream directly from USB runtime")
        lbl_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        console_bar.addWidget(lbl_hint)
        tab_console_layout.addLayout(console_bar)
        self.tab_widget.addTab(tab_console, "Live Analysis Console")

        # TAB 3: GRAPH AND ANALYTICS
        tab_analytics_scroll = QScrollArea()
        tab_analytics_scroll.setObjectName("scrollAnalytics")
        tab_analytics_scroll.setWidgetResizable(True)
        tab_analytics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tab_analytics_scroll.setFrameShape(QFrame.NoFrame)

        tab_analytics_content = QWidget()
        tab_analytics_layout = QVBoxLayout(tab_analytics_content)
        tab_analytics_layout.setContentsMargins(10, 10, 10, 10)
        tab_analytics_layout.setSpacing(10)

        # System CPU bar at top of Graph and Analytics tab (worker CPU bar removed, extra rounding)
        cpu_top_row = QHBoxLayout()
        cpu_top_row.setContentsMargins(2, 2, 2, 2)
        cpu_top_row.setSpacing(10)
        lbl_sys_cpu = QLabel("System CPU:")
        lbl_sys_cpu.setStyleSheet("font-weight: 600; color: #cbd5e1;")
        cpu_top_row.addWidget(lbl_sys_cpu)
        self.bar_sys_cpu = QProgressBar()
        self.bar_sys_cpu.setRange(0, 100)
        self.bar_sys_cpu.setFixedHeight(22)
        cpu_top_row.addWidget(self.bar_sys_cpu, 1)
        tab_analytics_layout.addLayout(cpu_top_row)

        # Current Task
        grp_cur = QGroupBox("CURRENT TASK (REAL-TIME EXECUTION & ESTIMATED COMPLETION)")
        grp_cur_layout = QVBoxLayout(grp_cur)
        cur_kpi_layout = _FlowLayout(spacing=8, expand_rows=True)
        self.lbl_cur_task_id = self._make_kpi("#38bdf8", "IDLE", mono=True)
        self.lbl_cur_task_nodes = self._make_kpi("#4ade80", "-")
        self.lbl_cur_task_eta = self._make_kpi("#fbbf24", "Calculating...")
        self.lbl_cur_nps = self._make_kpi("#a78bfa", "0 /s")

        cur_kpi_layout.addWidget(self._make_card("Task ID", self.lbl_cur_task_id, "Active worker slot"))
        cur_kpi_layout.addWidget(self._make_card("Nodes in Task", self.lbl_cur_task_nodes, "Target search budget"))
        cur_kpi_layout.addWidget(self._make_card("Est. Time Remaining", self.lbl_cur_task_eta, "Avg NPS of last 3 tasks"))
        cur_kpi_layout.addWidget(self._make_card("Current NPS", self.lbl_cur_nps, "Live engine speed"))
        grp_cur_layout.addLayout(cur_kpi_layout)

        line_box = QHBoxLayout()
        line_box.addWidget(QLabel("Calculating Line:"))
        self.lbl_cur_line = QLabel("Idle (waiting for next task from server)")
        self.lbl_cur_line.setWordWrap(True)
        self.lbl_cur_line.setStyleSheet(
            "background-color: #020617; color: #38bdf8; border: 1px solid #1e293b; "
            "padding: 6px 10px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 12px;"
        )
        self.lbl_cur_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        line_box.addWidget(self.lbl_cur_line)
        grp_cur_layout.addLayout(line_box)

        lbl_cur_hint = QLabel("Saved automatically to /logs/current_task.log and /logs/activity.log on this USB drive")
        lbl_cur_hint.setWordWrap(True)
        lbl_cur_hint.setStyleSheet("color: #94a3b8; font-size: 12px;")
        grp_cur_layout.addWidget(lbl_cur_hint)
        tab_analytics_layout.addWidget(grp_cur)

        # Session Statistics
        grp_session = QGroupBox("SESSION STATISTICS (SAVED TO /logs/session_statistics.log)")
        grp_session_layout = QVBoxLayout(grp_session)
        session_kpi_layout = _FlowLayout(spacing=8, expand_rows=True)
        self.lbl_session_tasks = self._make_kpi("#38bdf8", "0")
        self.lbl_session_nodes = self._make_kpi("#4ade80", "0")
        self.lbl_session_nps = self._make_kpi("#38bdf8", "0 /s")
        self.lbl_session_avg_nps = self._make_kpi("#a78bfa", "0 /s")
        self.lbl_session_nph = self._make_kpi("#fbbf24", "0 /hr")
        self.lbl_session_uptime = self._make_kpi("#f472b6", "00:00:00", mono=True)

        for title, lbl, sub in (
            ("Tasks This Session", self.lbl_session_tasks, "Session count"),
            ("Total Nodes This Session", self.lbl_session_nodes, "Session nodes"),
            ("Current NPS", self.lbl_session_nps, "Live speed"),
            ("Average NPS This Session", self.lbl_session_avg_nps, "Session average"),
            ("Nodes Per Hour", self.lbl_session_nph, "Session NPH"),
            ("Session Uptime", self.lbl_session_uptime, "Elapsed time"),
        ):
            session_kpi_layout.addWidget(self._make_card(title, lbl, sub))
        grp_session_layout.addLayout(session_kpi_layout)
        tab_analytics_layout.addWidget(grp_session)

        # Lifetime Statistics
        grp_lt = QGroupBox("LIFETIME STATISTICS (SAVED TO /logs/lifetime_statistics.txt — PERMANENTLY PRESERVED)")
        grp_lt_layout = QVBoxLayout(grp_lt)
        lt_kpi_layout = _FlowLayout(spacing=8, expand_rows=True)
        self.lbl_lt_tasks = self._make_kpi("#38bdf8", "0")
        self.lbl_lt_nodes = self._make_kpi("#4ade80", "0")
        self.lbl_lt_avg_nps = self._make_kpi("#fbbf24", "0 /s")
        self.lbl_lt_nph = self._make_kpi("#34d399", "0 /hr")
        self.lbl_lt_runtime = self._make_kpi("#a78bfa", "0s")
        self.lbl_lt_cpu_hours = self._make_kpi("#f472b6", "0.00 hrs")
        self.lbl_lt_sessions = self._make_kpi("#38bdf8", "1")

        for title, lbl, sub in (
            ("Total Tasks Completed", self.lbl_lt_tasks, "Lifetime tasks"),
            ("Total Lifetime Nodes", self.lbl_lt_nodes, "Lifetime nodes"),
            ("Lifetime Average NPS", self.lbl_lt_avg_nps, "Lifetime average"),
            ("Lifetime NPH", self.lbl_lt_nph, "Lifetime Nodes/Hr"),
            ("Total Accumulated Runtime", self.lbl_lt_runtime, "Total compute time"),
            ("Total CPU Hours", self.lbl_lt_cpu_hours, "Thread-hours"),
            ("Total Number of Sessions", self.lbl_lt_sessions, "Recorded runs"),
        ):
            lt_kpi_layout.addWidget(self._make_card(title, lbl, sub))
        grp_lt_layout.addLayout(lt_kpi_layout)

        lbl_lt_hint = QLabel("Lifetime statistics are recorded permanently on this USB thumb drive and are strictly preserved across sessions.")
        lbl_lt_hint.setWordWrap(True)
        lbl_lt_hint.setStyleSheet("color: #94a3b8; font-size: 12px;")
        grp_lt_layout.addWidget(lbl_lt_hint)
        tab_analytics_layout.addWidget(grp_lt)

        # Host Hardware & Graphs (1s Refresh)
        grp_graphs = QGroupBox("HOST HARDWARE TELEMETRY & REAL-TIME SESSION GRAPHS (1s REFRESH)")
        grp_graphs_outer = QVBoxLayout(grp_graphs)
        grp_graphs_outer.setSpacing(8)

        ram_row = _FlowLayout(spacing=12)
        ram_pair = QWidget()
        ram_pair_l = QHBoxLayout(ram_pair)
        ram_pair_l.setContentsMargins(0, 0, 0, 0)
        ram_pair_l.addWidget(QLabel("RAM Allocation:"))
        self.lbl_ram_details = QLabel("Detecting RAM...")
        self.lbl_ram_details.setStyleSheet("color: #38bdf8; font-family: monospace;")
        ram_pair_l.addWidget(self.lbl_ram_details)
        ram_row.addWidget(ram_pair)

        self.lbl_cores = QLabel(f"Cores: {self.resource_mgr.physical_cores} Physical / {self.resource_mgr.logical_cores} Logical")
        self.lbl_cores.setStyleSheet("color: #94a3b8;")
        ram_row.addWidget(self.lbl_cores)
        grp_graphs_outer.addLayout(ram_row)

        tf_bar = _FlowLayout(spacing=8)
        lbl_tf_title = QLabel("Graph Timeframe:")
        lbl_tf_title.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 12px;")
        tf_bar.addWidget(lbl_tf_title)

        self.slider_timeframe = QSlider(Qt.Horizontal)
        self.slider_timeframe.setObjectName("sliderTimeframe")
        self.slider_timeframe.setRange(0, len(self._timeframe_options) - 1)
        self.slider_timeframe.setSingleStep(1)
        self.slider_timeframe.setPageStep(1)
        self.slider_timeframe.setTickInterval(1)
        self.slider_timeframe.setTickPosition(QSlider.TicksBelow)
        self.slider_timeframe.setFixedWidth(160)
        self.slider_timeframe.setValue(1)
        self.slider_timeframe.valueChanged.connect(self._on_timeframe_slider_changed)
        tf_bar.addWidget(self.slider_timeframe)

        self._tf_dial_buttons: List[QPushButton] = []
        for idx, (label_txt, _secs) in enumerate(self._timeframe_options):
            dial_btn = QPushButton(label_txt)
            dial_btn.setCursor(Qt.PointingHandCursor)
            dial_btn.clicked.connect(lambda _checked=False, i=idx: self.slider_timeframe.setValue(i))
            self._tf_dial_buttons.append(dial_btn)
            tf_bar.addWidget(dial_btn)

        self.lbl_graph_timeframe = QLabel("Window: 5 mins")
        self.lbl_graph_timeframe.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 12px; font-weight: 600;")
        tf_bar.addWidget(self.lbl_graph_timeframe)
        self._update_timeframe_dial_styles(1)
        grp_graphs_outer.addLayout(tf_bar)

        grp_graphs_layout = _FlowLayout(spacing=8, expand_rows=True)
        self.chart_cpu = CPUChartWidget()
        self.chart_ram = RAMChartWidget()
        self.chart_nps = NPSChartWidget()
        for chart in (self.chart_cpu, self.chart_ram, self.chart_nps):
            chart.setMinimumWidth(260)
            grp_graphs_layout.addWidget(chart)
        grp_graphs_outer.addLayout(grp_graphs_layout)
        tab_analytics_layout.addWidget(grp_graphs)

        # Persistent Task Execution History
        table_group = QGroupBox("PERSISTENT TASK EXECUTION HISTORY (Saved to USB /logs/history.json)")
        table_layout = QVBoxLayout(table_group)

        self.table_tasks = QTableWidget()
        self.table_tasks.setColumnCount(7)
        self.table_tasks.setHorizontalHeaderLabels(["Timestamp", "Task ID", "Type", "Nodes", "NPS", "TB WDL/DTZ", "Result / Score"])
        self.table_tasks.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_tasks.setAlternatingRowColors(True)
        self.table_tasks.setMinimumHeight(180)
        self.table_tasks.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_tasks.setStyleSheet("""
            QTableWidget {
                background-color: #0b1120; alternate-background-color: #0f172a;
                gridline-color: #1e293b; color: #e2e8f0; font-size: 12px;
                border: 1px solid #1e293b; border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #1e293b; color: #38bdf8; font-weight: 600; padding: 6px; border: none;
            }
        """)
        table_layout.addWidget(self.table_tasks)

        storage_bar = _FlowLayout(spacing=8)
        logs_path = os.path.join(self.config.base_dir, "logs")
        self.lbl_storage_info = QLabel(f"USB Storage: {logs_path} (lifetime_statistics.txt, session_statistics.log, current_task.log, history.json)")
        self.lbl_storage_info.setWordWrap(True)
        self.lbl_storage_info.setStyleSheet("color: #94a3b8; font-size: 12px;")
        storage_bar.addWidget(self.lbl_storage_info)

        btn_refresh_analytics = QPushButton("Refresh from Disk")
        btn_refresh_analytics.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 11px; padding: 4px 10px;")
        btn_refresh_analytics.clicked.connect(self._refresh_analytics_from_disk)
        storage_bar.addWidget(btn_refresh_analytics)
        table_layout.addLayout(storage_bar)

        table_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tab_analytics_layout.addWidget(table_group)

        tab_analytics_scroll.setWidget(tab_analytics_content)
        self.tab_widget.addTab(tab_analytics_scroll, "Graph and Analytics")

        main_layout.addWidget(self.tab_widget, 1)

        if self.analytics_logger:
            self._update_analytics_ui(self.analytics_logger.get_summary())

        self.signals.log_received.connect(self._append_log)

    def _update_cmd_preview(self):
        parts = ["python atomicdb_worker.py", f"-T {self.spin_threads.value()}", f"--hash {self.spin_hash.value()}"]
        if (j := self.spin_jobs.value()) > 1:
            parts.append(f"--jobs {j}")
        if eng := self.txt_engine.text().strip():
            parts.append(f'--engine "{eng}"')
        if syz := self.txt_syzygy.text().strip():
            parts.append(f'--syzygy "{syz}"')
        parts.append("--no-fetch-syzygy" if self.chk_no_fetch_syzygy.isChecked() else "--fetch-syzygy")
        if self.chk_solve.isChecked():
            parts.append("--solve")
        if self.chk_no_auto_update.isChecked():
            parts.append("--no-auto-update")
        if self.chk_no_engine_update.isChecked():
            parts.append("--no-engine-update")
        if (interval := self.spin_engine_update_min.value()) != 15.0:
            parts.append(f"--engine-update-minutes {interval}")
        if self.chk_once.isChecked():
            parts.append("--once")
        self.lbl_cmd_preview.setText(" ".join(parts))

    def _save_ui_settings(self):
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
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._poll_tick)
        self.timer.start(1000)  # Unified 1-second refresh for ETA, CPU, RAM, and session uptime

    def _refresh_eta_1s(self):
        if not self.analytics_logger:
            return
        self.lbl_session_uptime.setText(self.analytics_logger.get_session_uptime_str())

        if self.analytics_logger.current_task_id and not self.worker_mgr.is_running and not self.analytics_logger.is_worker_paused:
            self.analytics_logger.reset_current_task()

        if self.analytics_logger.current_task_id:
            eta = self.analytics_logger.calculate_estimated_time_remaining()
            self.analytics_logger.current_task_eta_seconds = eta
            self.lbl_cur_task_eta.setText(self.analytics_logger.format_eta_str(eta))
            color = "#fb7185" if (eta is not None and eta < 0) else "#fbbf24"
            self.lbl_cur_task_eta.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color}; font-family: monospace;")
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
        self.lbl_ram_details.setText(f"Worker RSS: {worker_ram} MB | Host Avail: {avail_ram} MB")

        if self.analytics_logger:
            self.analytics_logger.set_active_threads(self.spin_threads.value())
            self.analytics_logger.record_hardware_sample(
                sys_cpu=sys_cpu, worker_cpu=worker_cpu, worker_ram_mb=worker_ram, available_ram_mb=avail_ram
            )
            self._update_graph_views()

        if self.resource_mgr.update_adaptive_state(sys_cpu) and self.worker_mgr.is_running:
            self._append_log("[ADAPTIVE] System load threshold triggered. Adjusting worker parameters gracefully...")

        if not self.worker_mgr.is_running and (self.btn_stop.isEnabled() or not self.btn_start.isEnabled()):
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("Stop After Finishing Current Task")

        self._refresh_eta_1s()

    def _start_worker(self):
        self.config.set("safety", "local_stop_active", False)
        user, pwd = self.config.get_account_credentials()
        threads = self.spin_threads.value()

        if self.analytics_logger:
            self.analytics_logger.set_active_threads(threads)
            self.analytics_logger.reset_current_task()

        self.btn_stop.setText("Stop After Finishing Current Task")
        started = self.worker_mgr.start_worker(
            username=user, password=pwd, server_url="https://belzedar.duckdns.org",
            threads=threads, hash_mb=self.spin_hash.value(), jobs=self.spin_jobs.value(),
            engine=self.txt_engine.text().strip(), syzygy=self.txt_syzygy.text().strip(),
            no_fetch_syzygy=self.chk_no_fetch_syzygy.isChecked(), solve=self.chk_solve.isChecked(),
            no_auto_update=self.chk_no_auto_update.isChecked(),
            no_engine_update=self.chk_no_engine_update.isChecked(),
            engine_update_minutes=self.spin_engine_update_min.value(), once=self.chk_once.isChecked(),
        )
        self.btn_start.setEnabled(not started)
        self.btn_stop.setEnabled(bool(started))
        self._refresh_eta_1s()

    def _stop_after_current_task(self):
        if self.worker_mgr.request_stop_after_current_task():
            self.btn_stop.setText("Stopping After Current Task...")
            self.btn_stop.setEnabled(False)
        else:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("Stop After Finishing Current Task")

    def _save_and_stop(self):
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

    def _append_log(self, text: str):
        self.console.append(text)
        if getattr(self, "chk_autoscroll", None) and self.chk_autoscroll.isChecked():
            cursor = self.console.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.console.setTextCursor(cursor)

    def _refresh_analytics_from_disk(self):
        if self.analytics_logger:
            self.analytics_logger.load_persisted_data()
            self._update_analytics_ui(self.analytics_logger.get_summary())

    def _update_timeframe_dial_styles(self, active_idx: int):
        for idx, btn in enumerate(getattr(self, "_tf_dial_buttons", [])):
            if idx == active_idx:
                btn.setStyleSheet("background-color: #0284c7; color: #ffffff; border: 1px solid #38bdf8; border-radius: 4px; font-size: 11px; font-weight: 700; padding: 3px 10px;")
            else:
                btn.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #475569; border-radius: 4px; font-size: 11px; font-weight: 600; padding: 3px 10px;")

    def _on_timeframe_slider_changed(self, idx: int):
        idx = max(0, min(len(self._timeframe_options) - 1, int(idx)))
        label_txt, secs = self._timeframe_options[idx]
        self.graph_timeframe_seconds = secs
        if hasattr(self, "lbl_graph_timeframe"):
            self.lbl_graph_timeframe.setText(f"Window: {label_txt}")
        self._update_timeframe_dial_styles(idx)
        self._update_graph_views()

    def _update_graph_views(self, summary: Optional[dict] = None):
        now = time.time()
        window = getattr(self, "graph_timeframe_seconds", 300)
        if summary is not None:
            cpu_src, ram_src, nps_src = summary.get("cpu_history", []), summary.get("ram_history", []), summary.get("nps_task_history", [])
        elif self.analytics_logger:
            cpu_src, ram_src, nps_src = self.analytics_logger.cpu_history, self.analytics_logger.ram_history, self.analytics_logger.nps_task_history
        else:
            cpu_src, ram_src, nps_src = [], [], []

        self.chart_cpu.update_data(AnalyticsLogger.filter_history_by_timeframe(cpu_src, window, now))
        self.chart_ram.update_data(AnalyticsLogger.filter_history_by_timeframe(ram_src, window, now))
        self.chart_nps.update_data(AnalyticsLogger.filter_history_by_timeframe(nps_src, window, now))

    def _update_analytics_ui(self, summary: dict):
        try:
            cur_id = summary.get("current_task_id")
            if cur_id != self._last_eta_task_id:
                self._last_eta_task_id = cur_id
                if cur_id and hasattr(self, "timer"):
                    self.timer.start(1000)

            if cur_id:
                self.lbl_cur_task_id.setText(str(cur_id))
                self.lbl_cur_task_nodes.setText(format_nodes_compact(summary.get("current_task_nodes", 0)))
                eta_val = summary.get("current_task_eta_seconds")
                self.lbl_cur_task_eta.setText(summary.get("current_task_eta_str", "Calculating..."))
                color = "#fb7185" if (eta_val is not None and eta_val < 0) else "#fbbf24"
                self.lbl_cur_task_eta.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color}; font-family: monospace;")
                self.lbl_cur_nps.setText(_format_nps_rate(summary.get("current_nps", 0)))
                self.lbl_cur_line.setText(summary.get("current_task_line", "Processing search moves..."))
            else:
                self.lbl_cur_task_id.setText("IDLE")
                self.lbl_cur_task_nodes.setText("-")
                self.lbl_cur_task_eta.setText("-")
                self.lbl_cur_task_eta.setStyleSheet("font-size: 18px; font-weight: bold; color: #fbbf24;")
                self.lbl_cur_nps.setText("0 /s")
                self.lbl_cur_line.setText("Idle (waiting for next task from server)")

            self.lbl_session_tasks.setText(f"{summary.get('session_tasks_completed', 0):,}")
            self.lbl_session_nodes.setText(format_nodes_compact(summary.get("session_total_nodes", 0)))
            self.lbl_session_nps.setText(_format_nps_rate(summary.get("current_nps", 0)))
            self.lbl_session_avg_nps.setText(_format_nps_rate(summary.get("session_average_nps", 0)))
            self.lbl_session_nph.setText(format_nph(summary.get("session_nph", 0)))
            self.lbl_session_uptime.setText(summary.get("session_uptime_str", "00:00:00"))

            self.lbl_lt_tasks.setText(f"{summary.get('lifetime_tasks_completed', 0):,}")
            self.lbl_lt_nodes.setText(format_nodes_compact(summary.get("lifetime_total_nodes", 0)))
            self.lbl_lt_avg_nps.setText(_format_nps_rate(summary.get("lifetime_average_nps", 0)))
            self.lbl_lt_nph.setText(format_nph(summary.get("lifetime_nph", 0)))
            self.lbl_lt_runtime.setText(summary.get("lifetime_total_runtime_str", "0s"))
            ch = summary.get("lifetime_cpu_hours", 0.0)
            self.lbl_lt_cpu_hours.setText(f"{ch:.4f} hrs" if (0 < ch < 0.1) else f"{ch:.2f} hrs")
            self.lbl_lt_sessions.setText(f"{summary.get('lifetime_total_sessions', 1):,}")

            self._update_graph_views(summary)

            recent = summary.get("recent_tasks", [])
            self.table_tasks.setRowCount(len(recent))
            for row_idx, task in enumerate(recent):
                ts = task.get("timestamp", "").split(" ")[-1]
                w = task.get("wdl") if task.get("wdl") is not None else task.get("tb_wdl")
                d = task.get("dtz") if task.get("dtz") is not None else task.get("tb_dtz")
                tb_info = (f"wdl={w}" + (f" dtz={d}" if d is not None else "")) if w is not None else "-"
                cols = (
                    ts,
                    str(task.get("task_id", "")),
                    str(task.get("type", "engine")).upper(),
                    format_nodes_compact(task.get("nodes", 0)),
                    f"{task.get('nps', 0):,}",
                    tb_info,
                    str(task.get("summary", "")),
                )
                for col_idx, val in enumerate(cols):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter if col_idx < 6 else Qt.AlignLeft | Qt.AlignVCenter)
                    self.table_tasks.setItem(row_idx, col_idx, item)
        except Exception as e:
            logger.debug(f"Error updating analytics UI: {e}")
