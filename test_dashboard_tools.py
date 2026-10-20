import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from dashboard_tools import DeviceHealth, FocusTimer, Scratchpad


class DashboardToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_focus_pause_resume_deadline_and_completion(self):
        now = [100.0]
        focus = FocusTimer(clock=lambda: now[0])
        self.addCleanup(focus.close)
        completions = []
        focus.completed.connect(lambda: completions.append(True))
        focus.toggle.click()
        now[0] += 75
        focus.tick()
        self.assertEqual(focus.display.text(), "23:45")
        focus.toggle.click()
        now[0] += 1000
        self.assertEqual(focus.remaining, 1425)
        focus.toggle.click()
        now[0] += 1426
        focus.tick()
        focus.tick()
        self.assertEqual(focus.display.text(), "00:00")
        self.assertEqual(completions, [True])
        self.assertFalse(focus.timer.isActive())

    def test_focus_presets_and_reset(self):
        focus = FocusTimer()
        self.addCleanup(focus.close)
        focus.duration.setCurrentIndex(2)
        self.assertEqual(focus.display.text(), "05:00")
        focus.toggle_running()
        focus.reset()
        self.assertIsNone(focus.deadline)
        self.assertEqual(focus.remaining, 300)
        self.assertTrue(focus.duration.isEnabled())

    def test_scratchpad_save_reload_and_failed_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.txt"
            notes = Scratchpad(path)
            self.addCleanup(notes.close)
            notes.editor.setPlainText("Launch plan 🚀\nSecond line")
            self.assertTrue(notes.dirty)
            self.assertTrue(notes.save())
            self.assertFalse(notes.dirty)
            second = Scratchpad(path)
            self.addCleanup(second.close)
            self.assertEqual(second.editor.toPlainText(), notes.editor.toPlainText())
            notes.editor.setPlainText("New idea")
            with patch("dashboard_tools.os.replace", side_effect=OSError("disk full")):
                self.assertFalse(notes.save())
            self.assertIn("disk full", notes.status.text())
            self.assertTrue(notes.dirty)
            self.assertIn("Launch plan", path.read_text())
            self.assertEqual(list(Path(directory).glob('.notes-*')), [])

    def test_device_health_values_and_missing_metrics(self):
        metrics = SimpleNamespace(
            disk_usage=lambda path: SimpleNamespace(percent=35, free=10 * 1024**3),
            boot_time=lambda: 1000,
        )
        with patch("dashboard_tools.time.time", return_value=1000 + 27 * 3600):
            health = DeviceHealth(metrics, "/")
        self.addCleanup(health.close)
        self.assertEqual(health.disk.value(), 35)
        self.assertIn("1d 3h", health.detail.text())
        self.assertIn("10.0 GB", health.detail.text())
        missing = DeviceHealth(None, "/")
        self.addCleanup(missing.close)
        self.assertIn("Install psutil", missing.detail.text())

    def test_hud_notes_close_protection_fullscreen_and_palette(self):
        import jarvis_hud as h
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(h.JarvisHUD, "refresh_weather"), patch.object(h, "DATA_DIR", Path(directory)):
                win = h.JarvisHUD()
            self.addCleanup(win.deleteLater)
            win.show()
            win.show_dashboard()
            win.focus_notes()
            self.assertEqual(win.operations.currentWidget(), win.scratchpad)
            win.scratchpad.editor.setPlainText("Keep this idea")
            with patch.object(QMessageBox, "question", return_value=QMessageBox.Cancel):
                self.assertFalse(win.close())
            self.assertTrue(win.isVisible())
            win.toggle_fullscreen()
            self.assertTrue(win.isFullScreen())
            win.toggle_fullscreen()
            self.assertFalse(win.isFullScreen())
            def choose_focus():
                palette = self.app.activeModalWidget()
                palette.search.setText("pause focus")
                palette.run_selected()
            QTimer.singleShot(0, choose_focus)
            win.open_command_palette()
            self.app.processEvents()
            self.assertIsNotNone(win.focus_timer.deadline)
            win.focus_timer.reset()
            with patch.object(QMessageBox, "question", return_value=QMessageBox.Save):
                self.assertTrue(win.close())
            self.assertEqual((Path(directory) / "scratchpad.txt").read_text(), "Keep this idea")


if __name__ == "__main__":
    unittest.main()
