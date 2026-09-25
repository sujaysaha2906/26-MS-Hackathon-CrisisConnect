import unittest

from crisisconnect.core import load_json
from crisisconnect.interview import Interview


class InterviewTests(unittest.TestCase):
    def test_questions_follow_crisis_data(self):
        crises = load_json("scenarios.json")
        flood = Interview(crises["flood"])
        wildfire = Interview(crises["wildfire"])
        self.assertIn("flood in Richmond city, VA", flood.prompt)
        self.assertTrue(any("food" in q for q in flood.questions))
        self.assertFalse(any("food" in q for q in wildfire.questions))

    def test_answer_advances_once_and_empty_answer_does_not(self):
        interview = Interview(load_json("scenarios.json")["flood"])
        first = interview.prompt
        with self.assertRaises(ValueError):
            interview.answer("  ")
        self.assertEqual(interview.prompt, first)
        self.assertEqual(interview.answer("My home flooded."), interview.questions[1])
        self.assertEqual(interview.answers, ["My home flooded."])

    def test_completion_and_session_isolation(self):
        crisis = load_json("scenarios.json")["flood"]
        interview = Interview(crisis)
        for _ in interview.questions:
            interview.answer("An answer")
        self.assertTrue(interview.complete)
        self.assertIn("end of our conversation", interview.prompt)
        with self.assertRaises(ValueError):
            interview.answer("Extra answer")
        self.assertEqual(Interview(crisis).answers, [])

    def test_answers_are_redacted(self):
        interview = Interview(load_json("scenarios.json")["flood"])
        interview.answer("My number is 123-45-6789")
        self.assertNotIn("123-45-6789", interview.answers[0])
