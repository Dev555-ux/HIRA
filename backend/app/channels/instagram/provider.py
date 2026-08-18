"""InstagramProvider — Instagram's implementation of ChannelProvider.

Purpose: Sprint 65 PR 1 built every method except `validate_credentials()`
and `send()` (foundation only, no live Meta calls). Sprint 65 PR 5
implements `send()` for real (see `send.py`) and advertises
`Capability.TEXT` accordingly — outbound Instagram messages now flow
through `ChannelManager`/`MessagingService` exactly like WhatsApp's.
Sprint 65 PR 6 adds media: `IMAGE`/`VIDEO`/`AUDIO`/`DOCUMENT` join `TEXT`
in `capabilities()`, backed by real inbound attachment parsing
(`parsing.py`) and outbound attachment sending (`send.py`).
`validate_credentials()` is still a documented stub (`credentials.py`) —
not needed for the connect flow (Sprint 65 PR 2 has its own live Graph API
check) or the send path (messaging-platform.md §6: only called during
connect/onboarding, never the per-message hot path), so it stays
unimplemented until something actually calls it.

Does NOT do — same constraint as every `ChannelProvider`: no database
session, no ORM model, no persistence, no CRM, no AI invocation. Nothing
here calls `db.scalars`, `db.add`, `db.commit`, or imports anything from
app.models.
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
from app.channels.instagram.credentials import validate_instagram_credentials
from app.channels.instagram.parsing import (
    CHANNEL_ID,
    first_business_account_id,
    parse_inbound_payload,
    signature_valid,
)
from app.channels.instagram.send import send_instagram_message
from app.core.config import settings


class InstagramProvider(ChannelProvider):
    channel_id = CHANNEL_ID

    def capabilities(self) -> CapabilitySet:
        """`TEXT` + `IMAGE`/`VIDEO`/`AUDIO`/`DOCUMENT` as of Sprint 65 PR 6
        — a direct read of what `send.py`/`parsing.py` actually implement
        end to end: inbound `attachments` map onto `NormalizedMessage.media`
        (`parsing._extract_media()`), outbound `MediaRef`s send as a real
        Meta attachment message (`send.py`'s `_ATTACHMENT_TYPE`), both
        tested. Still no reactions/typing/read-receipts/story-reply — not
        built this PR. Matches `WhatsAppProvider.capabilities()`'s exact
        reasoning (messaging-platform.md §7): declare only what's
        genuinely built and tested, never what the platform could
        theoretically do.
        """
        return CapabilitySet(
            channel=self.channel_id,
            supported=frozenset(
                {Capability.TEXT, Capability.IMAGE, Capability.VIDEO, Capability.AUDIO, Capability.DOCUMENT}
            ),
        )

    def validate_credentials(self, creds: ChannelCredentials) -> ConnectionResult:
        """Delegates to `credentials.validate_instagram_credentials()`,
        which raises `NotImplementedError` — see that function's
        docstring. Deliberately propagates rather than catching it into a
        `ConnectionResult(success=False, ...)`: this method hasn't
        attempted a check at all, so reporting a "failure" result would
        misrepresent what happened. Not implemented in this PR (no Meta
        API calls)."""
        return validate_instagram_credentials(creds.access_token, creds.external_account_id or "")

    def extract_routing_key(self, raw_body: bytes) -> str:
        """Same tree walk as `parsing.first_business_account_id()` —
        reads the Instagram Business Account id out of the first `entry`
        that has one, trusting nothing else about the body. Raises
        `WebhookVerificationFailedError` for malformed JSON or a payload
        with nothing to route on — same contract as
        `WhatsAppProvider.extract_routing_key()`."""
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise WebhookVerificationFailedError("Malformed webhook body") from exc

        account_id = first_business_account_id(payload)
        if account_id is None:
            raise WebhookVerificationFailedError(
                "No Instagram business account id found in webhook body"
            )
        return account_id

    def verify_webhook_signature(
        self, headers: Mapping[str, str], raw_body: bytes, creds: ChannelCredentials
    ) -> bool:
        """Delegates to `parsing.signature_valid()` — the same HMAC-
        SHA256 scheme Meta uses across every webhook product. `creds.secret`
        is this business's decrypted Meta App secret, resolved by the
        caller before this method is invoked."""
        if creds.secret is None:
            return False
        return signature_valid(raw_body, headers.get("X-Hub-Signature-256"), creds.secret)

    def verify_subscription(
        self, query_params: Mapping[str, str], creds: ChannelCredentials
    ) -> str | None:
        """Meta's GET-time webhook-subscription handshake — identical
        `hub.mode`/`hub.verify_token`/`hub.challenge` scheme across every
        Meta webhook product, mirroring
        `WhatsAppProvider.verify_subscription()`. `creds` is unused for
        the same reason it's unused there: this handshake is checked
        against one shared, global verify token, not a per-business
        credential — but Instagram's is its own setting
        (`settings.instagram_verify_token`), not a reuse of WhatsApp's;
        Meta's webhook verify token is configured per callback URL, and
        HIRA's Instagram webhook (not built yet — see module docstring)
        will have a different URL than `/webhooks/whatsapp`."""
        mode = query_params.get("hub.mode")
        token = query_params.get("hub.verify_token")
        challenge = query_params.get("hub.challenge", "")
        if mode == "subscribe" and hmac.compare_digest(
            token or "", settings.instagram_verify_token
        ):
            return challenge
        return None

    def parse_webhook(self, raw_body: bytes) -> list[NormalizedMessage]:
        """Decodes `raw_body` as JSON, then delegates to
        `parsing.parse_inbound_payload()`. Raises
        `WebhookVerificationFailedError` for malformed JSON — see
        `WhatsAppProvider.parse_webhook()`'s identical contract. The
        mapping itself is intentionally incomplete — see `parsing.py`'s
        module docstring for exactly which payload shapes normalize to an
        empty body rather than being fully handled."""
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise WebhookVerificationFailedError("Malformed webhook body") from exc
        return parse_inbound_payload(payload)

    def send(self, message: OutboundMessage, creds: ChannelCredentials) -> DeliveryReceipt:
        """One transport attempt via `send.send_instagram_message()` — no
        retry loop here (ChannelManager's job, messaging-platform.md §5).
        See that function's docstring for the request/response shape and
        retry classification."""
        return send_instagram_message(message, creds)
