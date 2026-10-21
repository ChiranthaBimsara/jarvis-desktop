import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from personal_companion import CompanionStore, PersonalCompanion, make_briefing


class PersonalCompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'companion.json'
        self.tasks = self.path.with_name('tasks.json')

    def test_remember_reload_forget(self):
        store = CompanionStore(self.path)
        store.remember('Goal', 'Grow my Facebook Page')
        store.remember('Preference', 'Keep suggestions brief')
        other = CompanionStore(self.path)
        self.assertEqual(len(other.data['memories']), 2)
        other.forget(other.data['memories'][0]['id'])
        self.assertEqual(len(CompanionStore(self.path).data['memories']), 1)

    def test_corrupt_file_is_protected(self):
        self.path.write_text('{broken')
        store = CompanionStore(self.path)
        with self.assertRaises(ValueError):
            store.remember('Goal', 'Something new')
        self.assertEqual(self.path.read_text(), '{broken')

    def test_failed_save_preserves_memory_and_file(self):
        store = CompanionStore(self.path)
        store.remember('Goal', 'Original')
        with patch('personal_companion.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                store.remember('Goal', 'New')
        self.assertEqual(len(store.data['memories']), 1)
        self.assertEqual(len(CompanionStore(self.path).data['memories']), 1)
        self.assertEqual(list(self.path.parent.glob('.companion-*')), [])

    def test_briefing_grounded_in_goals_and_open_tasks(self):
        text = make_briefing([{'kind': 'Goal', 'text': 'Make useful videos'}], [
            {'status': 'done', 'title': 'Finished'}, {'status': 'open', 'title': 'Write script'}],
            datetime(2026, 10, 21, 9))
        self.assertIn('Good morning', text)
        self.assertIn('Make useful videos', text)
        self.assertIn('Write script', text)
        self.assertNotIn('Finished', text)

    def test_ui_settings_checkins_and_snooze(self):
        now = [0]
        panel = PersonalCompanion(self.path, self.tasks, clock=lambda: now[0])
        self.addCleanup(panel.close)
        events = []
        panel.suggestion_ready.connect(events.append)
        panel.memory_input.setText('Grow my Page')
        panel.remember()
        self.assertIn('Grow my Page', panel.briefing.text())
        panel.check_in()
        self.assertEqual(events, [])
        panel.proactive.setChecked(True)
        self.assertTrue(panel.timer.isActive())
        panel.check_in()
        self.assertEqual(len(events), 1)
        panel.snooze()
        panel.check_in()
        self.assertEqual(len(events), 1)
        now[0] = 3601
        panel.check_in()
        self.assertEqual(len(events), 2)
        panel.proactive.setChecked(False)
        self.assertFalse(panel.timer.isActive())
        self.assertFalse(CompanionStore(self.path).data['proactive'])
        panel.memory_list.setCurrentRow(0)
        panel.forget()
        self.assertEqual(panel.memory_list.count(), 0)

    def test_unreadable_tasks_do_not_generate_false_briefings(self):
        self.tasks.write_text('not JSON')
        panel = PersonalCompanion(self.path, self.tasks)
        self.addCleanup(panel.close)
        events = []
        panel.suggestion_ready.connect(events.append)
        panel.proactive.setChecked(True)
        panel.check_in()
        self.assertEqual(events, [])
        self.assertIn('Could not read tasks', panel.briefing.text())


if __name__ == '__main__':
    unittest.main()
