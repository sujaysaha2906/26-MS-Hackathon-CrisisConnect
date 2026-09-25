from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit


class SafeError(Exception):
    """An actionable message safe to show without credentials or provider payloads."""


def endpoint(value, suffixes):
    p = urlsplit(value)
    if (p.scheme != "https" or not p.hostname or p.username or p.password
            or p.query or p.fragment or p.port not in (None, 443)
            or not any(p.hostname.endswith(s) for s in suffixes)):
        raise SafeError("Endpoint must be an HTTPS Azure resource URL. Check configuration.")
    return value.rstrip("/")


@dataclass(frozen=True)
class Settings:
    mode: str = "demo"
    voice_endpoint: str = ""
    voice_model: str = "gpt-4.1-mini"
    voice_api: str = "2026-04-10"
    voice_name: str = "en-US-AvaNeural"
    location_max_retries: int = 3
    location_match_km: float = 10.0
    fema_lookback_days: int = 30
    translator_endpoint: str = ""
    search_endpoint: str = ""
    search_index: str = "crisisconnect-assistance"
    search_api: str = "2024-07-01"
    acs_endpoint: str = ""
    email_sender: str = ""
    sms_sender: str = ""
    delivery_enabled: bool = False
    test_recipients: tuple = ()

    @classmethod
    def from_file(cls, mode="live", path=None):
        if path is None:
            root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
            path = root / "config.json"
        try:
            values = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise SafeError("Cannot read config.json. Ensure it exists and contains valid JSON.") from None
        if not isinstance(values, dict):
            raise SafeError("config.json must contain a JSON object.")
        fields = {
            "AZURE_VOICELIVE_ENDPOINT": "voice_endpoint",
            "AZURE_VOICELIVE_MODEL": "voice_model",
            "AZURE_VOICELIVE_API_VERSION": "voice_api",
            "AZURE_VOICELIVE_VOICE": "voice_name",
        }
        options = {}
        for key, field, maximum in (
            ("LOCATION_MAX_RETRIES", "location_max_retries", 20),
            ("FEMA_LOOKBACK_DAYS", "fema_lookback_days", 365),
        ):
            if key in values:
                value = values[key]
                if type(value) is not int or not 1 <= value <= maximum:
                    raise SafeError(f"{key} in config.json must be an integer from 1 to {maximum}.")
                options[field] = value
        for key, field in fields.items():
            if key in values:
                if not isinstance(values[key], str) or (key != "AZURE_VOICELIVE_ENDPOINT" and not values[key].strip()):
                    raise SafeError(f"{key} in config.json must be a nonempty string.")
                options[field] = values[key].strip()
        if options.get("voice_endpoint"):
            try:
                options["voice_endpoint"] = endpoint(options["voice_endpoint"], (".services.ai.azure.com", ".cognitiveservices.azure.com"))
            except ValueError:
                raise SafeError("AZURE_VOICELIVE_ENDPOINT in config.json must be a valid Azure HTTPS URL.") from None
        return cls(mode=mode, **options)

    @classmethod
    def from_env(cls, mode="demo"):
        e = os.environ
        return cls(mode=mode,
            voice_endpoint=e.get("AZURE_VOICELIVE_ENDPOINT", ""),
            voice_model=e.get("AZURE_VOICELIVE_MODEL", "gpt-4.1-mini"),
            voice_api=e.get("AZURE_VOICELIVE_API_VERSION", "2026-04-10"),
            voice_name=e.get("AZURE_VOICELIVE_VOICE", "en-US-AvaNeural"),
            translator_endpoint=e.get("AZURE_TRANSLATOR_ENDPOINT", ""),
            search_endpoint=e.get("AZURE_SEARCH_ENDPOINT", ""),
            search_index=e.get("AZURE_SEARCH_INDEX", "crisisconnect-assistance"),
            search_api=e.get("AZURE_SEARCH_API_VERSION", "2024-07-01"),
            acs_endpoint=e.get("AZURE_COMMUNICATION_ENDPOINT", ""),
            email_sender=e.get("ACS_EMAIL_SENDER", ""),
            sms_sender=e.get("ACS_SMS_SENDER", ""),
            delivery_enabled=e.get("CRISISCONNECT_ENABLE_DELIVERY", "0") == "1",
            test_recipients=tuple(x.strip() for x in e.get("CRISISCONNECT_TEST_RECIPIENTS", "").split(",") if x.strip()))

    def checks(self):
        return {"Mode": self.mode,
                "Voice Live endpoint": bool(self.voice_endpoint),
                "Translator endpoint": bool(self.translator_endpoint),
                "AI Search endpoint": bool(self.search_endpoint),
                "ACS endpoint": bool(self.acs_endpoint),
                "Real delivery enabled": self.delivery_enabled,
                "Tester allowlist configured": bool(self.test_recipients)}
