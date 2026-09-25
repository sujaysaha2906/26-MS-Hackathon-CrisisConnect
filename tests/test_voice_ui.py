import queue
import threading
import unittest
from unittest.mock import Mock

from crisisconnect.gui import App
from crisisconnect.workflow import Workflow
from crisisconnect.config import Settings


class VoiceUITests(unittest.TestCase):
    def app(self):
        app = App.__new__(App)
        app.root = Mock()
        app.status = Mock()
        app.language = "en"
        app.language_label = Mock()
        app.controls = Mock()
        app.recorder = Mock()
        app.results = queue.Queue()
        app.cancel = threading.Event()
        app.generation = 0
        app.closed = False
        app.busy = False
        app.recording = False
        app.timer = None
        app.interview = Workflow(Settings(), Mock(), Mock(), Mock(), Mock())
        return app

    def test_end_cancels_capture_and_clears_answers(self):
        app = self.app()
        app.interview.history.append({"question": "situation", "answer": "My home flooded"})
        app.recording, app.busy, app.timer = True, True, "timer"
        app.end()
        self.assertTrue(app.cancel.is_set())
        self.assertIsNone(app.interview)
        self.assertFalse(app.recording)
        self.assertFalse(app.busy)
        app.recorder.stop.assert_called_once()
        app.root.after_cancel.assert_called_once_with("timer")

    def test_late_transcription_cannot_restart_ended_session(self):
        app = self.app()
        callback = Mock()
        app.results.put((app.generation, app.cancel, (True, "old answer"), callback))
        app.end()
        app.poll()
        callback.assert_not_called()
        self.assertIsNone(app.interview)

    def test_completed_conversation_clears_session(self):
        app = self.app()
        app.interview = app.interview.advance("yes")
        app.spoken(None)
        self.assertIsNone(app.interview)

    def test_repeat_does_not_advance_question(self):
        app = self.app()
        app.consent = Mock()
        app.consent.get.return_value = True
        app.run = Mock()
        first = app.interview.prompt
        app.repeat()
        self.assertEqual(app.interview.prompt, first)
        self.assertEqual(app.interview.history, [])
        app.run.assert_called_once()
