"""Private, local memory and evidence-based check-ins; no external data collection."""
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from command_center import read_tasks


class CompanionStore:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {"memories": [], "proactive": False, "interval": 30}
        self.error = None
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if (not isinstance(data, dict) or not isinstance(data.get("memories"), list)
                        or any(not isinstance(row, dict) or not isinstance(row.get("id"), str)
                               or not isinstance(row.get("text"), str)
                               or row.get("kind") not in ("Goal", "Preference", "About me")
                               for row in data["memories"])
                        or type(data.get("proactive")) is not bool
                        or data.get("interval") not in (15, 30, 60)):
                    raise ValueError("Invalid companion data format")
                self.data = data
        except (OSError, ValueError) as exc:
            self.error = f"Cannot load companion data: {exc}. Existing file will not be overwritten."

    def save(self, data):
        if self.error:
            raise ValueError(self.error)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".companion-", delete=False) as stream:
                name = stream.name
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            self.data = data
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def remember(self, kind, text):
        text = text.strip()
        if kind not in ("Goal", "Preference", "About me") or not text or len(text) > 500:
            raise ValueError("Enter a memory of 1–500 characters and choose its type.")
        memories = self.data["memories"] + [{"id": uuid4().hex, "kind": kind, "text": text}]
        self.save({**self.data, "memories": memories})

    def forget(self, identity):
        self.save({**self.data, "memories": [row for row in self.data["memories"] if row["id"] != identity]})


def make_briefing(memories, tasks, now=None):
    """Use only explicit memories and task state; no invented personal insights."""
    now = now or datetime.now()
    greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"
    lines = [f"{greeting}. Here’s your personal briefing."]
    goals = [row["text"] for row in memories if row["kind"] == "Goal"]
    if goals:
        lines.append(f"Your priority: {goals[-1]}")
    opened = [task for task in tasks if task.get("status") == "open"]
    if opened:
        lines.append(f"You have {len(opened)} open task(s). A next step: {opened[0].get('title', 'Untitled task')}.")
    else:
        lines.append("No open tasks. Turn one of your goals into a small next step when you’re ready.")
    preferences = [row["text"] for row in memories if row["kind"] == "Preference"]
    if preferences:
        lines.append(f"Your saved preference: {preferences[-1]}")
    if not memories:
        lines.append("Tell me a goal or preference below to personalize this space.")
    return "\n\n".join(lines)


class PersonalCompanion(QWidget):
    suggestion_ready = Signal(str)

    def __init__(self, path, tasks_path, parent=None, clock=time.monotonic):
        super().__init__(parent)
        self.store = CompanionStore(path)
        self.tasks_path = Path(tasks_path)
        self.clock = clock
        self.snoozed_until = 0
        layout = QVBoxLayout(self)
        heading = QLabel("YOUR PERSONAL SPACE")
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        self.briefing = QLabel()
        self.briefing.setWordWrap(True)
        self.briefing.setTextFormat(Qt.PlainText)
        layout.addWidget(self.briefing)
        refresh = QPushButton("REFRESH MY BRIEFING")
        refresh.clicked.connect(self.refresh_briefing)
        layout.addWidget(refresh)
        layout.addWidget(QLabel("WHAT SHOULD JARVIS REMEMBER?"))
        self.kind = QComboBox()
        self.kind.addItems(["Goal", "Preference", "About me"])
        layout.addWidget(self.kind)
        self.memory_input = QLineEdit()
        self.memory_input.setMaxLength(500)
        self.memory_input.setPlaceholderText("A goal, preference, or fact about you…")
        self.memory_input.setAccessibleName("Personal memory")
        self.memory_input.returnPressed.connect(self.remember)
        layout.addWidget(self.memory_input)
        remember = QPushButton("REMEMBER THIS")
        remember.clicked.connect(self.remember)
        layout.addWidget(remember)
        self.memory_list = QListWidget()
        self.memory_list.setWordWrap(True)
        self.memory_list.setAccessibleName("Saved personal memories")
        layout.addWidget(self.memory_list, 1)
        self.forget_button = QPushButton("FORGET SELECTED")
        self.forget_button.clicked.connect(self.forget)
        layout.addWidget(self.forget_button)
        self.proactive = QCheckBox("Offer gentle check-ins while Jarvis is open")
        self.proactive.setChecked(self.store.data["proactive"])
        layout.addWidget(self.proactive)
        row = QHBoxLayout()
        self.interval = QComboBox()
        for minutes in (15, 30, 60):
            self.interval.addItem(f"Every {minutes} minutes", minutes)
        self.interval.setCurrentIndex(self.interval.findData(self.store.data["interval"]))
        row.addWidget(self.interval)
        snooze = QPushButton("SNOOZE 1H")
        snooze.clicked.connect(self.snooze)
        row.addWidget(snooze)
        layout.addLayout(row)
        self.status = QLabel(self.store.error or "Only what you explicitly save is remembered. Stored on this device.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        self.disclosure = QLabel("Local briefings use saved goals and tasks. No AI model, social-account access, or background monitoring is enabled.")
        self.disclosure.setWordWrap(True)
        layout.addWidget(self.disclosure)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_in)
        self.proactive.toggled.connect(self.save_settings)
        self.interval.currentIndexChanged.connect(self.save_settings)
        self.configure_timer()
        self.refresh_memories()
        self.refresh_briefing()

    def configure_timer(self):
        self.timer.stop()
        if self.store.data["proactive"] and not self.store.error:
            self.timer.start(self.store.data["interval"] * 60 * 1000)

    def save_settings(self):
        try:
            self.store.save({**self.store.data, "proactive": self.proactive.isChecked(),
                             "interval": self.interval.currentData()})
        except (OSError, ValueError) as exc:
            self.status.setText(f"Settings were not saved: {exc}")
            self.proactive.blockSignals(True)
            self.interval.blockSignals(True)
            self.proactive.setChecked(self.store.data["proactive"])
            self.interval.setCurrentIndex(self.interval.findData(self.store.data["interval"]))
            self.proactive.blockSignals(False)
            self.interval.blockSignals(False)
            return
        self.configure_timer()
        self.status.setText("Check-in settings saved. Check-ins run only while Jarvis is open.")

    def refresh_memories(self):
        self.memory_list.clear()
        for memory in self.store.data["memories"]:
            item = QListWidgetItem(f"{memory['kind']} · {memory['text']}")
            item.setData(Qt.UserRole, memory["id"])
            self.memory_list.addItem(item)

    def remember(self):
        try:
            self.store.remember(self.kind.currentText(), self.memory_input.text())
        except (OSError, ValueError) as exc:
            self.status.setText(f"Memory was not saved: {exc}")
            return
        self.memory_input.clear()
        self.status.setText("Remembered on this device. Select a memory to forget it anytime.")
        self.refresh_memories()
        self.refresh_briefing()

    def forget(self):
        item = self.memory_list.currentItem()
        if item is None:
            self.status.setText("Select a memory to forget first.")
            return
        try:
            self.store.forget(item.data(Qt.UserRole))
        except (OSError, ValueError) as exc:
            self.status.setText(f"Memory was not removed: {exc}")
            return
        self.status.setText("Memory removed from companion storage.")
        self.refresh_memories()
        self.refresh_briefing()

    def refresh_briefing(self):
        if self.store.error:
            self.briefing.setText(self.store.error)
            return False
        try:
            tasks = read_tasks(self.tasks_path)
        except (OSError, ValueError) as exc:
            self.briefing.setText(f"Could not read tasks for your briefing: {exc}")
            return False
        self.briefing.setText(make_briefing(self.store.data["memories"], tasks))
        return True

    def snooze(self):
        self.snoozed_until = self.clock() + 3600
        self.status.setText("Check-ins snoozed for one hour in this session.")

    def check_in(self):
        if not self.store.data["proactive"] or self.clock() < self.snoozed_until:
            return
        if self.refresh_briefing():
            self.suggestion_ready.emit(self.briefing.text())
            self.status.setText("A fresh check-in is ready above. No actions were taken.")
