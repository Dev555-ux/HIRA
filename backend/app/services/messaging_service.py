"""MessagingService — the one layer in the messaging pipeline allowed to
touch the database.

Purpose: consolidate everything stateful about a message — persistence,
the Assisted-Mode approval workflow, CRM updates, analytics — into a
single place, so the AI layer only ever has to say "send this text to this
conversation" and every channel's inbound webhook only ever has to say
"here are some normalized messages."

Responsibilities (final, once fully built out):

Inbound — receive `NormalizedMessage`s from ChannelManager, persist them
(get-or-create Customer/Conversation, dedupe on external message id,
insert Message rows), update CRM off message activity, enqueue the AI
reply job.

Outbound — persist an AI-generated or human-approved reply as a Message
row, run the Assisted/Autonomous Mode approval workflow, call
`ChannelManager.send()`, record the resulting DeliveryReceipt back onto
the Message row, trigger analytics.

Must never know about: how to parse or serialize any specific channel's
wire format (that's Provider's job); how many times to retry a failed send
or how to log/meter a provider call (that's ChannelManager's job). It
calls `ChannelManager`, never a `ChannelProvider` directly.

Current state (Sprint 64A PR 2 — foundation only): every method here is a
`NotImplementedError` stub. Building the real persistence/approval/CRM
logic now would mean either duplicating what `app/webhooks/whatsapp.py`,
`app/ai/processing.py`, and `app/services/replies.py` already do correctly
in production (two implementations of the same behavior, silently
diverging) or extracting them prematurely, before ChannelManager and a
real provider exist to route through. That extraction is Sprint 64A PR 6/7
work, done with characterization tests against the existing behavior — not
this PR.

Nothing in production constructs or calls `MessagingService` yet.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.channels.base.message import NormalizedMessage


class MessagingService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def record_inbound(self, business_id: uuid.UUID, messages: list[NormalizedMessage]) -> None:
        """Future: get-or-create Customer/Conversation per message, dedupe
        on `external_message_id`, insert Message rows, enqueue the AI
        reply job — the channel-agnostic generalization of today's
        `app/webhooks/whatsapp.py::_persist_inbound()`. Not implemented in
        this PR — see module docstring."""
        raise NotImplementedError(
            "MessagingService.record_inbound() is scoped to a later PR in the Sprint 64A "
            "sequence. This PR only lands the class skeleton."
        )

    def send_reply(self, conversation_id: uuid.UUID, text: str) -> None:
        """Future: persist the reply as a Message row, apply the
        Assisted/Autonomous Mode decision, and call
        `ChannelManager.send()` — the channel-agnostic generalization of
        today's `app/ai/processing.py::_auto_send()`. Not implemented in
        this PR — see module docstring."""
        raise NotImplementedError(
            "MessagingService.send_reply() is scoped to a later PR in the Sprint 64A "
            "sequence. This PR only lands the class skeleton."
        )

    def approve_and_send(self, message_id: uuid.UUID) -> None:
        """Future: the channel-agnostic generalization of today's
        `app/services/replies.py::approve_and_send()`. Not implemented in
        this PR — see module docstring."""
        raise NotImplementedError(
            "MessagingService.approve_and_send() is scoped to a later PR in the Sprint 64A "
            "sequence. This PR only lands the class skeleton."
        )
