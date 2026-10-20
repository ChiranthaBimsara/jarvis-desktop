"""Command center widgets. No voice runtime or external services required."""
from __future__ import annotations

import json
import os
import tempfile
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)


class Sparkline(QWidget):
    """Bounded history, with an independent scale for each metric."""

    def __init__(self, title, unit="%", fixed_scale=100, parent=None):
        super().__init__(parent)
        self.title, self.unit, self.fixed_scale = title, unit, fixed_scale
        self.samples = deque(maxlen=60)
        self.setMinimumHeight(100)
        self.setAccessibleName(title + " history")

    def add_sample(self, value):
        self.samples.append(max(0, float(value)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#06131d"))
        painter.setPen(QColor("#9ae8ff"))
        value = f"{self.samples[-1]:.1f}{self.unit}" if self.samples else "Unavailable"
        painter.drawText(12, 22, f"{self.title}   {value}")
        top, height, width = 35, max(1, self.height() - 47), max(1, self.width() - 24)
        painter.setPen(QPen(QColor("#143b49"), 1))
        for fraction in (0, 0.5, 1):
            y = int(top + height * fraction)
            painter.drawLine(12, y, 12 + width, y)
        if not self.samples:
            return
        scale = self.fixed_scale or max(1, max(self.samples) * 1.15)
        path = QPainterPath()
        for index, value in enumerate(self.samples):
            x = 12 + width * index / 59
            y = top + height * (1 - min(1, value / scale))
            if index == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        painter.setPen(QPen(QColor("#14d9ff"), 2))
        painter.drawPath(path)


class SystemPanel(QWidget):
    def __init__(self, metrics, parent=None):
        super().__init__(parent)
        self.metrics = metrics
        self.previous_network = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("SYSTEM RADAR"))
        self.cpu = Sparkline("CPU")
        self.ram = Sparkline("RAM")
        self.download = Sparkline("Download", " KB/s", None)
        self.upload = Sparkline("Upload", " KB/s", None)
        for graph in (self.cpu, self.ram, self.download, self.upload):
            layout.addWidget(graph)
        self.note = QLabel("60 samples · every 1.5s\nNetwork graphs scale automatically")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        layout.addStretch()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sample)
        self.timer.start(1500)
        self.sample()

    def sample(self):
        if self.metrics is None:
            self.note.setText("Install psutil to enable system telemetry.")
            return
        try:
            self.cpu.add_sample(self.metrics.cpu_percent(interval=None))
            self.ram.add_sample(self.metrics.virtual_memory().percent)
            counters = self.metrics.net_io_counters()
            now = time.monotonic()
            if counters is not None:
                if self.previous_network is not None:
                    before, received, sent = self.previous_network
                    elapsed = max(now - before, 0.001)
                    self.download.add_sample((counters.bytes_recv - received) / elapsed / 1024)
                    self.upload.add_sample((counters.bytes_sent - sent) / elapsed / 1024)
                self.previous_network = (now, counters.bytes_recv, counters.bytes_sent)
        except (OSError, RuntimeError) as exc:
            self.note.setText(f"Telemetry unavailable: {exc}")


def read_tasks(path: Path):
    if not path.exists():
        return []
    tasks = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(tasks, list) or any(not isinstance(task, dict) for task in tasks):
        raise ValueError("Task file must contain a list of task objects")
    return tasks


def write_tasks(path: Path, tasks):
    """Replace atomically so readers never see a partially written JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".tasks-", delete=False) as stream:
            name = stream.name
            json.dump(tasks, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


class OperationsPanel(QTabWidget):
    def __init__(self, tasks_path, activity_path, parent=None):
        super().__init__(parent)
        self.tasks_path, self.activity_path = Path(tasks_path), Path(activity_path)
        self.activity_rows = []
        tasks_tab = QWidget()
        layout = QVBoxLayout(tasks_tab)
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("New mission… press Enter")
        self.task_input.setAccessibleName("New task title")
        self.task_input.setMaxLength(500)
        self.task_input.returnPressed.connect(self.add_task)
        layout.addWidget(self.task_input)
        add = QPushButton("+ ADD TASK")
        add.clicked.connect(self.add_task)
        layout.addWidget(add)
        self.task_list = QListWidget()
        self.task_list.setAccessibleName("Tasks")
        layout.addWidget(self.task_list, 1)
        self.task_toggle = QPushButton("COMPLETE / REOPEN")
        self.task_toggle.clicked.connect(self.toggle_task)
        self.task_toggle.setEnabled(False)
        self.task_list.itemSelectionChanged.connect(
            lambda: self.task_toggle.setEnabled(self.task_list.currentItem() is not None))
        layout.addWidget(self.task_toggle)
        self.task_message = QLabel()
        self.task_message.setWordWrap(True)
        layout.addWidget(self.task_message)
        self.addTab(tasks_tab, "Tasks")

        activity_tab = QWidget()
        layout = QVBoxLayout(activity_tab)
        self.activity_search = QLineEdit()
        self.activity_search.setPlaceholderText("Search activity, type, or status…")
        self.activity_search.setAccessibleName("Search activity")
        self.activity_search.textChanged.connect(self.filter_activity)
        layout.addWidget(self.activity_search)
        self.activity_list = QListWidget()
        self.activity_list.setWordWrap(True)
        layout.addWidget(self.activity_list, 1)
        self.activity_message = QLabel()
        self.activity_message.setWordWrap(True)
        layout.addWidget(self.activity_message)
        self.addTab(activity_tab, "Activity")
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)

    def refresh_tasks(self):
        selected = self.task_list.currentItem()
        selected_id = selected.data(Qt.UserRole) if selected else None
        try:
            tasks = read_tasks(self.tasks_path)
        except (OSError, ValueError) as exc:
            self.task_message.setText(f"Cannot read tasks: {exc}")
            return
        self.task_list.clear()
        for task in tasks:
            done = task.get("status") == "done"
            title = str(task.get("title", "Untitled"))
            item = QListWidgetItem(f"{'✓' if done else '○'} {title}")
            item.setData(Qt.UserRole, task.get("id"))
            item.setToolTip(f"{task.get('status', 'open')} · Due: {task.get('due') or 'No due date'}")
            self.task_list.addItem(item)
            if selected_id is not None and task.get("id") == selected_id:
                self.task_list.setCurrentItem(item)
        count = sum(task.get("status") == "open" for task in tasks)
        self.task_message.setText(f"{count} open · {len(tasks)} total")

    def add_task(self):
        title = self.task_input.text().strip()
        if not title:
            self.task_message.setText("Enter a task title first.")
            return
        try:
            tasks = read_tasks(self.tasks_path)
            tasks.append({"id": uuid4().hex, "title": title, "status": "open",
                          "created": datetime.now().isoformat(timespec="seconds"),
                          "due": None, "category": "general", "notified": False})
            write_tasks(self.tasks_path, tasks)
        except (OSError, ValueError) as exc:
            self.task_message.setText(f"Task was not saved: {exc}")
            return
        self.task_input.clear()
        self.refresh_tasks()

    def toggle_task(self):
        item = self.task_list.currentItem()
        if item is None:
            return
        task_id = item.data(Qt.UserRole)
        if task_id is None:
            self.task_message.setText("This task has no ID; it cannot be updated safely.")
            return
        try:
            tasks = read_tasks(self.tasks_path)
            matches = [task for task in tasks if task.get("id") == task_id]
            if len(matches) != 1:
                self.task_message.setText("Task changed externally; refresh and select it again.")
                return
            task = matches[0]
            task["status"] = "open" if task.get("status") == "done" else "done"
            if task["status"] == "done":
                task["completed"] = datetime.now().isoformat(timespec="seconds")
            else:
                task.pop("completed", None)
            write_tasks(self.tasks_path, tasks)
        except (OSError, ValueError) as exc:
            self.task_message.setText(f"Task was not updated: {exc}")
            return
        self.refresh_tasks()

    def refresh(self):
        self.refresh_tasks()
        try:
            rows, invalid = [], 0
            if self.activity_path.exists():
                with self.activity_path.open(encoding="utf-8", errors="replace") as stream:
                    for line in deque(stream, maxlen=500):
                        try:
                            row = json.loads(line)
                            if not isinstance(row, dict):
                                raise ValueError("Not an activity object")
                            rows.append(" · ".join(str(row.get(key, "")) for key in
                                                   ("time", "kind", "status", "detail")))
                        except ValueError:
                            invalid += 1
            self.activity_rows = list(reversed(rows))
            self.filter_activity()
            if invalid:
                self.activity_message.setText(self.activity_message.text() + f" · {invalid} malformed skipped")
        except OSError as exc:
            self.activity_message.setText(f"Cannot read activity: {exc}")

    def filter_activity(self):
        query = self.activity_search.text().strip().casefold()
        self.activity_list.clear()
        matches = [row for row in self.activity_rows if query in row.casefold()]
        self.activity_list.addItems(matches)
        self.activity_message.setText(f"{len(matches)} matches · latest 500 events" if self.activity_rows
                                      else "No activity yet")

    def focus_tasks(self):
        self.setCurrentIndex(0)
        self.task_input.setFocus()

    def focus_activity(self):
        self.setCurrentIndex(1)
        self.activity_search.setFocus()


class CommandPalette(QDialog):
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Command palette")
        self.setMinimumWidth(520)
        self.actions = actions
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("COMMAND PALETTE · ↑ ↓ to select · Enter to run · Esc to close"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a command…")
        self.search.setAccessibleName("Search commands")
        layout.addWidget(self.search)
        self.results = QListWidget()
        layout.addWidget(self.results)
        self.empty = QLabel("No matching commands")
        layout.addWidget(self.empty)
        self.search.textChanged.connect(self.filter)
        self.search.returnPressed.connect(self.run_selected)
        self.results.itemActivated.connect(self.run_selected)
        self.filter()

    def filter(self):
        self.results.clear()
        query = self.search.text().casefold().split()
        for title, callback in self.actions:
            if all(word in title.casefold() for word in query):
                item = QListWidgetItem(title)
                item.setData(Qt.UserRole, self.actions.index((title, callback)))
                self.results.addItem(item)
        self.results.setCurrentRow(0)
        self.empty.setVisible(self.results.count() == 0)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Down, Qt.Key_Up):
            step = 1 if event.key() == Qt.Key_Down else -1
            row = max(0, min(self.results.count() - 1, self.results.currentRow() + step))
            self.results.setCurrentRow(row)
            return
        super().keyPressEvent(event)

    def run_selected(self, *_):
        item = self.results.currentItem()
        if item is not None:
            callback = self.actions[item.data(Qt.UserRole)][1]
            self.accept()
            QTimer.singleShot(0, callback)
