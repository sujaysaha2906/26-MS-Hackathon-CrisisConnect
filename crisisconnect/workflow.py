"""Wellbeing -> location -> FEMA -> bounded, non-confidential voice conversation."""
import copy
import json
import re

from .config import SafeError
from .core import redact
from .public_data import check_cancel, distance_km


CHAT_QUESTIONS = {
    "situation": "How is the disaster affecting you right now? Please keep it general and leave out personal details.",
    "shelter": "Do you have somewhere safe to stay?",
    "food": "Do you have access to food and drinking water?",
    "household": "Are you alone, or are other people with you? Please do not share their names.",
    "support": "What kind of practical support would help you most right now?",
    "anything_else": "Is there anything else about the situation you would like to discuss, without sharing private information?",
}
ASK_LOCATION = "What town or city and state are you in? Please say just the place names, not your address."
AGENT_REQUEST = re.compile(
    r"\b(?:human|agent|representative|real person)\b|\b(?:speak|talk) to (?:a |some)?(?:person|someone)\b", re.I)
URGENT_REQUEST = re.compile(r"\b(?:trapped|cannot breathe|can't breathe|immediate danger|medical emergency)\b", re.I)


def yes_no(text):
    value = re.sub(r"[^a-z ]", "", text.lower()).strip()
    if re.search(r"\b(no|not|unsafe|hurt|help|danger|unsure)\b", value):
        return False
    if re.fullmatch(r"(?:yes|yeah|yep|im okay|i am okay|im ok|i am ok|im fine|i am fine|okay|ok|correct|thats right|that is right)(?: thanks| thank you)?", value):
        return True
    if re.fullmatch(r"yes (?:im|i am) (?:okay|ok|fine)", value):
        return True
    return None


class Workflow:
    def __init__(self, settings, locations, places, fema, voice, handoff=None):
        self.settings, self.locations, self.places, self.fema, self.voice = settings, locations, places, fema, voice
        self.handoff = handoff
        self.stage = "wellbeing"
        self.prompt = "Are you okay? Please say yes or no."
        self.complete = False
        self.place = None
        self.retries = 0
        self.location_verified = False
        self.summary = ""
        self.history = []
        self.current_question = None
        self.handoff_requested = False

    def advance(self, text, cancel=None):
        # Commit only after external operations succeed; retries cannot half-advance a session.
        result = copy.copy(self)
        result.history = list(self.history)
        result.answer(text, cancel)
        # A transfer request cannot be rolled back if cancellation arrives just
        # after Call Automation accepts it.
        if not result.handoff_requested:
            check_cancel(cancel)
        return result

    def finish(self, message):
        self.stage, self.complete, self.prompt = "done", True, message
        self.place, self.summary, self.history = None, "", []

    def answer(self, text, cancel=None):
        check_cancel(cancel)
        if self.complete:
            raise SafeError("The conversation has ended.")
        if not text.strip():
            raise SafeError("No speech was recognized. Please try again.")
        normalized = text.lower().strip(" .!")
        if normalized in ("stop", "quit", "end", "end conversation", "goodbye"):
            self.finish("I'm here if you need me.")
            return
        if self.handoff is not None:
            reason = "urgent" if URGENT_REQUEST.search(text) else "human_requested" if AGENT_REQUEST.search(text) else None
            if reason:
                self.request_handoff(reason, cancel)
                return
        if self.stage == "wellbeing":
            okay = yes_no(text)
            if okay is True:
                self.finish("I am here if you need me.")
            elif okay is False:
                self.stage, self.prompt = "location", ASK_LOCATION
            else:
                self.prompt = "I want to make sure I understood. Are you okay? Please say yes or no."
        elif self.stage == "location":
            place = self.places.resolve(text, cancel)
            if place is None:
                self.location_retry("I couldn't identify that town and state.")
            else:
                self.place = place
                self.stage = "confirm_location"
                self.prompt = f"I heard {place.label}. Is that the location you mean? Please say yes or no."
        elif self.stage == "confirm_location":
            answer = yes_no(text)
            if answer is True:
                self.check_location(cancel)
            elif answer is False:
                self.location_retry("Let's correct the location.")
            else:
                self.prompt = f"Is {self.place.label} correct? Please say yes or no."
        elif self.stage == "location_choice":
            if normalized in ("continue", "continue without location", "skip", "skip location"):
                self.location_verified = False
                self.check_fema(cancel)
            elif normalized in ("retry", "check again", "turned on", "location is on", "i turned it on"):
                self.check_location(cancel)
            else:
                self.prompt = "Turn on location in your device settings and say check again, or say continue to use the town you gave me."
        elif self.stage == "chat":
            self.history.append({"question": self.current_question, "answer": redact(text)[:600]})
            if self.handoff is not None:
                intent = self.voice.classify(text, cancel=cancel)
                if intent["urgent"] or "human" in intent["needs"]:
                    reason = "urgent" if intent["urgent"] else "human_requested"
                    self.request_handoff(reason, cancel)
                    return
            self.next_question(cancel)

    def request_handoff(self, reason, cancel):
        self.handoff.transfer({"reason": reason, "summary": self.summary}, cancel=cancel)
        self.handoff_requested = True
        message = "I'm requesting a transfer to a support agent now."
        if reason == "urgent":
            message += " If you are in immediate danger or have a medical emergency, call 911."
        self.finish(message)

    def location_retry(self, reason):
        # This count is correction prompts AFTER the initial location attempt.
        if self.retries >= self.settings.location_max_retries:
            self.finish("I'm sorry, I couldn't confirm your location. We can try again another time. I am here if you need me.")
            return
        self.retries += 1
        self.place = None
        self.stage = "location"
        self.prompt = f"{reason} {ASK_LOCATION}"

    def check_location(self, cancel):
        reading = self.locations.read(cancel)
        if reading.status != "available":
            self.stage = "location_choice"
            reason = {"disabled": "Device location is turned off.",
                      "denied": "The app does not have permission to read your location."}.get(reading.status, "I couldn't get a reliable device location.")
            self.prompt = reason + " You can enable location in device settings and say check again, or say continue without it."
            return
        distance = distance_km((reading.latitude, reading.longitude), (self.place.latitude, self.place.longitude))
        if distance > self.settings.location_match_km:
            self.location_retry("The device location is more than ten kilometers from the town's reference point.")
            return
        self.location_verified = True
        self.check_fema(cancel)

    def check_fema(self, cancel):
        declaration = self.fema.find(self.place, cancel)
        if declaration is None:
            self.finish("I couldn't find a recent FEMA disaster declaration for that area. This does not mean the area is safe. I'll end this conversation here. I am here if you need me.")
            return
        self.summary = json.dumps({"wellbeing": "person reports not okay", "area": self.place.label,
                                   "device_location_verified": self.location_verified,
                                   "fema_declaration": declaration}, ensure_ascii=True)
        self.next_question(cancel)

    def next_question(self, cancel):
        asked = {item["question"] for item in self.history}
        available = [key for key in CHAT_QUESTIONS if key not in asked]
        if not available:
            self.finish("Thank you for talking with me. I am here if you need me.")
            return
        key = self.voice.next_question(self.summary, self.history, available, cancel=cancel)
        if key not in available:
            raise SafeError("The voice service returned an unexpected question. Please try again.")
        self.stage, self.current_question = "chat", key
        self.prompt = CHAT_QUESTIONS[key]
