import copy
from datetime import date
import threading
import unittest
from unittest.mock import patch

from crisisconnect.config import Settings, SafeError, endpoint
from crisisconnect.core import Session, demo_intent, validate_intent, redact, load_json, make_plan, usable_record, plan_hash
from crisisconnect.engine import Engine, DEMO_DATE
from crisisconnect.delivery import Delivery, Approval


class Forbidden:
    def __getattr__(self, name):
        raise AssertionError("Offline mode attempted a cloud operation: " + name)


class CoreTests(unittest.TestCase):
    def test_demo_scenarios_are_network_free(self):
        engine = Engine(Settings(), Forbidden(), Forbidden())
        with patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
            for key, scenario in load_json("scenarios.json").items():
                with self.subTest(key=key):
                    s = Session(state=scenario["state"], county=scenario["county"], event=scenario["event"], incident_date=scenario["incident_date"])
                    result = engine.reply(s, scenario["text"])
                    self.assertTrue(set(scenario["expected_needs"]).issubset(s.needs))
                    self.assertIn("SIMULATION", result["plan"])
                    self.assertIn("No eligibility", result["plan"])
                    if key == "urgent": self.assertIn("PRIORITY", result["plan"])

    def test_spanish_offline_plan(self):
        s = Session(language="es")
        result = Engine(Settings(), Forbidden(), Forbidden()).reply(s, "Necesito comida y refugio")
        self.assertIn("SU PLAN DE ACCIÓN", result["plan"])
        self.assertEqual(set(result["intent"]["needs"]), {"food", "shelter"})

    def test_bengali_demo_does_not_fake_translation(self):
        with self.assertRaises(SafeError):
            Engine(Settings(), Forbidden(), Forbidden()).reply(Session(language="bn"), "food")

    def test_redacts_common_identifiers(self):
        out = redact("SSN 123-45-6789 email person@example.com phone +12025550123")
        for private in ("123-45-6789", "person@example.com", "+12025550123"):
            self.assertNotIn(private, out)

    def test_unknown_intent_goes_to_human(self):
        self.assertEqual(demo_intent("I don't know what to ask")["needs"], ["human"])

    def test_strict_ai_schema(self):
        for value in ({"needs":["send_sms"],"urgent":False}, {"needs":[],"urgent":False},
                      {"needs":["food"],"urgent":"false"}, {"needs":["food"],"urgent":False,"send":"x"}):
            with self.subTest(value=value), self.assertRaises(ValueError): validate_intent(value)

    def test_record_filters(self):
        r = load_json("resources.json")[0]
        self.assertTrue(usable_record(r, "VA", "Richmond city", DEMO_DATE))
        changes = [{"is_demo":True}, {"approved":False}, {"state":"CA"}, {"county":"Another county"},
                   {"source_url":"https://www.usa.gov.evil.example/help"}, {"source_url":"http://www.usa.gov/help"},
                   {"reviewed_at":"2020-01-01"}, {"reviewed_at":"2099-01-01"}, {"expires_on":"2026-09-01"},
                   {"reviewed_at":"invalid"}, {"need":"approve"}]
        for change in changes:
            with self.subTest(change=change): self.assertFalse(usable_record({**r, **change}, "VA", "Richmond city", DEMO_DATE))

    def test_empty_or_stale_results_never_confirm_eligibility(self):
        plan = make_plan(Session(needs={"food"}), [], "live", today=DEMO_DATE)
        self.assertIn("No current approved matching record", plan)
        self.assertIn("No eligibility", plan)

    def test_bad_location_and_future_date_rejected(self):
        for s in (Session(state="UK"), Session(county=""), Session(incident_date="2099-01-01"), Session(incident_date="09/20/26")):
            with self.subTest(s=s), self.assertRaises(ValueError): s.validate()

    def test_cancelled_request_does_not_call_azure(self):
        cancelled = threading.Event(); cancelled.set()
        with self.assertRaises(SafeError): Engine(Settings(mode="live"), Forbidden(), Forbidden()).reply(Session(), "food", cancelled)

    def test_endpoint_rejects_credential_leak_targets(self):
        for url in ("http://x.services.ai.azure.com", "https://evil.example", "https://x.services.ai.azure.com.evil.com",
                    "https://user:password@x.services.ai.azure.com", "https://x.services.ai.azure.com?api-key=secret"):
            with self.subTest(url=url), self.assertRaises(SafeError): endpoint(url, (".services.ai.azure.com",))


class DeliveryTests(unittest.TestCase):
    def approval(self, body="A test action plan", target="tester@example.com", consent=True):
        return Approval("email", target, plan_hash(body), consent)

    def test_demo_never_calls_provider(self):
        result = Delivery(Settings(), Forbidden()).send("A test action plan", self.approval())
        self.assertEqual(result["status"], "simulated")

    def test_missing_consent_blocks(self):
        with self.assertRaises(SafeError): Delivery(Settings(), Forbidden()).send("A test action plan", self.approval(consent=False))

    def test_edited_summary_requires_new_approval(self):
        with self.assertRaises(SafeError): Delivery(Settings(), Forbidden()).send("A different plan", self.approval())

    def test_duplicate_attempt_blocks(self):
        d = Delivery(Settings(), Forbidden())
        d.send("A test action plan", self.approval())
        with self.assertRaises(SafeError): d.send("A test action plan", self.approval())

    def test_live_disabled_blocks(self):
        with self.assertRaises(SafeError): Delivery(Settings(mode="live"), Forbidden()).send("A test action plan", self.approval())

    def test_unlisted_recipient_blocks(self):
        with self.assertRaises(SafeError):
            Delivery(Settings(mode="live", delivery_enabled=True, test_recipients=("other@example.com",)), Forbidden()).send("A test action plan", self.approval())

    def test_unknown_provider_result_cannot_auto_retry(self):
        class Failing:
            calls = 0
            def email(self, dest, body):
                self.calls += 1
                raise SafeError("Unknown outcome")
        provider = Failing()
        d = Delivery(Settings(mode="live", delivery_enabled=True, test_recipients=("tester@example.com",)), provider)
        for _ in range(2):
            with self.assertRaises(SafeError): d.send("A test action plan", self.approval())
        self.assertEqual(provider.calls, 1)

    def test_sms_size_limit(self):
        body = "a" * 1401
        a = Approval("sms", "+12025550123", plan_hash(body), True)
        with self.assertRaises(SafeError): Delivery(Settings(), Forbidden()).send(body, a)

    def test_bad_destination(self):
        with self.assertRaises(SafeError): Delivery(Settings(), Forbidden()).send("A test action plan", self.approval(target="bad"))
