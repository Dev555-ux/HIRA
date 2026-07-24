"""Error hierarchy for self-serve WhatsApp connection (Sprint 69), mirroring
app/calendar/providers/base.py's CalendarError hierarchy.

Deliberately does NOT redefine "not connected" here — app.services.messaging
already has WhatsAppNotConnectedError ("this business has no WhatsApp phone
number configured yet"), and since the new connect endpoint always sets
Business.whatsapp_phone_number_id and the WhatsAppCredential row together
atomically, "no phone number" and "no stored credential" are the same
failure mode in practice. Reuse that one class rather than defining a
second, confusingly-identical name here.
"""

from __future__ import annotations


class WhatsAppCredentialError(RuntimeError):
    """Base error for WhatsApp credential storage failures."""


class WhatsAppNotConfiguredError(WhatsAppCredentialError):
    """The encryption key isn't configured on this deployment."""


class WhatsAppCredentialInvalidError(WhatsAppCredentialError):
    """The submitted credentials failed Meta's own verification call —
    carries the reason back to the caller so the connect UI can show
    something more specific than "something went wrong"."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
