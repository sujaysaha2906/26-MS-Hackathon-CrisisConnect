"""Exercise the new Voice Live request contract without optional WebSocket packages."""
import json
import unittest
from unittest.mock import Mock

from crisisconnect.config import Settings, SafeError
from crisisconnect.voice import VoiceLive


class FakeSocket:
    def __init__(self, result):
        self.sent = []
        self.events = iter([
            {"type": "session.updated"},
            {"type": "response.text.delta", "delta": json.dumps(result)},
            {"type": "response.done", "response": {"status": "completed"}},
        ])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def send(self, value):
        self.sent.append(json.loads(value))

    async def recv(self):
        return json.dumps(next(self.events))


class InterviewVoiceTests(unittest.TestCase):
    def voice(self, result):
        self.socket = FakeSocket(result)
        tokens = Mock()
        tokens.token.return_value = "synthetic-token"
        return VoiceLive(Settings(voice_endpoint="https://example.services.ai.azure.com"), tokens,
                         connector=lambda *args, **kwargs: self.socket)

    def test_summary_and_allowed_keys_sent_and_response_validated(self):
        result = self.voice({"question": "situation"}).next_question("FEMA test summary", [], ["situation"])
        self.assertEqual(result, "situation")
        message = next(value for value in self.socket.sent if value["type"] == "conversation.item.create")
        payload = json.loads(message["item"]["content"][0]["text"])
        self.assertEqual(payload["summary"], "FEMA test summary")
        self.assertEqual(payload["allowed"], ["situation"])
        self.assertIn("Never request names", self.socket.sent[0]["session"]["instructions"])

    def test_unapproved_or_malformed_output_never_becomes_spoken_question(self):
        for output in ({"question": "bank account"}, {"question": "situation", "extra": "secret"}, []):
            with self.subTest(output=output), self.assertRaises(SafeError):
                self.voice(output).next_question("summary", [], ["situation"])
