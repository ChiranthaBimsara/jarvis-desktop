"""Local dashboard tools: focus sessions, scratchpad and device health."""
import math
import os
import platform
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)


class FocusTimer(QFrame):
    completed = Signal()

    def __init__(self, parent=None, clock=time.monotonic):
        super().__init__(parent)
        self.setObjectName("hudFrame")
        self.clock = clock
        self.deadline = None
        self.remaining = 25 * 60
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("FOCUS PROTOCOL"))
        self.duration = QComboBox()
        for title, seconds in (("25 min focus", 1500), ("50 min deep work", 3000), ("5 min break", 300)):
            self.duration.addItem(title, seconds)
        self.duration.currentIndexChanged.connect(self.reset)
        header.addWidget(self.duration)
        layout.addLayout(header)
        row = QHBoxLayout()
        self.display = QLabel("25:00")
        self.display.setStyleSheet("font-size:32px; color:#14d9ff; font-weight:600;")
        row.addWidget(self.display)
        self.toggle = QPushButton("▶ START FOCUS")
        self.toggle.clicked.connect(self.toggle_running)
        row.addWidget(self.toggle)
        reset = QPushButton("RESET")
        reset.clicked.connect(self.reset)
        row.addWidget(reset)
        layout.addLayout(row)
        self.status = QLabel("One mission. Zero distractions.")
        layout.addWidget(self.status)
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.tick)

    def reset(self):
        self.timer.stop()
        self.deadline = None
        self.remaining = self.duration.currentData()
        self.duration.setEnabled(True)
        self.toggle.setText("▶ START FOCUS")
        self.status.setText("Ready when you are.")
        self.render_time()

    def toggle_running(self):
        if self.deadline is not None:
            self.remaining = max(0, self.deadline - self.clock())
            self.deadline = None
            self.timer.stop()
            self.duration.setEnabled(True)
            self.toggle.setText("▶ RESUME")
            self.status.setText("Paused · your remaining time is preserved")
        else:
            if self.remaining <= 0:
                self.remaining = self.duration.currentData()
            self.deadline = self.clock() + self.remaining
            self.duration.setEnabled(False)
            self.timer.start()
            self.toggle.setText("Ⅱ PAUSE")
            self.status.setText("Focus engaged · keep building")
        self.render_time()

    def tick(self):
        if self.deadline is None:
            return
        self.remaining = max(0, self.deadline - self.clock())
        self.render_time()
        if self.remaining == 0:
            self.deadline = None
            self.timer.stop()
            self.duration.setEnabled(True)
            self.toggle.setText("↻ START AGAIN")
            self.status.setText("SESSION COMPLETE · take a breath")
            self.completed.emit()

    def render_time(self):
        minutes, seconds = divmod(math.ceil(self.remaining), 60)
        self.display.setText(f"{minutes:02d}:{seconds:02d}")


class Scratchpad(QWidget):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.dirty = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("CAPTURE AN IDEA"))
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Ideas, commands, plans… keep them here.")
        self.editor.setAccessibleName("Scratchpad notes")
        layout.addWidget(self.editor, 1)
        self.status = QLabel("Saved locally when you click Save")
        self.status.setWordWrap(True)
        try:
            if self.path.exists():
                self.editor.setPlainText(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            self.status.setText(f"Could not load notes: {exc}")
        self.save_button = QPushButton("SAVE NOTES")
        self.save_button.clicked.connect(self.save)
        self.editor.textChanged.connect(self.mark_dirty)
        layout.addWidget(self.save_button)
        layout.addWidget(self.status)

    def mark_dirty(self):
        self.dirty = True
        self.status.setText("Unsaved changes · click Save before closing")

    def save(self):
        name = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".notes-", delete=False) as stream:
                name = stream.name
                stream.write(self.editor.toPlainText())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        except OSError as exc:
            self.status.setText(f"Notes were not saved: {exc}")
            return False
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
        self.editor.document().setModified(False)
        self.dirty = False
        self.status.setText("Saved on this device")
        return True


class DeviceHealth(QFrame):
    def __init__(self, metrics, disk_path, parent=None):
        super().__init__(parent)
        self.metrics, self.disk_path = metrics, str(disk_path)
        self.setObjectName("hudFrame")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("DEVICE HEALTH"))
        self.host = QLabel(f"{platform.system()} · {platform.machine()}")
        self.host.setWordWrap(True)
        layout.addWidget(self.host)
        self.disk = QProgressBar()
        self.disk.setAccessibleName("Disk usage")
        layout.addWidget(self.disk)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(10000)

    def refresh(self):
        if self.metrics is None:
            self.detail.setText("Install psutil for device health")
            self.disk.setEnabled(False)
            return
        try:
            disk = self.metrics.disk_usage(self.disk_path)
            self.disk.setValue(round(disk.percent))
            self.disk.setFormat("DISK %p%")
            hours = max(0, int((time.time() - self.metrics.boot_time()) / 3600))
            self.detail.setText(f"{disk.free / 1024**3:.1f} GB free\nUptime {hours // 24}d {hours % 24}h")
        except (OSError, RuntimeError) as exc:
            self.detail.setText(f"Health unavailable: {exc}")
