import base64
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from screen_assist import ScreenAssistant, VisionRequest, image_payload


class ScreenAssistanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_image_encoding_and_size_limit(self):
        image = QImage(2400, 1200, QImage.Format_RGB32)
        image.fill(Qt.blue)
        decoded = QImage.fromData(base64.b64decode(image_payload(image)))
        self.assertEqual((decoded.width(), decoded.height()), (1600, 800))
        with self.assertRaises(ValueError):
            image_payload(QImage())

    def test_no_image_no_network_and_explicit_clear(self):
        panel = ScreenAssistant()
        self.addCleanup(panel.close)
        with patch('screen_assist.VisionRequest') as request:
            panel.analyze()
            request.assert_not_called()
            image = QImage(80, 40, QImage.Format_RGB32)
            image.fill(Qt.red)
            panel.set_image(image)
            request.assert_not_called()
            self.assertIn('not sent', panel.status.text())
            panel.append_token('<b>Untrusted screenshot text</b>')
            self.assertEqual(panel.answer.toPlainText(), '<b>Untrusted screenshot text</b>')
            panel.clear_image()
            self.assertTrue(panel.image.isNull())
            self.assertEqual(panel.answer.toPlainText(), '')

    def test_local_ollama_protocol_streaming(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200)
                self.end_headers()
                for row in ({'message': {'content': 'A blue '}, 'done': False},
                            {'message': {'content': 'screen'}, 'done': True}):
                    self.wfile.write(json.dumps(row).encode() + b'\n')
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            worker = VisionRequest('llava', 'Explain this', 'aW1hZ2U=', endpoint=f'http://127.0.0.1:{server.server_port}/api/chat')
            tokens = QSignalSpy(worker.token)
            done = QSignalSpy(worker.succeeded)
            failed = QSignalSpy(worker.failed)
            worker.start()
            self.assertTrue(worker.wait(5000))
            self.app.processEvents()
            self.assertEqual(done.count(), 1)
            self.assertEqual(failed.count(), 0)
            self.assertEqual(tokens.at(0)[0] + tokens.at(1)[0], 'A blue screen')
            self.assertEqual(received[0]['messages'][1]['images'], ['aW1hZ2U='])
            self.assertTrue(received[0]['stream'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_connection_error_and_cancellation(self):
        worker = VisionRequest('llava', 'Question', 'image')
        failures = QSignalSpy(worker.failed)
        with patch('screen_assist.urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect = OSError('connection refused')
            worker.run()
        self.assertEqual(failures.count(), 1)
        self.assertIn('Start Ollama', failures.at(0)[0])
        with patch('screen_assist.urllib.request.build_opener') as opener:
            worker.requestInterruption()
            # QThread interruption applies only once it is running; test the branch directly.
            with patch.object(worker, 'isInterruptionRequested', return_value=True):
                worker.run()
        self.assertIn('cancelled', failures.at(1)[0])

    def test_theme_and_screen_workspace_integration(self):
        import jarvis_hud as h
        with patch.object(h.JarvisHUD, 'refresh_weather'):
            win = h.JarvisHUD()
        self.addCleanup(win.close)
        win.open_screen_assistant()
        self.assertTrue(win.screen_assistant.isVisible())
        for name in ('AMETHYST', 'EMBER', 'CYAN'):
            win.cycle_theme()
            self.assertIn(name, win.theme_button.text())
        win.screen_assistant.close()


if __name__ == '__main__':
    unittest.main()
