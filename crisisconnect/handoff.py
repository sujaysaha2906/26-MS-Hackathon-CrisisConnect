"""Human-agent handoff for a call controlled by Azure Call Automation."""
from .config import SafeError
from .public_data import check_cancel


class CallAutomationHandoff:
    """Request a blind transfer on an existing Call Automation connection.

    The telephone host owns the call connection and target identifier. Keeping
    those objects injected here lets the desktop application run without the
    optional Call Automation SDK or telephone credentials.
    """

    def __init__(self, call_connection, target_participant, callback_url=None):
        self.call_connection = call_connection
        self.target_participant = target_participant
        self.callback_url = callback_url

    def transfer(self, context, cancel=None):
        check_cancel(cancel)
        reason = context.get("reason") if isinstance(context, dict) else None
        operation_context = "crisisconnect-agent-handoff"
        if reason in ("urgent", "human_requested"):
            operation_context += ":" + reason
        options = {"operation_context": operation_context}
        if self.callback_url:
            options["operation_callback_url"] = self.callback_url
        try:
            # Conversation text is deliberately not put in SIP/VoIP headers.
            # The receiving agent can ask the caller for details after transfer.
            return self.call_connection.transfer_call_to_participant(
                target_participant=self.target_participant, **options)
        except Exception:
            raise SafeError("The call could not be handed to an agent. Please try again.") from None
