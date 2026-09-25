"""Offline multilingual recognition with explicit, preinstalled Whisper weights."""
import io
from pathlib import Path
import sys
import wave

from .config import SafeError
from .core import redact
from .languages import SpeechTurn, supported_language
from .public_data import check_cancel


def model_directory():
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    return root / "models" / "faster-whisper-base"


class LocalRecognizer:
    def __init__(self, path=None):
        self.path = Path(path) if path else model_directory()
        self.model = None

    def transcribe(self, audio, previous_language=None, cancel=None):
        check_cancel(cancel)
        if not 4800 <= len(audio) <= 1_440_000:
            raise SafeError("Record between 0.1 and 30 seconds of audio.")
        if self.model is None:
            if not (self.path / "model.bin").is_file():
                raise SafeError("Run the demo setup script again to download the multilingual speech model.")
            try:
                from faster_whisper import WhisperModel
                self.model = WhisperModel(str(self.path), device="cpu", compute_type="int8", local_files_only=True)
            except Exception:
                raise SafeError("Could not load the local speech model. Rerun demo setup and check README.md.") from None
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(audio)

        def decode(language=None, task="transcribe"):
            buffer.seek(0)
            segments, info = self.model.transcribe(buffer, language=language, task=task, beam_size=5,
                                                   vad_filter=True, condition_on_previous_text=False)
            parts = []
            for segment in segments:
                check_cancel(cancel)
                if segment.no_speech_prob < 0.6 and segment.avg_logprob > -1.0:
                    parts.append(segment.text.strip())
            return " ".join(parts).strip(), info

        try:
            text, info = decode()
            check_cancel(cancel)
            if not text:
                raise SafeError("No speech recognized locally. Please record your answer again.")
            # Short shared words cannot reliably identify a language. Keep the session language.
            ambiguous = text.lower().strip(" .!?") in {"no", "ok", "okay", "yes"}
            if ambiguous and previous_language:
                language = supported_language(previous_language)
            elif info.language_probability < 0.6:
                raise SafeError("I couldn't identify the language confidently. Please say a full sentence in English, Spanish, or Bengali.")
            else:
                language = supported_language(info.language)
            english = text
            if language != "en":
                english, _ = decode(language=language, task="translate")
                if not english:
                    raise SafeError("I couldn't understand that answer. Please try again with a full sentence.")
            check_cancel(cancel)
            return SpeechTurn(redact(english), language)
        except SafeError:
            raise
        except Exception:
            raise SafeError("Local multilingual recognition failed. Please retry or check the demo setup.") from None
