"""Instagram connection domain (Sprint 65 PR 2) — OAuth flow, credential
storage, and connection-health checks for a business's own connected
Instagram professional account. Mirrors app/whatsapp/ and app/calendar/'s
shape: this package owns the database-touching, live-Meta-calling business
logic behind app/api/instagram.py's routes.

Not the same thing as app/channels/instagram/ — that package is the
ChannelProvider contract (messaging/webhooks, Sprint 65 PR 1), which this PR
does not touch. See documentation/architecture/messaging-platform.md for the
distinction between a channel's transport (ChannelProvider) and its
connection/credentials management (this package, same split WhatsApp
already has between app/channels/whatsapp/ and app/whatsapp/).
"""

from __future__ import annotations
