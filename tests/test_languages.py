import asyncio
import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

from crisisconnect.config import Settings, SafeError
from crisisconnect.demo import DemoConversation, LocalVoice
from crisisconnect.languages import SpeechTurn, localize, PROMPTS
from crisisconnect.local_recognition import LocalRecognizer
from crisisconnect.voice import VoiceLive
from crisisconnect.workflow import CHAT_QUESTIONS, ASK_LOCATION


def recognition(text, language="es", probability=0.95):
    return iter([SimpleNamespace(text=text, no_speech_prob=0.01, avg_logprob=-0.1)]), SimpleNamespace(language=language, language_probability=probability)


class RecognitionTests(unittest.TestCase):
    def recognizer(self, outputs):
        recognizer = LocalRecognizer()
        recognizer.model = Mock()
        recognizer.model.transcribe.side_effect = outputs
        return recognizer

    def test_detects_and_normalizes_spanish_and_bengali_offline(self):
        for language, phrase in (("es", "Estoy preocupado"), ("bn", "আমি চিন্তিত")):
            with self.subTest(language=language), patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
                recognizer = self.recognizer([recognition(phrase, language), recognition("I am worried", language)])
                turn = recognizer.transcribe(b"\x00" * 4800, "en")
                self.assertEqual(turn, SpeechTurn("I am worried", language))
                calls = recognizer.model.transcribe.call_args_list
                self.assertIsNone(calls[0].kwargs["language"])
                self.assertEqual(calls[1].kwargs["task"], "translate")
                self.assertEqual(calls[1].kwargs["language"], language)
                reply = DemoConversation().advance(turn.text)
                self.assertNotEqual(localize(reply.prompt, language), reply.prompt)

    def test_english_does_not_need_translation(self):
        recognizer = self.recognizer([recognition("Hello there", "en")])
        self.assertEqual(recognizer.transcribe(b"\x00" * 4800).language, "en")
        recognizer.model.transcribe.assert_called_once()

    def test_ambiguous_short_reply_keeps_previous_language(self):
        recognizer = self.recognizer([recognition("No.", "en", 0.3), recognition("No", "es")])
        self.assertEqual(recognizer.transcribe(b"\x00" * 4800, "es").language, "es")

    def test_uncertain_unsupported_or_silent_recording_is_not_english_fallback(self):
        for output in (recognition("unclear", "es", 0.2), recognition("bonjour", "fr"), recognition("", "en")):
            recognizer = self.recognizer([output])
            with self.assertRaises(SafeError):
                recognizer.transcribe(b"\x00" * 4800)

    def test_missing_model_never_downloads_during_conversation(self):
        with patch("pathlib.Path.is_file", return_value=False), patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
            with self.assertRaisesRegex(SafeError, "setup"):
                LocalRecognizer().transcribe(b"\x00" * 4800)

    def test_cancelled_input_skips_inference(self):
        recognizer = self.recognizer([])
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(SafeError):
            recognizer.transcribe(b"\x00" * 4800, cancel=cancel)
        recognizer.model.transcribe.assert_not_called()

    def test_model_receives_valid_in_memory_wav(self):
        recognizer = LocalRecognizer()
        recognizer.model = Mock()
        def inspect(buffer, **kwargs):
            with wave.open(buffer, "rb") as wav:
                self.assertEqual((wav.getframerate(), wav.getnchannels(), wav.getsampwidth()), (24000, 1, 2))
            return recognition("hello", "en")
        recognizer.model.transcribe.side_effect = inspect
        self.assertEqual(recognizer.transcribe(b"\x00" * 4800).text, "hello")


class ReplyLanguageTests(unittest.TestCase):
    def test_all_registered_prompts_have_nonempty_translations(self):
        for source in PROMPTS:
            for language in ("es", "bn"):
                self.assertTrue(localize(source, language))
                self.assertNotEqual(localize(source, language), source)
        for source in CHAT_QUESTIONS.values():
            self.assertIn(source, PROMPTS)

    def test_compound_location_prompts_and_place_names(self):
        for reason in ("I couldn't identify that town and state.", "Let's correct the location.", "The device location is more than ten kilometers from the town's reference point."):
            for language in ("es", "bn"):
                self.assertNotIn(ASK_LOCATION, localize(reason + " " + ASK_LOCATION, language))
        for language in ("es", "bn"):
            self.assertIn("Richmond city, VA", localize("I heard Richmond city, VA. Is that the location you mean? Please say yes or no.", language))

    def test_missing_translation_fails_instead_of_speaking_english(self):
        with self.assertRaises(SafeError):
            localize("Unexpected prompt", "bn")

    def test_espeak_receives_matching_voice(self):
        with patch("crisisconnect.demo.shutil.which", return_value="espeak-ng"), patch("crisisconnect.demo.run_local") as run:
            LocalVoice().speak("হ্যালো", language="bn")
        self.assertEqual(run.call_args.args[0][3], "bn")
        self.assertEqual(run.call_args.args[1], "হ্যালো")


class LiveLanguageTests(unittest.TestCase):
    def test_live_detection_propagates_language_and_english_interpretation(self):
        voice = VoiceLive(Settings(), Mock())
        voice.transcribe = Mock(return_value="আমি ভালো নেই")
        async def request(task, **kwargs):
            self.assertEqual(task, "normalize")
            payload = json.loads(kwargs["text"])
            self.assertEqual(payload["previous_language"], "en")
            return SpeechTurn("I am not okay", "bn")
        voice.request = request
        self.assertEqual(voice.transcribe_turn(b"audio", "en"), SpeechTurn("I am not okay", "bn"))

    def test_bengali_azure_voice_and_automatic_transcription_config(self):
        import base64
        class Socket:
            sent = []
            async def __aenter__(self):
                self.events = iter([{"type": "session.updated"}, {"type": "response.audio_transcript.delta", "delta": "হ্যালো"},
                                    {"type": "response.audio.delta", "delta": base64.b64encode(b"\x00" * 4800).decode()},
                                    {"type": "response.done", "response": {"status": "completed"}}])
                return self
            async def __aexit__(self, *args): pass
            async def send(self, value): self.sent.append(json.loads(value))
            async def recv(self): return json.dumps(next(self.events))
        socket = Socket()
        services = Mock()
        services.token.return_value = "synthetic"
        voice = VoiceLive(Settings(voice_endpoint="https://example.services.ai.azure.com"), services, connector=lambda *a, **k: socket)
        asyncio.run(voice.request("speak", text="হ্যালো", language="bn"))
        session = socket.sent[0]["session"]
        self.assertEqual(session["voice"]["name"], "bn-BD-NabanitaNeural")
        self.assertEqual(session["input_audio_transcription"]["model"], "mai-transcribe")
        self.assertNotIn("language", session["input_audio_transcription"])
