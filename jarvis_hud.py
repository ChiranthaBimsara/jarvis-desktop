#!/usr/bin/env python3
"""
JARVIS HUD UI
Futuristic animated desktop interface for the existing Jarvis stack.

Put this file in the SAME folder as:
    jarvis_pro.py
    jarvis_max.py
    jarvis_agentic.py
    .env

Run:
    python jarvis_hud.py

Features
--------
- Animated boot/loading sequence
- Animated central HUD core
- Listening waveform animation
- Live clock/date
- Live CPU / RAM / battery / network-style status
- Reads jarvis_data/tasks.json
- Reads jarvis_data/memory.json
- Reads jarvis_data/approvals.json
- Reads jarvis_data/activity.jsonl
- Weather panel
- Quick-launch buttons
- Start / Stop your jarvis_agentic.py process
- Streams Jarvis terminal output into the UI
- Reacts visually to "YOU:" and "JARVIS:" output
"""

from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPointF,
    QProcess,
    QRectF,
    QThread,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    import psutil
except ImportError:
    psutil = None


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "jarvis_data"
TASKS_FILE = DATA_DIR / "tasks.json"
MEMORY_FILE = DATA_DIR / "memory.json"
APPROVALS_FILE = DATA_DIR / "approvals.json"
ACTIVITY_FILE = DATA_DIR / "activity.jsonl"

AGENTIC_FILE = BASE_DIR / "jarvis_agentic.py"

USER_NAME = os.getenv("JARVIS_USER_NAME", "Chirantha Bimsara")
USER_AGE = os.getenv("JARVIS_USER_AGE", "24")
DEFAULT_CITY = os.getenv("JARVIS_DEFAULT_CITY", "Colombo")

CYAN = QColor("#14d9ff")
CYAN_2 = QColor("#00a8d8")
BLUE = QColor("#0878c9")
DARK = QColor("#03080d")
PANEL = QColor("#06131d")
PANEL_2 = QColor("#081c28")
GREEN = QColor("#26ff88")
AMBER = QColor("#ffb22e")
RED = QColor("#ff4b47")
TEXT = QColor("#c9f6ff")
MUTED = QColor("#78a9b7")


# ---------------------------------------------------------------------------
# SHARED UTILS
# ---------------------------------------------------------------------------

def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def open_url(url: str):
    if sys.platform == "win32":
        os.startfile(url)
    else:
        import webbrowser
        webbrowser.open(url)


# ---------------------------------------------------------------------------
# WEATHER WORKER
# ---------------------------------------------------------------------------

class WeatherWorker(QThread):
    result = Signal(dict)

    def __init__(self, city: str):
        super().__init__()
        self.city = city

    def run(self):
        result = {
            "city": self.city,
            "temp": "--",
            "desc": "Unavailable",
            "feels": "--",
            "humidity": "--",
            "wind": "--",
        }
        try:
            url = "https://wttr.in/" + urllib.parse.quote(self.city) + "?format=j1"
            req = urllib.request.Request(
                url, headers={"User-Agent": "Jarvis-HUD/1.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8"))
            cur = data["current_condition"][0]
            result = {
                "city": self.city,
                "temp": cur.get("temp_C", "--"),
                "desc": cur.get("weatherDesc", [{"value": "Unknown"}])[0]["value"],
                "feels": cur.get("FeelsLikeC", "--"),
                "humidity": cur.get("humidity", "--"),
                "wind": cur.get("windspeedKmph", "--"),
            }
        except Exception:
            pass
        self.result.emit(result)


# ---------------------------------------------------------------------------
# VISUAL WIDGETS
# ---------------------------------------------------------------------------

class HudFrame(QFrame):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("hudFrame")
        self.setFrameShape(QFrame.NoFrame)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setSpacing(8)

        if title:
            title_label = QLabel(title.upper())
            title_label.setObjectName("panelTitle")
            self.layout.addWidget(title_label)


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "0", accent="cyan", parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self._accent = accent

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(1)

        self.value = QLabel(value)
        self.value.setObjectName("metricValue")
        self.value.setAlignment(Qt.AlignLeft)

        self.title = QLabel(title.upper())
        self.title.setObjectName("metricTitle")

        lay.addWidget(self.value)
        lay.addWidget(self.title)

    def set_value(self, value):
        self.value.setText(str(value))


class CoreWidget(QWidget):
    """Animated reactor/JARVIS core."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0.0
        self.pulse = 0.0
        self.listening = False
        self.speaking = False
        self.booting = False
        self.setMinimumSize(430, 430)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)

    def tick(self):
        self.angle = (self.angle + (2.2 if self.listening else 1.15)) % 360
        self.pulse += (0.14 if self.listening else 0.06)
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def set_state(self, *, listening=False, speaking=False, booting=False):
        self.listening = listening
        self.speaking = speaking
        self.booting = booting
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) * 0.38

        # faint radial glow
        glow = QRadialGradient(QPointF(cx, cy), r * 1.3)
        glow.setColorAt(0, QColor(0, 210, 255, 55))
        glow.setColorAt(0.45, QColor(0, 150, 220, 18))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r * 1.35, r * 1.35)

        # state pulse color
        active = CYAN
        if self.speaking:
            active = GREEN
        elif self.listening:
            active = QColor("#00eeff")
        elif self.booting:
            active = AMBER

        # outer segmented rings
        for layer, frac, speed, width in [
            (0, 1.05, 1.0, 2.0),
            (1, 0.92, -1.7, 1.3),
            (2, 0.79, 2.2, 1.1),
            (3, 0.66, -2.7, 1.0),
        ]:
            rr = r * frac
            pen = QPen(QColor(active.red(), active.green(), active.blue(), 180 - layer * 25))
            pen.setWidthF(width)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)

            segs = 36 - layer * 4
            for i in range(segs):
                if i % (3 + layer) == 0:
                    continue
                start = (i * 360 / segs + self.angle * speed) * 16
                span = (360 / segs * 0.58) * 16
                p.drawArc(QRectF(cx - rr, cy - rr, rr * 2, rr * 2), int(start), int(span))

        if self.listening:
            for ripple in range(6):
                rr = r * (0.82 + ripple * 0.12) * (1.0 + 0.12 * math.sin(self.pulse + ripple))
                pen = QPen(QColor(120, 220, 255, max(18, 130 - ripple * 18)))
                pen.setWidthF(1.3 if ripple % 2 == 0 else 0.9)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(cx, cy), rr, rr)

        # radial tick marks
        p.save()
        p.translate(cx, cy)
        p.rotate(self.angle * 0.6)
        for i in range(72):
            a = math.radians(i * 5)
            inner = r * (0.57 if i % 6 else 0.53)
            outer = r * (0.61 if i % 6 else 0.64)
            alpha = 100 if i % 6 else 210
            p.setPen(QPen(QColor(active.red(), active.green(), active.blue(), alpha), 1))
            p.drawLine(
                QPointF(math.cos(a) * inner, math.sin(a) * inner),
                QPointF(math.cos(a) * outer, math.sin(a) * outer),
            )
        p.restore()

        # wireframe inner sphere
        sphere_r = r * 0.48
        p.setPen(QPen(QColor(active.red(), active.green(), active.blue(), 110), 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), sphere_r, sphere_r)
        for k in [-0.65, -0.32, 0, 0.32, 0.65]:
            hh = sphere_r * math.sqrt(max(0.0, 1 - k * k))
            y = cy + sphere_r * k
            p.drawEllipse(QRectF(cx - hh, y - hh * 0.18, hh * 2, hh * 0.36))

        for deg in [0, 30, 60, 90, 120, 150]:
            p.save()
            p.translate(cx, cy)
            p.rotate(deg + self.angle * 0.2)
            p.drawEllipse(QRectF(-sphere_r * 0.18, -sphere_r, sphere_r * 0.36, sphere_r * 2))
            p.restore()

        # pulse disc
        pulse_scale = 1.0 + math.sin(self.pulse * (2.2 if self.listening else 1.3)) * (0.025 if not self.listening else 0.09)
        disc_r = r * (0.36 if not self.listening else 0.42) * pulse_scale
        grad = QRadialGradient(QPointF(cx, cy), disc_r)
        grad.setColorAt(0, QColor(20, 220, 255, 58 if self.listening else 38))
        grad.setColorAt(0.7, QColor(0, 140, 200, 22 if self.listening else 14))
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(grad)
        p.setPen(QPen(QColor(active.red(), active.green(), active.blue(), 210 if self.listening else 170), 1.8))
        p.drawEllipse(QPointF(cx, cy), disc_r, disc_r)

        # center label
        p.setPen(QPen(TEXT))
        f = QFont("Segoe UI", max(20, int(r * 0.19)), QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        p.setFont(f)
        label_rect = QRectF(cx - r * 0.85, cy - 42, r * 1.7, 84)
        p.drawText(label_rect, Qt.AlignCenter, "JARVIS")

        # state line
        status = "ONLINE"
        if self.booting:
            status = "INITIALIZING"
        elif self.listening:
            status = "LISTENING"
        elif self.speaking:
            status = "RESPONDING"

        sf = QFont("Segoe UI", 11, QFont.Bold)
        sf.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        p.setFont(sf)
        p.setPen(QPen(active))
        p.drawText(QRectF(cx - 120, cy + r * 0.56, 240, 30), Qt.AlignCenter, status)


class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0.0
        self.active = False
        self.speaking = False
        self.samples = [0.0] * 80
        self.setMinimumHeight(72)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(45)

    def set_active(self, active: bool, speaking: bool = False):
        self.active = active
        self.speaking = speaking

    def tick(self):
        self.phase += 0.24
        if self.active:
            amp = 1.0 if self.speaking else 0.76
            self.samples = [
                (
                    math.sin(self.phase * 2.2 + i * 0.32) * 0.42
                    + math.sin(self.phase * 4.7 + i * 0.17) * 0.32
                    + random.uniform(-0.22, 0.22)
                ) * amp
                for i in range(80)
            ]
        else:
            self.samples = [
                s * 0.86 + math.sin(self.phase + i * 0.18) * 0.02
                for i, s in enumerate(self.samples)
            ]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        mid = h / 2

        color = GREEN if self.speaking else CYAN
        if self.active:
            glow = QRadialGradient(QPointF(w / 2, mid), w * 0.55)
            glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 35 if not self.speaking else 60))
            glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            p.setBrush(glow)
            p.setPen(Qt.NoPen)
            p.drawEllipse(0, 0, w, h)

        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 210), 2.0 if self.active else 1.5))

        path = QPainterPath()
        path_fill = QPainterPath()
        baseline = mid
        for i, s in enumerate(self.samples):
            x = i * (w / max(1, len(self.samples) - 1))
            y = mid - s * h * (0.52 if self.active else 0.36)
            if i == 0:
                path.moveTo(x, y)
                path_fill.moveTo(x, baseline)
                path_fill.lineTo(x, y)
            else:
                path.lineTo(x, y)
                path_fill.lineTo(x, y)
        path_fill.lineTo(w, baseline)
        path_fill.closeSubpath()

        if self.active:
            fill = QColor(color.red(), color.green(), color.blue(), 24)
            p.setPen(Qt.NoPen)
            p.setBrush(fill)
            p.drawPath(path_fill)

        p.drawPath(path)

        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 45), 1))
        p.drawLine(0, int(mid), w, int(mid))


class CircularGauge(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label = label
        self.value = 0
        self.setMinimumSize(105, 105)

    def set_value(self, value):
        try:
            self.value = max(0, min(100, int(value)))
        except Exception:
            self.value = 0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        s = min(w, h) - 18
        rect = QRectF((w - s) / 2, (h - s) / 2, s, s)

        p.setPen(QPen(QColor(20, 70, 88, 130), 7))
        p.drawArc(rect, 0, 360 * 16)

        color = GREEN if self.value < 75 else AMBER if self.value < 90 else RED
        p.setPen(QPen(color, 7, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 90 * 16, int(-360 * 16 * self.value / 100))

        p.setPen(TEXT)
        p.setFont(QFont("Segoe UI", 16, QFont.Bold))
        p.drawText(rect, Qt.AlignCenter, f"{self.value}%")

        p.setPen(MUTED)
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(QRectF(0, h - 19, w, 18), Qt.AlignCenter, self.label.upper())


class BootScreen(QWidget):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(100, 80, 100, 80)
        lay.setAlignment(Qt.AlignCenter)

        title = QLabel("J.A.R.V.I.S")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 44px; font-weight: 800; letter-spacing: 10px; color: #14d9ff;"
        )

        self.status = QLabel("INITIALIZING CORE SYSTEMS")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet(
            "font-size: 13px; letter-spacing: 3px; color: #8bdff2;"
        )

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet("""
            QProgressBar {
                background: #07131c;
                border: 1px solid #0d6f91;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: #14d9ff;
                border-radius: 3px;
            }
        """)

        self.detail = QLabel("BOOT SEQUENCE 00")
        self.detail.setAlignment(Qt.AlignCenter)
        self.detail.setStyleSheet("color:#376f82; font-size:10px; letter-spacing:2px;")

        lay.addStretch()
        lay.addWidget(title)
        lay.addSpacing(25)
        lay.addWidget(self.status)
        lay.addSpacing(20)
        lay.addWidget(self.progress)
        lay.addSpacing(15)
        lay.addWidget(self.detail)
        lay.addStretch()

        self.value = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.step)
        self.timer.start(35)

        self.messages = [
            "INITIALIZING CORE SYSTEMS",
            "LOADING NEURAL INTERFACE",
            "CONNECTING VOICE SUBSYSTEM",
            "MOUNTING MEMORY BANKS",
            "CHECKING AGENT WORKFLOWS",
            "SYNCHRONIZING HUD",
            "SYSTEM READY",
        ]

    def step(self):
        self.value += random.randint(1, 4)
        self.value = min(self.value, 100)
        self.progress.setValue(self.value)
        idx = min(len(self.messages) - 1, self.value * len(self.messages) // 101)
        self.status.setText(self.messages[idx])
        self.detail.setText(f"BOOT SEQUENCE {self.value:02d}")

        if self.value >= 100:
            self.timer.stop()
            QTimer.singleShot(500, self.finished.emit)


# ---------------------------------------------------------------------------
# MAIN HUD
# ---------------------------------------------------------------------------

class JarvisHUD(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS HUD")
        self.resize(1700, 980)
        self.setMinimumSize(1200, 700)
        self.setWindowFlag(Qt.FramelessWindowHint)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_process_output)
        self.process.stateChanged.connect(self.process_state_changed)

        self.weather_worker = None
        self.last_activity_mtime = 0
        self.last_mode = "IDLE"

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.boot = BootScreen()
        self.boot.finished.connect(self.show_dashboard)
        self.stack.addWidget(self.boot)

        self.dashboard = QWidget()
        self.stack.addWidget(self.dashboard)

        # Minimal runtime state widgets for the simplified cinematic HUD.
        self.tasks_card = MetricCard("Tasks")
        self.approvals_card = MetricCard("Approvals")
        self.memory_card = MetricCard("Memory")
        self.status_card = MetricCard("Status", "STANDBY")
        self.tasks_card.hide(); self.approvals_card.hide(); self.memory_card.hide(); self.status_card.hide()

        # Keep a minimal system-state strip available without cluttering the cinematic HUD.
        self.cpu_gauge = CircularGauge("CPU")
        self.ram_gauge = CircularGauge("RAM")
        self.battery_gauge = CircularGauge("BAT")
        self.net_gauge = CircularGauge("NET")
        for gauge in (self.cpu_gauge, self.ram_gauge, self.battery_gauge, self.net_gauge):
            gauge.hide()

        self.weather_temp = QLabel("--°C")
        self.weather_desc = QLabel("Loading...")
        self.weather_meta = QLabel("")
        self.weather_temp.hide(); self.weather_desc.hide(); self.weather_meta.hide()

        self.tasks_text = QLabel("No open tasks")
        self.approvals_text = QLabel("No pending approvals")
        self.activity_text = QLabel("Waiting for activity...")
        self.tasks_text.hide(); self.approvals_text.hide(); self.activity_text.hide()

        self.build_dashboard()
        self.apply_style()

        # Timers
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(500)

        self.system_timer = QTimer(self)
        self.system_timer.timeout.connect(self.update_system)
        self.system_timer.start(1500)

        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.refresh_data)
        self.data_timer.start(2000)

        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self.refresh_weather)
        self.weather_timer.start(15 * 60 * 1000)

        self.update_clock()
        self.update_system()
        self.refresh_data()
        self.refresh_weather()

    # ------------------------------------------------------------------

    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #02070d, stop:0.42 #061924, stop:1 #03080f);
                color: #e6fbff;
                font-family: "Segoe UI";
            }

            QFrame#hudFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(8, 20, 30, 235), stop:1 rgba(5, 15, 23, 230));
                border: 1px solid rgba(94, 202, 255, 90);
                border-radius: 20px;
                padding: 6px;
            }

            QFrame#metricCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(11, 26, 35, 255), stop:1 rgba(6, 17, 22, 245));
                border: 1px solid rgba(94, 197, 255, 155);
                border-radius: 16px;
            }

            QLabel#panelTitle {
                color: #9ae8ff;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 2px;
                border-bottom: 1px solid rgba(69, 138, 170, 120);
                padding-bottom: 8px;
            }

            QLabel#metricValue {
                color: #8cecff;
                font-size: 31px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }

            QLabel#metricTitle {
                color: #9bc8d6;
                font-size: 10px;
                letter-spacing: 1.2px;
            }

            QPushButton {
                color: #dffcff;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0b2430, stop:1 #0a1826);
                border: 1px solid rgba(25, 166, 214, 170);
                border-radius: 12px;
                min-height: 32px;
                padding: 10px 12px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }

            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #14384e, stop:1 #0d2a38);
                border: 1px solid #69d8ff;
                color: white;
            }

            QPushButton:pressed {
                background: #0d3e52;
            }

            QPushButton#dangerButton {
                border-color: rgba(255, 118, 118, 170);
                color: #ff9e9a;
            }

            QPushButton#startButton {
                border-color: rgba(62, 216, 143, 180);
                color: #8ef6bc;
            }

            QTextEdit {
                background: rgba(3, 11, 18, 230);
                border: 1px solid rgba(76, 152, 180, 160);
                border-radius: 12px;
                color: #b7edf9;
                font-family: Consolas;
                font-size: 10px;
                padding: 8px;
            }

            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollBar:vertical {
                background: rgba(5, 15, 24, 180);
                width: 8px;
                border-radius: 4px;
            }

            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0c8cc0, stop:1 #62d9ff);
                min-height: 30px;
                border-radius: 4px;
            }
        """)

    # ------------------------------------------------------------------

    def build_dashboard(self):
        root = QVBoxLayout(self.dashboard)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # Header
        header = QHBoxLayout()
        brand = QLabel("JARVIS")
        brand.setStyleSheet(
            "font-size:15px;font-weight:700;letter-spacing:4px;color:#7fe8ff;"
        )

        self.online_label = QLabel("● STANDBY")
        self.online_label.setStyleSheet(
            "color:#ffb22e;font-size:9px;font-weight:700;letter-spacing:2px;"
        )

        self.clock = QLabel()
        self.clock.setStyleSheet(
            "font-size:11px;color:#9fefff;font-weight:600;letter-spacing:1px;"
        )
        self.clock.setAlignment(Qt.AlignRight)

        header.addWidget(brand)
        header.addStretch()
        header.addWidget(self.online_label)
        header.addSpacing(18)
        header.addWidget(self.clock)
        root.addLayout(header)

        # Main cinematic body
        body = QHBoxLayout()
        body.setSpacing(10)

        center = self.build_center_column()
        body.addWidget(center, 1)

        root.addLayout(body, 1)

        # Minimal footer controls
        footer = HudFrame("")
        fl = QHBoxLayout()
        fl.setContentsMargins(12, 4, 12, 4)
        fl.setSpacing(18)

        self.start_btn = QPushButton("▶ START")
        self.start_btn.setObjectName("startButton")
        self.start_btn.clicked.connect(self.start_jarvis)

        self.stop_btn = QPushButton("■ STOP")
        self.stop_btn.setObjectName("dangerButton")
        self.stop_btn.clicked.connect(self.stop_jarvis)

        fl.addStretch()
        fl.addWidget(self.start_btn)
        fl.addWidget(self.stop_btn)

        footer.layout.addLayout(fl)
        root.addWidget(footer)

    # ------------------------------------------------------------------

    def build_left_column(self):
        col = QWidget()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        overview = HudFrame("Overview")
        grid = QGridLayout()
        grid.setSpacing(7)

        self.tasks_card = MetricCard("Tasks")
        self.approvals_card = MetricCard("Approvals")
        self.memory_card = MetricCard("Memory")
        self.status_card = MetricCard("Status", "STANDBY")

        grid.addWidget(self.tasks_card, 0, 0)
        grid.addWidget(self.approvals_card, 0, 1)
        grid.addWidget(self.memory_card, 1, 0)
        grid.addWidget(self.status_card, 1, 1)
        overview.layout.addLayout(grid)

        weather = HudFrame("Weather")
        self.weather_temp = QLabel("--°C")
        self.weather_temp.setStyleSheet("font-size:30px;color:#d9fbff;font-weight:300;")
        self.weather_desc = QLabel("Loading...")
        self.weather_desc.setStyleSheet("color:#61dfff;font-size:11px; font-weight:600;")
        self.weather_meta = QLabel("")
        self.weather_meta.setStyleSheet("color:#91b8c2;font-size:10px; line-height:1.3;")
        self.weather_desc.setWordWrap(True)
        self.weather_meta.setWordWrap(True)
        weather.layout.addWidget(self.weather_temp)
        weather.layout.addWidget(self.weather_desc)
        weather.layout.addWidget(self.weather_meta)

        quick = HudFrame("Quick")
        qgrid = QGridLayout()
        qgrid.setSpacing(6)

        buttons = [
            ("ChatGPT", "https://chatgpt.com"),
            ("YouTube", "https://www.youtube.com"),
            ("Gmail", "https://mail.google.com"),
            ("Meta", "https://business.facebook.com/latest/home"),
        ]

        for i, (name, url) in enumerate(buttons):
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, u=url: open_url(u))
            qgrid.addWidget(b, i // 2, i % 2)

        quick.layout.addLayout(qgrid)

        profile = HudFrame("Profile")
        self.profile_name = QLabel(USER_NAME.upper())
        self.profile_name.setStyleSheet(
            "font-size:13px;color:#14d9ff;font-weight:700;letter-spacing:1px;"
        )
        self.profile_meta = QLabel(f"AGE {USER_AGE} • {DEFAULT_CITY}")
        self.profile_meta.setStyleSheet("font-size:10px;color:#86b3bf;line-height:1.4;")
        profile.layout.addWidget(self.profile_name)
        profile.layout.addWidget(self.profile_meta)

        lay.addWidget(overview)
        lay.addWidget(weather)
        lay.addWidget(quick)
        lay.addWidget(profile)
        lay.addStretch()
        return col

    # ------------------------------------------------------------------

    def build_center_column(self):
        col = QWidget()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        center_frame = HudFrame("")
        center_frame.layout.setContentsMargins(10, 8, 10, 10)

        self.core = CoreWidget()
        self.core.clicked.connect(self.toggle_jarvis)
        self.core.setMinimumSize(520, 520)

        self.wave = WaveformWidget()
        self.wave.setMinimumHeight(70)

        self.prompt_label = QLabel("HOW CAN I HELP YOU TODAY, SIR?")
        self.prompt_label.setAlignment(Qt.AlignCenter)
        self.prompt_label.setWordWrap(True)
        self.prompt_label.setStyleSheet(
            "font-size:16px;color:#8ee8ff;border:1px solid rgba(126, 216, 255, 140);"
            "padding:12px 18px;background:rgba(7, 22, 30, 200);"
            "letter-spacing:1.2px;border-radius:14px;"
        )

        center_frame.layout.addWidget(self.core, 1)
        center_frame.layout.addWidget(self.wave)
        center_frame.layout.addWidget(self.prompt_label)

        console_frame = HudFrame("Live Feed")
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(110)
        self.console.setStyleSheet("background: rgba(3,12,18,220); border: 1px solid rgba(91,170,210,110); border-radius: 12px;")
        console_frame.layout.addWidget(self.console)

        lay.addWidget(center_frame, 1)
        lay.addWidget(console_frame)
        return col

    # ------------------------------------------------------------------

    def build_right_column(self):
        col = QWidget()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        task_frame = HudFrame("Tasks")
        self.tasks_text = QLabel("No open tasks")
        self.tasks_text.setWordWrap(True)
        self.tasks_text.setStyleSheet("color:#a9dce7;font-size:11px; line-height:1.5;")
        task_frame.layout.addWidget(self.tasks_text)

        approval_frame = HudFrame("Approvals")
        self.approvals_text = QLabel("No pending approvals")
        self.approvals_text.setWordWrap(True)
        self.approvals_text.setStyleSheet("color:#d9c47a;font-size:11px; line-height:1.5;")
        approval_frame.layout.addWidget(self.approvals_text)

        activity = HudFrame("Activity")
        self.activity_text = QLabel("Waiting for activity...")
        self.activity_text.setWordWrap(True)
        self.activity_text.setStyleSheet("color:#9fc6d0;font-size:10px; line-height:1.5;")
        activity.layout.addWidget(self.activity_text)

        workflow = HudFrame("Links")
        wgrid = QGridLayout()
        wf = [
            ("Creator", "https://business.facebook.com/latest/content"),
            ("Dashboard", "https://business.facebook.com/latest/home"),
            ("Claude", "https://claude.ai/new"),
            ("Gemini", "https://gemini.google.com"),
        ]
        for i, (name, url) in enumerate(wf):
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, u=url: open_url(u))
            wgrid.addWidget(b, i // 2, i % 2)
        workflow.layout.addLayout(wgrid)

        lay.addWidget(task_frame)
        lay.addWidget(approval_frame)
        lay.addWidget(activity)
        lay.addWidget(workflow)
        lay.addStretch()
        return col

    # ------------------------------------------------------------------

    def show_dashboard(self):
        self.stack.setCurrentWidget(self.dashboard)
        self.core.set_state()
        self.append_console("[HUD] Boot sequence complete.")
        self.append_console("[HUD] Click the central core or START JARVIS.")

    # ------------------------------------------------------------------

    def update_clock(self):
        now = datetime.now()
        self.clock.setText(now.strftime("%a %d %b %Y   %I:%M:%S %p"))

    def update_system(self):
        if psutil:
            try:
                cpu = int(psutil.cpu_percent(interval=None))
                ram = int(psutil.virtual_memory().percent)
                bat = psutil.sensors_battery()
                battery = int(bat.percent) if bat else 100

                for gauge, value in (
                    (getattr(self, "cpu_gauge", None), cpu),
                    (getattr(self, "ram_gauge", None), ram),
                    (getattr(self, "battery_gauge", None), battery),
                    (getattr(self, "net_gauge", None), max(5, 100 - max(cpu, ram))),
                ):
                    if gauge is not None:
                        gauge.set_value(value)
            except Exception:
                pass

    # ------------------------------------------------------------------

    def refresh_weather(self):
        if self.weather_worker and self.weather_worker.isRunning():
            return
        self.weather_worker = WeatherWorker(DEFAULT_CITY)
        self.weather_worker.result.connect(self.apply_weather)
        self.weather_worker.start()

    def apply_weather(self, data):
        self.weather_temp.setText(f"{data['temp']}°C")
        self.weather_desc.setText(data["desc"])
        self.weather_meta.setText(
            f"{data['city']}\n"
            f"Feels like {data['feels']}°C  •  Humidity {data['humidity']}%\n"
            f"Wind {data['wind']} km/h"
        )

    # ------------------------------------------------------------------

    def refresh_data(self):
        tasks = [
            t for t in load_json(TASKS_FILE, [])
            if t.get("status") == "open"
        ]
        memories = load_json(MEMORY_FILE, [])
        approvals = [
            a for a in load_json(APPROVALS_FILE, [])
            if a.get("status") == "pending"
        ]

        if hasattr(self, "tasks_card"):
            self.tasks_card.set_value(len(tasks))
        if hasattr(self, "memory_card"):
            self.memory_card.set_value(len(memories))
        if hasattr(self, "approvals_card"):
            self.approvals_card.set_value(len(approvals))

        if hasattr(self, "tasks_text"):
            if tasks:
                lines = []
                for t in tasks[:5]:
                    due = t.get("due")
                    due_txt = f"  [{due}]" if due else ""
                    lines.append(f"• {t.get('title','Task')}{due_txt}")
                self.tasks_text.setText("\n".join(lines))
            else:
                self.tasks_text.setText("No open tasks\nYou're all caught up.")

        if hasattr(self, "approvals_text"):
            if approvals:
                self.approvals_text.setText(
                    "\n".join(
                        f"• {a.get('description','Pending action')}"
                        for a in approvals[:4]
                    )
                )
            else:
                self.approvals_text.setText("No pending approvals")

        self.refresh_activity()

    def refresh_activity(self):
        if not ACTIVITY_FILE.exists():
            return
        try:
            lines = ACTIVITY_FILE.read_text(encoding="utf-8").splitlines()[-7:]
            output = []
            for line in reversed(lines):
                try:
                    row = json.loads(line)
                    t = row.get("time", "")
                    if "T" in t:
                        t = t.split("T", 1)[1][:5]
                    detail = row.get("detail", "")
                    output.append(f"● {t}   {detail}")
                except Exception:
                    continue
            if output and hasattr(self, "activity_text"):
                self.activity_text.setText("\n".join(output))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # PROCESS CONTROL
    # ------------------------------------------------------------------

    def start_jarvis(self):
        if self.process.state() != QProcess.NotRunning:
            self.append_console("[HUD] Jarvis is already running.")
            return

        if not AGENTIC_FILE.exists():
            QMessageBox.warning(
                self,
                "Missing file",
                f"Could not find:\n{AGENTIC_FILE}\n\n"
                "Put jarvis_hud.py in the same folder as jarvis_agentic.py.",
            )
            return

        self.append_console("[HUD] Launching jarvis_agentic.py ...")
        self.process.setWorkingDirectory(str(BASE_DIR))
        self.process.start(sys.executable, ["-u", str(AGENTIC_FILE)])

        self.online_label.setText("● STARTING")
        self.online_label.setStyleSheet(
            "color:#ffb22e;font-size:11px;font-weight:700;letter-spacing:2px;"
        )
        self.status_card.set_value("STARTING")
        self.core.set_state(booting=True)
        self.wave.set_active(True)

    def stop_jarvis(self):
        if self.process.state() == QProcess.NotRunning:
            self.append_console("[HUD] Jarvis is not running.")
            return

        self.append_console("[HUD] Stopping Jarvis ...")
        self.process.terminate()
        QTimer.singleShot(2500, self.force_kill_if_needed)

    def force_kill_if_needed(self):
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()

    def toggle_jarvis(self):
        if self.process.state() == QProcess.NotRunning:
            self.start_jarvis()
        else:
            self.show_status_message()

    def process_state_changed(self, state):
        if state == QProcess.Running:
            self.online_label.setText("● ONLINE")
            self.online_label.setStyleSheet(
                "color:#26ff88;font-size:11px;font-weight:700;letter-spacing:2px;"
            )
            self.status_card.set_value("ONLINE")
            self.core.set_state(listening=True)
            self.wave.set_active(True)
            self.prompt_label.setText("LISTENING FOR YOUR COMMAND")
        elif state == QProcess.NotRunning:
            self.online_label.setText("● STANDBY")
            self.online_label.setStyleSheet(
                "color:#ffb22e;font-size:11px;font-weight:700;letter-spacing:2px;"
            )
            self.status_card.set_value("STANDBY")
            self.core.set_state()
            self.wave.set_active(False)
            self.prompt_label.setText("HOW CAN I HELP YOU TODAY, SIR?")

    def read_process_output(self):
        data = bytes(self.process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        if not data:
            return

        for line in data.splitlines():
            self.append_console(line)
            u = line.upper()

            if "YOU:" in u or "LISTENING FOR COMMAND" in u:
                self.last_mode = "LISTENING"
                self.core.set_state(listening=True)
                self.wave.set_active(True, speaking=False)
                self.prompt_label.setText("LISTENING...")
            elif "JARVIS:" in u:
                self.last_mode = "RESPONDING"
                self.core.set_state(speaking=True)
                self.wave.set_active(True, speaking=True)
                self.prompt_label.setText("JARVIS RESPONDING")
                QTimer.singleShot(4000, self.return_to_listening_state)
            elif "DOUBLE CLAP" in u:
                self.core.set_state(booting=True)
                self.prompt_label.setText("WAKE SIGNAL DETECTED")
                QTimer.singleShot(1500, self.return_to_listening_state)

    def return_to_listening_state(self):
        if self.process.state() == QProcess.Running:
            self.core.set_state(listening=True)
            self.wave.set_active(True, speaking=False)
            self.prompt_label.setText("LISTENING FOR YOUR COMMAND")

    def append_console(self, text):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.console.append(f"[{stamp}] {text}")
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ------------------------------------------------------------------
    # BUTTON ACTIONS
    # ------------------------------------------------------------------

    def show_status_message(self):
        tasks = self.tasks_card.value.text()
        approvals = self.approvals_card.value.text()
        memories = self.memory_card.value.text()
        QMessageBox.information(
            self,
            "JARVIS STATUS",
            f"Jarvis: {self.status_card.value.text()}\n"
            f"Tasks: {tasks}\n"
            f"Approvals: {approvals}\n"
            f"Memories: {memories}",
        )

    def show_tasks_dialog(self):
        tasks = [
            t for t in load_json(TASKS_FILE, [])
            if t.get("status") == "open"
        ]
        text = "\n".join(
            f"• {t.get('title','Task')}"
            for t in tasks
        ) or "No open tasks."
        QMessageBox.information(self, "Open Tasks", text)

    def show_memories_dialog(self):
        memories = load_json(MEMORY_FILE, [])
        text = "\n".join(
            f"• {m.get('text','')}"
            for m in memories[-12:]
        ) or "No saved memories."
        QMessageBox.information(self, "Recent Memories", text)

    def open_morning_brief_help(self):
        self.append_console("[HUD] Voice command: say 'morning brief' after Jarvis is listening.")
        QMessageBox.information(
            self,
            "Morning Brief",
            "With Jarvis running, say:\n\n"
            "“Morning brief”\n\n"
            "Jarvis will read your open tasks and approvals and open your work dashboards.",
        )


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS HUD")

    # dark palette-friendly font setup
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    win = JarvisHUD()
    win.showMaximized()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
