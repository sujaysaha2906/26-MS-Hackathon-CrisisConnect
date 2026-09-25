import threading
import unittest
from unittest.mock import Mock, patch

from crisisconnect.config import SafeError
from crisisconnect.demo import DemoConversation, LocalVoice, run_local
from crisisconnect.languages import SpeechTurn
import main


class DemoTests(unittest.TestCase):
    def test_basic_chat_needs_no_network(self):
        with patch("socket.socket.connect", side_effect=AssertionError("Demo attempted network access")):
            chat = DemoConversation()
            chat = chat.advance("hello")
            self.assertIn("Hello", chat.prompt)
            chat = chat.advance("I feel worried")
            self.assertIn("biggest concern", chat.prompt)
            chat = chat.advance("My home flooded")
            self.assertIn("safe to stay", chat.prompt)
            chat = chat.advance("thank you")
            self.assertIn("welcome", chat.prompt)
            chat = chat.advance("goodbye")
            self.assertTrue(chat.complete)

    def test_demo_does_not_keep_answers_and_new_session_resets(self):
        chat = DemoConversation().advance("My name is Jane, ID 123-45-6789")
        self.assertNotIn("Jane", str(vars(chat)))
        self.assertNotIn("123-45-6789", str(vars(chat)))
        self.assertEqual(chat.turns, 1)
        self.assertEqual(DemoConversation().turns, 0)

    def test_cancel_and_blank_answer_do_not_advance(self):
        chat = DemoConversation()
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(SafeError):
            chat.advance("hello", cancel)
        with self.assertRaises(SafeError):
            chat.advance(" ")
        self.assertEqual(chat.turns, 0)

    def test_demo_launch_bypasses_config_and_azure(self):
        with patch("sys.argv", ["main.py", "--demo"]), \
             patch("main.Settings.from_file", side_effect=AssertionError("Demo read live config")), \
             patch("main.AzureServices", side_effect=AssertionError("Demo initialized Azure")), \
             patch("tkinter.Tk") as root, patch("crisisconnect.gui.App") as app:
            self.assertEqual(main.main(), 0)
            self.assertEqual(app.call_args.args[1].mode, "demo")
            self.assertIsInstance(app.call_args.args[2], LocalVoice)
            root.return_value.mainloop.assert_called_once()

    def test_live_mode_still_requires_config(self):
        with patch("sys.argv", ["main.py", "--live"]), \
             patch("main.Settings.from_file", side_effect=SafeError("Missing config")) as config, \
             patch("sys.stderr"):
            self.assertEqual(main.main(), 1)
            config.assert_called_once_with("live")

    def test_demo_uses_multilingual_recognizer(self):
        voice = LocalVoice()
        voice.recognizer = Mock()
        voice.recognizer.transcribe.return_value = SpeechTurn("I am worried", "bn")
        result = voice.transcribe_turn(b"audio", previous_language="en")
        self.assertEqual(result.language, "bn")
        voice.recognizer.transcribe.assert_called_once_with(b"audio", "en", None)

    def test_speech_content_is_stdin_not_shell_code(self):
        text = "Hello $(do-not-run) `example`"
        import json
        with patch("crisisconnect.demo.sys.platform", "win32"), patch("crisisconnect.demo.shutil.which", return_value=None), \
             patch("crisisconnect.demo.Path.is_file", return_value=False), patch("crisisconnect.demo.run_local") as runner:
            LocalVoice().speak(text)
        command, payload, _ = runner.call_args.args
        self.assertNotIn(text, command[-1])
        self.assertEqual(json.loads(payload)["text"], text)

    def test_silent_recognition_allows_retry(self):
        voice = LocalVoice()
        with patch.object(voice.recognizer, "transcribe", side_effect=SafeError("No speech recognized locally")):
            with self.assertRaisesRegex(SafeError, "No speech recognized locally"):
                voice.transcribe(b"\x00" * 4800)

    def test_cancelled_speech_does_not_start_process(self):
        cancel = threading.Event()
        cancel.set()
        with patch("crisisconnect.demo.subprocess.Popen") as process:
            with self.assertRaises(SafeError):
                run_local(["unused"], "hello", cancel)
            process.assert_not_called()
