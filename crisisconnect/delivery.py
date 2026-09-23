"""Explicit tester-only send guard. No model can call this module autonomously."""
from dataclasses import dataclass
import re
import threading

from .config import SafeError
from .core import plan_hash, redact


@dataclass(frozen=True)
class Approval:
    channel: str
    destination: str
    body_hash: str
    consent: bool


def validate_destination(channel, destination):
    if channel == "email":
        ok = re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", destination)
    elif channel == "sms":
        ok = re.fullmatch(r"\+[1-9]\d{7,14}", destination)
    else:
        ok = False
    if not ok:
        raise SafeError("Enter a valid email or an international phone number such as +12025550123.")


class Delivery:
    def __init__(self, settings, services):
        self.settings, self.services = settings, services
        self.used = set()
        self.lock = threading.Lock()

    def send(self, body, approval):
        validate_destination(approval.channel, approval.destination)
        if not approval.consent or approval.body_hash != plan_hash(body):
            raise SafeError("Review the current message and explicitly approve this exact version before sending.")
        if not body.strip() or len(body) > (1400 if approval.channel == "sms" else 12000):
            raise SafeError("Message is empty or too long. SMS maximum is 1,400 characters; email maximum is 12,000.")
        if self.settings.mode == "live":
            if not self.settings.delivery_enabled:
                raise SafeError("Real delivery is disabled. Operator must set CRISISCONNECT_ENABLE_DELIVERY=1.")
            if approval.destination not in self.settings.test_recipients:
                raise SafeError("Destination is not in the operator's explicit tester allowlist.")
        key = (approval.channel, plan_hash(approval.destination), approval.body_hash)
        with self.lock:
            if key in self.used:
                raise SafeError("This exact send was already attempted in this app run. Check status instead of retrying.")
            self.used.add(key)  # Retain even on ambiguous failure; never auto-retry.
        if self.settings.mode == "demo":
            return {"status": "simulated", "id": "demo-only", "detail": "Nothing was transmitted. This is an offline delivery preview."}
        return getattr(self.services, approval.channel)(approval.destination, body)
