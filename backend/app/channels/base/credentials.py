"""The one DTO that carries secrets across the provider boundary.

Purpose: let a provider authenticate to its external API and verify
inbound webhook signatures without ever holding a database session or an
ORM `WhatsAppCredential`/`Business` row.

Responsibilities: bundle whatever a specific channel's API needs
(access token, optional signing secret, the account id Meta calls
`phone_number_id`) plus a channel-specific overflow bag for anything that
doesn't deserve its own field.

Does NOT do: decrypt anything itself, know which business it belongs to,
or get persisted anywhere. Loading a business's stored credential,
decrypting it, and building this DTO is a MessagingService/ChannelManager
responsibility (see channel_manager.py, messaging_service.py) — this class
is purely the shape they pass down to a provider.

Future integration point: passed to every `ChannelProvider` method that
needs to call out or verify something — `validate_credentials()`,
`verify_webhook_signature()`, `verify_subscription()`, `send()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class ChannelCredentials:
    channel: str
    access_token: str
    secret: str | None = None
    external_account_id: str | None = None
    extra: Mapping[str, str] = field(default_factory=dict)
