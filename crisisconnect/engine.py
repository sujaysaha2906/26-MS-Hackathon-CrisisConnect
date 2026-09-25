from datetime import date
from .core import demo_intent, load_json, make_plan, redact
from .config import SafeError

DEMO_DATE = date(2026, 9, 23)


class Engine:
    def __init__(self, settings, azure, voice):
        self.settings, self.azure, self.voice = settings, azure, voice

    def reply(self, session, text, cancel=None):
        session.validate()
        if cancel and cancel.is_set():
            raise SafeError("Operation cancelled.")
        text = redact(text)
        if self.settings.mode == "demo":
            if session.language == "bn":
                raise SafeError("Bengali translation needs live Azure mode. Offline demonstration supports English and Spanish.")
            intent = demo_intent(text)
        else:
            intent = self.voice.classify(text, cancel=cancel)
        session.needs.update(intent["needs"])
        session.urgent = session.urgent or intent["urgent"]
        if cancel and cancel.is_set():
            raise SafeError("Operation cancelled.")
        if self.settings.mode == "demo":
            records = load_json("resources.json")
        else:
            records = self.azure.search(session)  # Failure is visible, no stale silent fallback.
        plan = make_plan(session, records, self.settings.mode,
                         today=DEMO_DATE if self.settings.mode == "demo" else None)
        if cancel and cancel.is_set():
            raise SafeError("Operation cancelled.")
        if self.settings.mode == "live" and session.language != "en":
            plan = self.azure.translate(plan, session.language)
        return {"plan": plan, "intent": intent, "records": records, "safe_input": text}
