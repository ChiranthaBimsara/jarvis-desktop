"""Run with QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest -v."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from command_center import CommandPalette, OperationsPanel, SystemPanel


class CommandCenterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tasks = self.root / "tasks.json"
        self.activity = self.root / "activity.jsonl"
        self.panel = OperationsPanel(self.tasks, self.activity)
        self.addCleanup(self.panel.close)

    def test_task_add_complete_reopen_and_reload(self):
        self.panel.task_input.setText("Build mission control")
        QTest.keyClick(self.panel.task_input, Qt.Key_Return)
        self.assertEqual(self.panel.task_list.count(), 1)
        self.panel.task_list.setCurrentRow(0)
        self.panel.task_toggle.click()
        saved = json.loads(self.tasks.read_text())
        self.assertEqual(saved[0]["status"], "done")
        self.assertIn("completed", saved[0])
        self.panel.task_toggle.click()
        saved = json.loads(self.tasks.read_text())
        self.assertEqual(saved[0]["status"], "open")
        self.assertNotIn("completed", saved[0])
        other = OperationsPanel(self.tasks, self.activity)
        self.addCleanup(other.close)
        self.assertEqual(other.task_list.item(0).text(), "○ Build mission control")

    def test_invalid_tasks_are_not_overwritten(self):
        self.tasks.write_text('{broken')
        self.panel.task_input.setText("Keep existing data safe")
        self.panel.add_task()
        self.assertEqual(self.tasks.read_text(), '{broken')
        self.assertIn("not saved", self.panel.task_message.text())

    def test_empty_title_and_write_failure(self):
        self.panel.add_task()
        self.assertFalse(self.tasks.exists())
        self.panel.task_input.setText("Unsaved task")
        with patch("command_center.write_tasks", side_effect=OSError("disk full")):
            self.panel.add_task()
        self.assertEqual(self.panel.task_input.text(), "Unsaved task")
        self.assertIn("disk full", self.panel.task_message.text())

    def test_refresh_preserves_selection_and_external_task_changes(self):
        self.tasks.write_text(json.dumps([{"id": 42, "title": "Existing", "status": "open"}]))
        self.panel.refresh_tasks()
        self.panel.task_list.setCurrentRow(0)
        self.panel.refresh_tasks()
        self.assertEqual(self.panel.task_list.currentItem().data(Qt.UserRole), 42)
        rows = json.loads(self.tasks.read_text())
        rows.append({"id": 43, "title": "Added externally", "status": "open"})
        self.tasks.write_text(json.dumps(rows))
        self.panel.toggle_task()
        self.assertEqual(len(json.loads(self.tasks.read_text())), 2)

    def test_activity_search_and_malformed_lines(self):
        self.activity.write_text('\n'.join([
            json.dumps({"kind": "task", "status": "ok", "detail": "Deploy radar"}),
            'invalid JSON', '[]',
            json.dumps({"kind": "memory", "status": "pending", "detail": "Remember launch"}),
        ]))
        self.panel.refresh()
        self.assertEqual(self.panel.activity_list.count(), 2)
        self.assertIn("2 malformed", self.panel.activity_message.text())
        self.panel.activity_search.setText("DEPLOY")
        self.assertEqual(self.panel.activity_list.count(), 1)
        self.assertIn("radar", self.panel.activity_list.item(0).text())
        self.panel.activity_search.setText("pending")
        self.assertEqual(self.panel.activity_list.count(), 1)
        self.panel.activity_search.setText("missing")
        self.assertEqual(self.panel.activity_list.count(), 0)

    def test_activity_is_bounded(self):
        self.activity.write_text('\n'.join(json.dumps({"detail": str(i)}) for i in range(510)))
        self.panel.refresh()
        self.assertEqual(self.panel.activity_list.count(), 500)
        self.assertTrue(self.panel.activity_list.item(0).text().endswith("509"))

    def test_palette_keyboard_search_and_execution(self):
        calls = []
        palette = CommandPalette([("Show tasks", lambda: calls.append("tasks")),
                                  ("Search activity", lambda: calls.append("activity"))])
        self.addCleanup(palette.close)
        palette.show()
        palette.search.setFocus()
        QTest.keyClick(palette.search, Qt.Key_Down)
        self.assertEqual(palette.results.currentRow(), 1)
        QTest.keyClick(palette.search, Qt.Key_Return)
        self.app.processEvents()
        self.assertEqual(calls, ["activity"])
        palette.search.setText("show tasks")
        self.assertEqual(palette.results.count(), 1)
        palette.search.setText("no such command")
        self.assertEqual(palette.results.count(), 0)
        palette.run_selected()
        self.assertEqual(calls, ["activity"])

    def test_telemetry_network_rates_and_history_bound(self):
        class Metrics:
            cpu_percent = staticmethod(lambda interval: 25)
            virtual_memory = staticmethod(lambda: SimpleNamespace(percent=60))
            net_io_counters = staticmethod(lambda: SimpleNamespace(bytes_recv=2048, bytes_sent=1024))
        with patch("command_center.time.monotonic", side_effect=[10, 12]):
            system = SystemPanel(Metrics)
            self.addCleanup(system.close)
            Metrics.net_io_counters = staticmethod(lambda: SimpleNamespace(bytes_recv=6144, bytes_sent=3072))
            system.sample()
        self.assertEqual(system.download.samples[-1], 2)
        self.assertEqual(system.upload.samples[-1], 1)
        for index in range(100):
            system.cpu.add_sample(index)
        self.assertEqual(len(system.cpu.samples), 60)
        system.show()
        self.app.processEvents()
        self.assertFalse(system.grab().isNull())


if __name__ == "__main__":
    unittest.main()
