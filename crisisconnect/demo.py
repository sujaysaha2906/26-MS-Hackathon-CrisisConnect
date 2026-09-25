"""Local-only demo conversation and offline speech adapters."""
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from .config import SafeError
from .public_data import check_cancel


class DemoConversation:
    def __init__(self):
        self.complete = False
        self.prompt = "Hi, I'm CrisisConnect. This is a local practice conversation. How are you feeling today?"
        self.turns = 0

    def advance(self, text, cancel=None):
        check_cancel(cancel)
        if self.complete:
            raise SafeError("The conversation has ended. Start a new one to chat again.")
        if not text.strip():
            raise SafeError("I didn't hear an answer. Please record again.")
        result = copy.copy(self)
        result.turns += 1
        words = set(re.findall(r"[a-z]+", text.lower()))
        if words.intersection({"stop", "quit", "goodbye", "bye"}):
            result.complete = True
            result.prompt = "Thank you for chatting. I am here if you need me."
        elif words.intersection({"worried", "scared", "afraid", "stressed", "sad", "anxious"}):
            result.prompt = "I'm sorry this feels difficult. I'm here to listen. What is your biggest concern right now?"
        elif words.intersection({"shelter", "home", "house", "flood", "fire"}):
            result.prompt = "That sounds difficult. Do you have somewhere safe to stay? Please keep your answer general."
        elif words.intersection({"food", "water", "hungry"}):
            result.prompt = "I hear that basic supplies are a concern. Is someone nearby able to support you?"
        elif words.intersection({"hello", "hi", "hey"}):
            result.prompt = "Hello! I'm here to listen. What would you like to talk about?"
        elif "thank" in words or "thanks" in words:
            result.prompt = "You're welcome. Would you like to talk about anything else? Say goodbye when you want to finish."
        elif words.intersection({"okay", "fine", "good", "well"}) and not words.intersection({"not", "no"}):
            result.prompt = "I'm glad to hear that. What would you like to talk about today?"
        elif {"can", "you"}.issubset(words) or "demo" in words:
            result.prompt = "In this demo I can listen and ask simple follow-up questions. I don't check disasters or arrange assistance. What would you like to discuss?"
        else:
            result.prompt = ("I'm listening. What kind of support would help you most right now?" if result.turns % 2
                             else "Thank you for sharing. Is there anything else you would like to talk about? Please leave out private details.")
        return result


def run_local(command, payload, cancel=None, timeout=60):
    """Send content over stdin, never through a shell or a file; cancel local playback promptly."""
    check_cancel(cancel)
    process = None
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        deadline = time.monotonic() + timeout
        pending = payload.encode("utf-8")
        while True:
            check_cancel(cancel)
            if time.monotonic() >= deadline:
                raise SafeError("Local speech took too long. Please try again.")
            try:
                stdout, _ = process.communicate(input=pending, timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                pending = None
        if process.returncode == 3:
            raise SafeError("No installed voice matches the detected language. Install eSpeak NG or a matching Windows desktop voice, then repeat the question.")
        if process.returncode:
            raise SafeError("Local speech failed. Check the demo speech setup in README.md and your audio device.")
        check_cancel(cancel)
        return stdout.decode("utf-8-sig").strip()
    except OSError:
        raise SafeError("Local speech tools are missing. Follow the demo setup in README.md.") from None
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate()


WINDOWS_SPEECH = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
    Add-Type -AssemblyName System.Speech
    $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
    try {
        $voice = $speaker.GetInstalledVoices() | Where-Object {
            $_.Enabled -and $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq $payload.language
        } | Select-Object -First 1
        if (-not $voice) { exit 3 }
        $speaker.SelectVoice($voice.VoiceInfo.Name)
        $speaker.Speak([string]$payload.text)
    } finally { $speaker.Dispose() }
} catch { exit 1 }
'''


class LocalVoice:
    def __init__(self, model_path=None):
        from .local_recognition import LocalRecognizer
        self.recognizer = LocalRecognizer(model_path)

    def windows(self, payload, cancel):
        return run_local(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", WINDOWS_SPEECH],
                         json.dumps(payload, ensure_ascii=True), cancel)

    def speak(self, text, cancel=None, language="en"):
        from .languages import supported_language
        language = supported_language(language)
        check_cancel(cancel)
        speaker = shutil.which("espeak-ng") or shutil.which("espeak")
        if not speaker and sys.platform == "win32":
            import os
            for variable in ("ProgramFiles", "ProgramFiles(x86)"):
                candidate = Path(os.environ.get(variable, "")) / "eSpeak NG" / "espeak-ng.exe"
                if candidate.is_file():
                    speaker = str(candidate)
                    break
        if speaker:
            # --stdin keeps text out of command parsing; -v selects the actual speech language.
            run_local([speaker, "--stdin", "-v", "en-us" if language == "en" else language, "-s", "155"], text, cancel)
        elif sys.platform == "win32":
            self.windows({"task": "speak", "text": text, "language": language}, cancel)
        else:
            raise SafeError("Install eSpeak NG for local speech in the detected language.")

    def transcribe_turn(self, audio, previous_language=None, cancel=None):
        return self.recognizer.transcribe(audio, previous_language, cancel)

    def transcribe(self, audio, language="en", cancel=None):
        return self.transcribe_turn(audio, language, cancel).text
