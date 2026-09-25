import threading
import unittest
from unittest.mock import Mock, patch

from crisisconnect.config import Settings, SafeError
from crisisconnect.device_location import LocationReading, validated_reading
from crisisconnect.public_data import Place, distance_km
from crisisconnect.workflow import Workflow, CHAT_QUESTIONS


PLACE = Place("Richmond city, VA", "VA", "51", "760", 37.54, -77.43)
DECLARATION = {"disasterNumber": 1234, "incidentType": "Flood", "declarationTitle": "Test flood"}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.locations, self.places, self.fema, self.voice = Mock(), Mock(), Mock(), Mock()
        self.places.resolve.return_value = PLACE
        self.locations.read.return_value = LocationReading("available", PLACE.latitude, PLACE.longitude, 20)
        self.fema.find.return_value = DECLARATION
        self.voice.next_question.side_effect = lambda summary, history, available, cancel=None: available[0]
        self.flow = Workflow(Settings(), self.locations, self.places, self.fema, self.voice)

    def step(self, text):
        self.flow = self.flow.advance(text)

    def location(self):
        self.step("No")
        self.step("Richmond, Virginia")

    def test_okay_exits_without_location_fema_or_ai(self):
        self.step("Yes, I am okay")
        self.assertTrue(self.flow.complete)
        self.assertEqual(self.flow.prompt, "I am here if you need me.")
        self.locations.read.assert_not_called()
        self.places.resolve.assert_not_called()
        self.fema.find.assert_not_called()
        self.voice.next_question.assert_not_called()

    def test_ambiguous_answer_does_not_quit(self):
        self.step("I don't know")
        self.assertFalse(self.flow.complete)
        self.assertEqual(self.flow.stage, "wellbeing")

    def test_negative_overrides_yes(self):
        self.step("Yes but I am not okay")
        self.assertEqual(self.flow.stage, "location")

    def test_verified_disaster_starts_ai_with_summary_not_coordinates(self):
        self.location()
        self.voice.next_question.assert_not_called()
        self.step("Yes")
        self.assertEqual(self.flow.stage, "chat")
        self.assertTrue(self.flow.location_verified)
        summary = self.voice.next_question.call_args.args[0]
        self.assertIn("Test flood", summary)
        self.assertNotIn(str(PLACE.latitude), summary)
        self.assertNotIn(str(PLACE.longitude), summary)
        self.assertEqual(self.flow.prompt, CHAT_QUESTIONS["situation"])

    def test_off_denied_and_unavailable_allow_explicit_continue(self):
        for status in ("disabled", "denied", "unavailable"):
            with self.subTest(status=status):
                self.setUp()
                self.locations.read.return_value = LocationReading(status)
                self.location()
                self.step("Yes")
                self.fema.find.assert_not_called()
                self.assertEqual(self.flow.stage, "location_choice")
                self.step("continue")
                self.assertFalse(self.flow.location_verified)
                self.assertEqual(self.flow.stage, "chat")

    def test_enable_and_recheck(self):
        self.locations.read.return_value = LocationReading("disabled")
        self.location()
        self.step("yes")
        self.locations.read.return_value = LocationReading("available", PLACE.latitude, PLACE.longitude, 20)
        self.step("check again")
        self.assertEqual(self.flow.stage, "chat")
        self.assertTrue(self.flow.location_verified)

    def test_mismatch_stops_after_three_corrections(self):
        self.locations.read.return_value = LocationReading("available", 0, 0, 20)
        self.location()
        for index in range(4):
            self.step("yes")
            if index < 3:
                self.assertFalse(self.flow.complete)
                self.step("Richmond, Virginia")
        self.assertTrue(self.flow.complete)
        self.assertEqual(self.flow.retries, 3)
        self.fema.find.assert_not_called()

    def test_retry_limit_is_configurable(self):
        self.flow.settings = Settings(location_max_retries=1)
        self.places.resolve.return_value = None
        self.step("no")
        self.step("unknown")
        self.assertFalse(self.flow.complete)
        self.step("unknown")
        self.assertTrue(self.flow.complete)

    def test_ten_km_boundary(self):
        for distance, stage in ((10.0, "chat"), (10.001, "location")):
            self.setUp()
            self.location()
            with patch("crisisconnect.workflow.distance_km", return_value=distance):
                self.step("yes")
            self.assertEqual(self.flow.stage, stage)

    def test_no_declaration_quits_without_ai(self):
        self.fema.find.return_value = None
        self.location()
        self.step("yes")
        self.assertTrue(self.flow.complete)
        self.assertIn("does not mean the area is safe", self.flow.prompt)
        self.voice.next_question.assert_not_called()

    def test_service_failure_is_retryable_not_no_disaster(self):
        self.fema.find.side_effect = SafeError("Unavailable")
        self.location()
        with self.assertRaises(SafeError):
            self.step("yes")
        self.assertEqual(self.flow.stage, "confirm_location")
        self.assertFalse(self.flow.complete)
        self.voice.next_question.assert_not_called()

    def test_ai_cannot_invent_confidential_questions(self):
        self.location()
        self.voice.next_question.side_effect = None
        self.voice.next_question.return_value = "What is your bank account number?"
        with self.assertRaises(SafeError):
            self.step("yes")
        self.assertEqual(self.flow.stage, "confirm_location")

    def test_conversation_finishes_and_clears_answers(self):
        self.location()
        self.step("yes")
        for _ in CHAT_QUESTIONS:
            self.step("I need support")
        self.assertTrue(self.flow.complete)
        self.assertEqual(self.flow.history, [])
        self.assertEqual(self.flow.summary, "")
        self.assertIsNone(self.flow.place)

    def test_cancel_stops_before_network(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(SafeError):
            self.flow.advance("no", cancel)
        self.places.resolve.assert_not_called()

    def test_unknown_location_cannot_bypass_to_fema(self):
        self.step("no")
        self.places.resolve.return_value = None
        self.step("continue")
        self.fema.find.assert_not_called()


class LocationMathTests(unittest.TestCase):
    def test_distance(self):
        self.assertEqual(distance_km((0, 0), (0, 0)), 0)
        self.assertAlmostEqual(distance_km((0, 0), (0, 1)), 111.195, places=2)
        self.assertAlmostEqual(distance_km((0, 179.99), (0, -179.99)), 2.224, places=2)

    def test_stale_inaccurate_or_invalid_device_fix_is_unavailable(self):
        for values in ((0, 0, 100, 121), (0, 0, 1001, 1), (91, 0, 20, 1), (0, 0, float("nan"), 1)):
            self.assertEqual(validated_reading(*values).status, "unavailable")
        self.assertEqual(validated_reading(0, 0, 20, 1).status, "available")
