"""WhatsAppProvider — WhatsApp's implementation of ChannelProvider.

Purpose: wrap the WhatsApp transport logic that already exists in
production (app/webhooks/whatsapp.py, app/whatsapp/credentials.py,
app/services/messaging.py) behind the PR 2 interface, without rewriting
any of it. Every method below either reuses an existing pure function
directly or mirrors its logic closely enough to be covered by an
equivalence test — see each method's docstring for which.

Responsibilities: exactly the six ChannelProvider methods — validate
credentials, verify webhook signature, verify subscription handshake,
parse inbound payloads, send outbound messages, report capabilities.

Does NOT do — same constraint as the interface itself: no database
session, no ORM model, no persistence, no CRM, no AI invocation. Nothing
here calls `db.scalars`, `db.add`, `db.commit`, or imports anything from
app.models. Business/Customer/Conversation resolution stays entirely in
app/webhooks/whatsapp.py until a later PR moves it into MessagingService.

Not wired anywhere: no route, no registry entry, no ChannelManager call
references this class. It exists, is importable, and is tested — nothing
more, per PR 3's scope.
"""

from __future__ import annotations

import hmac
import json
from typing import Mapping

from app.channels.base.capabilities import Capability, CapabilitySet
from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import WebhookVerificationFailedError
from app.channels.base.message import NormalizedMessage, OutboundMessage
from app.channels.base.provider import ChannelProvider
from app.channels.base.results import ConnectionResult, DeliveryReceipt
from app.channels.whatsapp.parsing import CHANNEL_ID, parse_inbound_payload, signature_valid
from app.channels.whatsapp.send import send_whatsapp_message
from app.core.config import settings
from app.whatsapp.credentials import verify_whatsapp_credentials
from app.whatsapp.errors import WhatsAppCredentialInvalidError


class WhatsAppProvider(ChannelProvider):
    channel_id = CHANNEL_ID

    def capabilities(self) -> CapabilitySet:
        """Only TEXT — the truth of what this codebase actually does
        today, not what WhatsApp's platform is capable of. `_extract_text`
        (parsing.py) only reads a body for `type == "text"`; `send_text`
        (app/services/messaging.py) only ever posts `type: "text"`; no
        template, media, typing-indicator, reaction, or story-reply code
        exists anywhere in the send or receive path. Revisit this the
        moment any of those is actually implemented — not before."""
        return CapabilitySet(channel=self.channel_id, supported=frozenset({Capability.TEXT}))

    def validate_credentials(self, creds: ChannelCredentials) -> ConnectionResult:
        """Wraps `app.whatsapp.credentials.verify_whatsapp_credentials`
        verbatim — that function was already DB-free and DTO-shaped
        (takes a phone_number_id/access_token pair, not a stored
        `WhatsAppCredential` row), so there is nothing to adapt beyond
        translating its return value into `ConnectionResult`."""
        if creds.external_account_id is None:
            return ConnectionResult(
                success=False,
                error="ChannelCredentials.external_account_id (phone_number_id) is required "
                "to validate WhatsApp credentials",
            )
        try:
            display_name = verify_whatsapp_credentials(
                creds.external_account_id, creds.access_token
            )
        except WhatsAppCredentialInvalidError as exc:
            return ConnectionResult(success=False, error=str(exc))
        return ConnectionResult(
            success=True,
            external_account_id=creds.external_account_id,
            display_name=display_name,
        )

    def extract_routing_key(self, raw_body: bytes) -> str:
        """Same tree walk as `app/webhooks/whatsapp.py::_first_phone_number_id`
        — reads `phone_number_id` out of the first entry/change that has
        one, trusting nothing else about the body. Raises
        WebhookVerificationFailedError (rather than returning None, as the
        original private helper does) for malformed JSON or a payload with
        no `phone_number_id` anywhere, since a caller has no useful routing
        key to act on either way."""
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise WebhookVerificationFailedError("Malformed webhook body") from exc

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                phone_number_id = change.get("value", {}).get("metadata", {}).get("phone_number_id")
                if phone_number_id:
                    return phone_number_id
        raise WebhookVerificationFailedError("No phone_number_id found in webhook body")

    def verify_webhook_signature(
        self, headers: Mapping[str, str], raw_body: bytes, creds: ChannelCredentials
    ) -> bool:
        """Delegates to `parsing.signature_valid` directly (imported, not
        copied) — the same HMAC-SHA256 comparison production runs via
        `webhooks/whatsapp.py`, which imports this same function (PR 4
        relocated it here to break a circular import — see parsing.py's
        docstring). `creds.secret` is this business's decrypted app
        secret, resolved by the caller before this method is invoked
        (this method never touches a credential store itself)."""
        if creds.secret is None:
            return False
        return signature_valid(raw_body, headers.get("X-Hub-Signature-256"), creds.secret)

    def verify_subscription(
        self, query_params: Mapping[str, str], creds: ChannelCredentials
    ) -> str | None:
        """Mirrors `app/webhooks/whatsapp.py::verify_subscription`'s two
        conditions exactly (`hub.mode == "subscribe"` and a
        constant-time-compared `hub.verify_token`), returning the raw
        challenge string instead of a FastAPI Response — the original
        isn't reusable as pure logic since it's coupled to
        `Request`/`Response`. `creds` is unused on purpose: per that
        route's own docstring, WhatsApp's subscription handshake is
        checked against one shared, global `settings.whatsapp_verify_token`
        (a one-time "prove you own this endpoint" check Meta performs per
        App), not a per-business credential — this parameter exists only
        because the ChannelProvider interface is shared across channels
        that may need it."""
        mode = query_params.get("hub.mode")
        token = query_params.get("hub.verify_token")
        challenge = query_params.get("hub.challenge", "")
        if mode == "subscribe" and hmac.compare_digest(token or "", settings.whatsapp_verify_token):
            return challenge
        return None

    def parse_webhook(self, raw_body: bytes) -> list[NormalizedMessage]:
        """Decodes `raw_body` as JSON, then delegates to
        `parsing.parse_inbound_payload()`. Raises
        WebhookVerificationFailedError for malformed JSON — in the real
        flow this body was already parsed once by `extract_routing_key`,
        so reaching malformed JSON here would mean this method was called
        out of order; guarded anyway since nothing enforces call order at
        the type level."""
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise WebhookVerificationFailedError("Malformed webhook body") from exc
        return parse_inbound_payload(payload)

    def send(self, message: OutboundMessage, creds: ChannelCredentials) -> DeliveryReceipt:
        """Delegates to `send.send_whatsapp_message`, which itself calls
        `app.services.messaging.send_text` unchanged — see send.py's
        docstring for why this keeps `send_text`'s existing retry loop
        rather than the single-attempt contract `ChannelProvider.send()`
        otherwise describes."""
        return send_whatsapp_message(message, creds)
