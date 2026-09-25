import asyncio
import base64
import json
import threading
import unittest
try:
    import websockets
    from websockets.asyncio.server import serve
    from websockets.asyncio.client import connect
    HAS_WS=True
except ImportError:
    HAS_WS=False

from crisisconnect.config import Settings, SafeError
from crisisconnect.voice import VoiceLive


class Tokens:
    def token(self, scope): return "SYNTHETIC_TEST_TOKEN"


@unittest.skipUnless(HAS_WS, "Install websockets to run local WebSocket integration tests")
class VoiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events=[]
        self.reply_text='{"needs":["shelter"],"urgent":false}'
        self.speech=False
        self.error=False
        async def handler(ws):
            async for message in ws:
                value=json.loads(message); self.events.append(value)
                kind=value["type"]
                if kind=="session.update":
                    await ws.send(json.dumps({"type":"session.updated"}))
                elif kind=="input_audio_buffer.commit":
                    await ws.send(json.dumps({"type":"conversation.item.input_audio_transcription.completed","transcript":"I need shelter. My ID is 123-45-6789."}))
                elif kind=="response.create":
                    if self.error:
                        await ws.send(json.dumps({"type":"error","error":{"message":"PRIVATE TOKEN"}})); continue
                    await ws.send(json.dumps({"type":"response.audio_transcript.delta" if self.speech else "response.text.delta","delta":self.reply_text}))
                    if self.speech:
                        await ws.send(json.dumps({"type":"response.audio.delta","delta":base64.b64encode(b"\x00"*4800).decode()}))
                    await ws.send(json.dumps({"type":"response.done","response":{"status":"completed"}}))
        self.server=await serve(handler, "127.0.0.1", 0)
        port=self.server.sockets[0].getsockname()[1]
        def connector(url, **kwargs):
            self.original_url=url
            return connect(f"ws://127.0.0.1:{port}", **kwargs)
        self.voice=VoiceLive(Settings(voice_endpoint="https://test.services.ai.azure.com"),Tokens(),connector)

    async def asyncTearDown(self):
        self.server.close(); await self.server.wait_closed()

    async def test_classification_over_local_websocket(self):
        result=await self.voice.request("classify",text="I need shelter")
        self.assertEqual(result["needs"],["shelter"])
        self.assertIn("api-version=2026-04-10",self.original_url)
        self.assertNotIn("TOKEN",self.original_url)
        self.assertTrue(any(e["type"]=="conversation.item.create" for e in self.events))

    async def test_transcription_audio_protocol_and_redaction(self):
        result=await self.voice.request("transcribe",audio=b"\x00"*9600)
        self.assertNotIn("123-45-6789",result)
        chunks=[e for e in self.events if e["type"]=="input_audio_buffer.append"]
        self.assertEqual(sum(len(base64.b64decode(e["audio"])) for e in chunks),9600)
        self.assertFalse(any(e["type"]=="response.create" for e in self.events))

    async def test_unvalidated_spoken_words_blocked(self):
        self.speech=True; self.reply_text="You definitely qualify for money"
        with self.assertRaises(SafeError): await self.voice.request("speak",text="Please check the official source.")

    async def test_matching_spoken_text_releases_buffer(self):
        self.speech=True; self.reply_text="Please check the official source."
        result=await self.voice.request("speak",text=self.reply_text)
        self.assertEqual(len(result),4800)

    async def test_bad_ai_schema_blocked(self):
        self.reply_text='{"needs":["approve_award"],"urgent":false}'
        with self.assertRaises(SafeError): await self.voice.request("classify",text="hello")

    async def test_provider_error_is_sanitized(self):
        self.error=True
        with self.assertRaises(SafeError) as cm: await self.voice.request("classify",text="hello")
        self.assertNotIn("PRIVATE TOKEN",str(cm.exception))

    async def test_cancel_before_connect(self):
        cancel=threading.Event(); cancel.set()
        with self.assertRaises(SafeError): await self.voice.request("classify",text="hello",cancel=cancel)
        self.assertEqual(self.events,[])
