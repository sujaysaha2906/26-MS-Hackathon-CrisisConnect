import threading
import unittest
from unittest.mock import Mock

from crisisconnect.config import SafeError
from crisisconnect.handoff import CallAutomationHandoff


class HandoffTests(unittest.TestCase):
    def test_requests_call_automation_transfer_without_conversation_headers(self):
        connection, target = Mock(), object()
        handoff = CallAutomationHandoff(connection, target, "https://example.test/callback")
        handoff.transfer({"reason": "human_requested", "summary": "private conversation"})
        connection.transfer_call_to_participant.assert_called_once_with(
            target_participant=target,
            operation_context="crisisconnect-agent-handoff:human_requested",
            operation_callback_url="https://example.test/callback",
        )
        self.assertNotIn("private conversation", str(connection.mock_calls))

    def test_cancel_and_provider_failure_are_safe(self):
        connection = Mock()
        handoff = CallAutomationHandoff(connection, object())
        cancel = threading.Event()
        cancel.set()
        with self.assertRaisesRegex(SafeError, "Conversation ended"):
            handoff.transfer({"reason": "urgent"}, cancel)
        connection.transfer_call_to_participant.assert_not_called()

        connection.transfer_call_to_participant.side_effect = RuntimeError("provider secret")
        with self.assertRaises(SafeError) as raised:
            handoff.transfer({"reason": "urgent"})
        self.assertNotIn("provider secret", str(raised.exception))
