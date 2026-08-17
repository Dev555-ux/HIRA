"""Multi-channel messaging foundation (Sprint 64A PR 2).

Everything under this package is additive scaffolding: DTOs, the
`ChannelProvider` interface, and a provider registry that nothing in
production calls yet. WhatsApp's actual message handling keeps living in
app/webhooks/whatsapp.py, app/whatsapp/, and app/services/messaging.py
until a later PR wraps it behind `channels.whatsapp.WhatsAppProvider` and
cuts production traffic over — see the Sprint 64A architecture doc for the
full phased plan. Importing this package has zero side effects on existing
behavior.
"""

from __future__ import annotations
