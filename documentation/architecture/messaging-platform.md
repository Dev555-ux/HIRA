# Messaging Platform Architecture

**Status**: Accepted (2026-08-17)
**Scope**: The channel-agnostic messaging pipeline — inbound message receipt through outbound delivery — across every transport HIRA supports. Vertical-agnostic, channel-agnostic; today's only live channel is WhatsApp.
**Built in**: Sprint 64A, PRs 2–7 (`v0.64.1-whatsapp-provider` through `v0.64.5-messaging-platform`).
**Related**: `documentation/ARCHITECTURE.md` (system-wide overview — predates this work and describes the pipeline this document supersedes for the messaging path specifically), `documentation/WHATSAPP_INTEGRATION.md`, `documentation/architecture/ADR-001-transactional-outbox.md` (the job/retry engine `MessagingService.record_inbound()` enqueues into), `documentation/architecture/channel-development-guide.md` (the step-by-step playbook for adding a channel — this document explains *why* the architecture is shaped this way; that one is the *how-to*).

This is the canonical reference for how a message moves through HIRA. Read this before touching `app/channels/`, `app/services/channel_manager.py`, `app/services/messaging_service.py`, or `app/webhooks/`. If you're adding a new channel (Messenger, Email, Website Chat, Telegram), read this first for the architecture, then go to `channel-development-guide.md` for the step-by-step build process — §8 below is the extension checklist in brief; that document is the full playbook.

---

## 1. Overview

Five layers, in a fixed order, each with exactly one job:

```
INBOUND

  External      Webhook Route      ChannelManager      MessagingService     AI
  Platform  ──▶  (verify request,  ──▶ (resolve      ──▶ (persist,      ──▶ (decide
  (Meta)         resolve provider)     provider)          dedupe, enqueue)   what to say)


OUTBOUND

  AI /           MessagingService     ChannelManager      Provider          External
  Dashboard  ──▶ (persist, run    ──▶ (resolve,       ──▶ (one transport ──▶ Platform
                  tool execution)      retry, validate     attempt)          (Meta)
                                       capability)
```

Only **MessagingService** touches Postgres. Only **ChannelManager** owns retry policy. Only a **Provider** speaks a platform's native wire format. Nothing above ChannelManager (AI, the dashboard, the webhook route) knows or cares which channel it's talking to beyond a `channel: str` field on a DTO.

The whole point: adding Messenger should mean writing one new package under `app/channels/messenger/` and registering it. Nothing in `app/ai/`, `app/services/messaging_service.py`, `app/services/channel_manager.py`, or `app/channels/registry/` should need to change. §8 is the checklist that keeps that true.

---

## 2. Layer responsibilities

| Layer | Lives in | Owns | Must never do |
|---|---|---|---|
| **AI** | `app/ai/` | Deciding what to say, which tool to call, when to escalate. Calls `MessagingService.send_reply()` (Autonomous Mode) with nothing more than a `Message` row already written to `pending`-shaped state. | Parse a channel's payload. Call a provider or `ChannelManager` directly. Know a channel exists beyond what's on the `Business`/`Conversation` row. |
| **Webhook route** | `app/webhooks/whatsapp.py` (one file per channel, eventually) | Read the raw request. Resolve the provider via `ChannelManager`. Resolve *which business* this request authenticates as (needed to pick the right credential — this is an auth concern, not message parsing). Call `provider.verify_webhook_signature()` / `parse_webhook()`. Hand the result to `MessagingService`. | Parse a native payload itself. Touch `Message`/`Customer`/`Conversation`. Dedupe. Enqueue a job. |
| **MessagingService** | `app/services/messaging_service.py` | The only DB-touching layer in this pipeline. Inbound: get-or-create Customer/Conversation, dedupe by external message id, persist `Message`, enqueue the AI job. Outbound: persist the send outcome, run governed tool execution, call `ChannelManager.send()`, record the resulting `DeliveryReceipt`. | Parse a channel's native payload. Decide retry policy or log per-attempt. Change what the AI decided to say or which CRM/calendar action to take. |
| **ChannelManager** | `app/services/channel_manager.py` | Resolve a provider via the registry. Validate the outbound message against the provider's declared `CapabilitySet` before calling it. Own retry/backoff for transient failures. Normalize an unexpected provider exception into one failed `DeliveryReceipt`. | Touch the database or any ORM model. Know about `Business`/`Conversation`/approvals/CRM. Fetch credentials itself — it receives `ChannelCredentials` as a parameter. |
| **Registry** | `app/channels/registry/` | One thing: `channel_id -> ChannelProvider` lookup. | Retry, logging, capability validation, credential loading, configuration, any API call. If a change needs to add one of those here, it belongs in `ChannelManager` instead. |
| **Provider** | `app/channels/<channel>/` | Translate a native payload into `NormalizedMessage`. Translate an `OutboundMessage` into a native API call — one attempt, no retry loop. Declare its own `CapabilitySet`. | Touch the database, import an ORM model, know about `Business`/`Conversation`, retry, do approvals, CRM, or analytics, or know any other provider exists. |

---

## 3. Invariants

These are checked by repository-wide grep, not just code review — re-run them after adding a channel. All seven held as of PR 7 (`git log` for the exact commit: `17d4ea0`).

1. **Providers never access the database.**
   `grep -rn "sqlalchemy\|db.Session\|db.scalars\|db.commit" app/channels/<channel>/` should return nothing (docstring mentions of these terms in prose are fine — check the match, not just the hit).

2. **ChannelManager never imports an ORM model.**
   `grep -n "from app.models" app/services/channel_manager.py` should return nothing.

3. **MessagingService is the only orchestration layer.**
   `grep -rn "def record_inbound\|def _get_or_create_customer\|def _get_or_create_conversation\|def send_reply\|def approve_and_send" app/` should return matches only inside `app/services/messaging_service.py`.

4. **AI never performs transport.**
   `grep -n "sender(\|ChannelManager\|WhatsAppProvider\|send_text" app/ai/processing.py` should return nothing. `ai/processing.py` calls `MessagingService(db).send_reply(...)` and nothing further down the stack.

5. **Webhooks never perform persistence.**
   `grep -n "db.add\|db.commit\|db.flush\|enqueue_job\|select(Message)\|select(Customer)\|select(Conversation)" app/webhooks/<channel>.py` should return nothing (the pre-auth `Business` lookup for credential resolution is the one legitimate `select(Business)` — see §4.1 — everything else moved out).

6. **Every outbound message routes through ChannelManager.**
   `grep -rn "send_text(\|\.post(" app/services/messaging_service.py` — the only HTTP-adjacent call should be inside `_send()`, and only via `ChannelManager().send(...)`, never a direct Graph-API-style call.

7. **Every inbound message from a real channel routes through MessagingService.**
   `grep -rn 'direction="inbound"' app/ --include="*.py"` returns exactly two hits: `app/services/messaging_service.py` and `app/ai/playground.py`. The second is a deliberate, documented exception, not a violation — Demo Chat (`app/ai/playground.py`) is a synthetic in-dashboard sandbox that reuses the AI pipeline directly, with no webhook, no `ChannelProvider`, and no external platform involved (see that file's own module docstring: "a second transport onto the exact same AI pipeline"). It is not a channel and is not subject to this pipeline's invariants. Any *other* hit is a real violation.

A capability-adjacent invariant worth naming separately, since it's the one that actually makes §8 cheap: **no layer above the provider branches on channel name.** `ChannelManager` and `MessagingService` check `provider.capabilities().supports(Capability.X)`, never `if channel == "whatsapp"`. `grep -rn '== "whatsapp"' app/services/channel_manager.py app/services/messaging_service.py` should return nothing.

**One deliberate, documented exception** (Sprint 65 PR 5), the same shape as invariant 7's playground.py exception: `MessagingService._resolve_send_context()` is the single place that dispatches on `conversation.channel` to pick which credential table backs an outbound send (`WhatsAppCredential` vs `InstagramCredential` — genuinely different tables with different fields, not something a capability flag can express). This was flagged as real, expected work in §10's "Known limitations" (credential resolution being WhatsApp-specific) before any second channel existed — not a redesign discovered after the fact. Everything *else* in `send_reply()`/`approve_and_send()` — tool execution, status transitions, retry, capability checks — stays 100% channel-agnostic; only credential *sourcing* branches. `grep -n 'conversation.channel ==' app/services/messaging_service.py` should return matches only inside `_resolve_send_context()`; any other hit is a real violation of this invariant.

---

## 4. Data flow

### 4.1 Inbound

```
Meta ──POST /webhooks/whatsapp──▶ receive()  [app/webhooks/whatsapp.py]
                                       │
                1. provider = ChannelManager().resolve("whatsapp")
                2. phone_number_id = provider.extract_routing_key(raw_body)
                3. business = SELECT Business WHERE whatsapp_phone_number_id = ...
                     (the one legitimate DB read left in the webhook route —
                     needed to know WHICH business's secret to check against)
                4. credential = get_stored_credential(db, business.id)
                5. signing_creds = ChannelCredentials(secret=app_secret)
                   provider.verify_webhook_signature(headers, raw_body, signing_creds)
                6. messages = provider.parse_webhook(raw_body)   -> list[NormalizedMessage]
                7. MessagingService(db).record_inbound(business.id, messages)
                       │
                       ├─ dedupe by external_message_id  (skip if already persisted)
                       ├─ get-or-create Customer (business_id, wa_phone)
                       ├─ get-or-create Conversation (business_id, customer_id, status=active)
                       ├─ INSERT Message(direction="inbound", ...)
                       ├─ Conversation.last_message_at / window_expires_at updated
                       ├─ if use_transactional_outbox: enqueue_job(GENERATE_AI_REPLY_TASK)
                       └─ commit  (once per message)
                       │
                8. legacy path (use_transactional_outbox=False): dispatch
                   generate_and_store_reply() via BackgroundTasks
                9. return 200
```

Steps 1–2 and 6 are the only places a native Meta payload is touched, and both are inside `WhatsAppProvider`. Step 3–5 is authentication, not message parsing — it stays in the webhook route on purpose (§2, §3 invariant 5's carve-out).

**Why `record_inbound(business_id, messages)` takes a single `business_id`, not one per message**: `NormalizedMessage` carries no business/routing field — by design (§6), it only knows about the *external* world (a customer's native id, not HIRA's internal `Business.id`). Since a single signed webhook delivery is authenticated as exactly one business (Meta signs one delivery per App), the webhook resolves that business once, during auth, and passes it through. This is strictly a simplification of the pre-PR-5 design, which re-resolved a business per Meta "change" — that per-change lookup was *not* re-verified against the signature check, a latent correctness gap this design closes rather than reintroduces.

**Commit granularity**: once per `NormalizedMessage`, not once per webhook delivery. Before PR 7, persistence committed once per Meta "change" (a delivery could contain several). Since `NormalizedMessage` is a flat list with no surviving "change" grouping, per-message commits are the natural boundary — strictly finer-grained, never coarser, than before.

### 4.2 Outbound — Assisted Mode (human approval)

```
Dashboard "Approve" ──▶ POST /api/v1/messages/{id}/approve  [app/api/dashboard.py]
                              │
                    MessagingService(db).approve_and_send(business_id, message_id)
                              │
                1. get_pending_reply()  — tenant-scoped, must be pending_approval
                2. check WhatsApp connected (phone_number_id + stored credential)
                3. claim: UPDATE Message SET status='sending' WHERE status='pending_approval'
                     — conditional UPDATE; concurrent approvals race here, loser gets
                       rowcount=0 and raises ValueError before touching anything else
                4. check 24h service window; raise WhatsAppWindowExpiredError if closed
                5. if message.type == "tool_call": execute_tool_call(..., commit=False)
                     — DEC-032/033 governance; human clicking Approve IS the confirmation
                6. self._send(phone_number_id, wa_phone, body, access_token=...)
                     │
                     └─ builds OutboundMessage + ChannelCredentials
                        ChannelManager().send(message, creds)   ── see §5
                        raises WhatsAppSendError on any failure
                7. message.status = "sent" | "failed"; commit
                     — every exit path leaves the message in a terminal state,
                       never stuck at "sending" (see recover_stale_sending_messages
                       in app/services/replies.py for the crash-recovery backstop)
```

### 4.3 Outbound — Autonomous Mode (no human in the loop)

```
AI turn generates a reply  [app/ai/processing.py::generate_reply_into_session]
        │
   business.mode == "autonomous"
        │
   MessagingService(db).send_reply(business, conversation, message)
        │
   Same shape as approve_and_send() minus the claim step (nothing to claim —
   there's no pending-approval state in this mode) and minus governance's
   pending_action gate (an Autonomous Mode tool call only runs if a prior
   turn already went through the confirm-with-the-customer flow).
   Same terminal-state guarantee, same self._send() call, same
   WhatsAppSendError -> message.ai_meta["failure_reason"] = "whatsapp_send_failed".
```

Both paths converge on the exact same `MessagingService._send()` → `ChannelManager.send()` → `WhatsAppProvider.send()` chain. This convergence is the point of §1's diagram — there is one transport path, not two.

---

## 5. Retry ownership

**ChannelManager owns retry. Providers make exactly one attempt.** This is the one place a naive reading of "wrap the old code" would have gotten it wrong — worth stating explicitly.

```python
# app/services/channel_manager.py
DEFAULT_MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.2

def send(self, message: OutboundMessage, creds: ChannelCredentials) -> DeliveryReceipt:
    provider = self.resolve(message.channel)
    if not provider.capabilities().supports(Capability.TEXT):
        raise CapabilityNotSupportedError(...)

    for attempt in range(1, self._max_attempts + 1):
        try:
            receipt = provider.send(message, creds)
        except Exception as exc:
            return DeliveryReceipt(status="failed", retryable=False, error=...)  # unexpected -> stop

        if receipt.status == "sent" or not receipt.retryable:
            return receipt
        last_receipt = receipt
        if attempt < self._max_attempts:
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    return last_receipt
```

The mechanism a provider uses to say "this is worth retrying" is `DeliveryReceipt.retryable: bool` — a generic, provider-agnostic signal. `ChannelManager` never sees an HTTP status code or any provider-specific error shape; it only ever checks one boolean.

`WhatsAppProvider.send()` sets it like this (`app/channels/whatsapp/send.py`):

| Failure | `retryable` | Matches Meta's meaning |
|---|---|---|
| 5xx response | `True` | Transient server error |
| Network/transport error (`httpx.RequestError`) | `True` | Request never definitively completed |
| 4xx response | `False` | Client error — retrying repeats the same mistake |
| 2xx with a malformed body | `False` | Meta likely already sent it — retrying risks a duplicate |
| Any other unexpected exception | `False` | Unknown failure mode — don't retry blindly |

Three attempts, `0.2 * attempt` seconds between tries (0.2s, then 0.4s) — this is a straight carry-forward of the pre-Sprint-64A `send_text()` retry loop's exact behavior (`app/services/messaging.py`), not a new policy. `send_text()` itself still exists, still independently tested (`tests/test_messaging.py`), and still has its own internal retry loop — it just has zero production callers as of PR 6/7. Its single-HTTP-call step (`send_text_once()`) is what `WhatsAppProvider.send()` actually calls; the two retry loops (the old one inside `send_text()`, the new one inside `ChannelManager`) are independent, not layered — a provider's `send()` never retries internally, so there's exactly one retry loop on the live path.

**A provider must never loop, sleep, or catch-and-retry inside `send()`.** If you're implementing a new provider and find yourself writing a `for attempt in range(...)` inside it, that logic belongs in `ChannelManager` (as a future per-channel override, if a channel genuinely needs different retry semantics — not built yet, see §10) or it's wrong.

---

## 6. Provider contract

`ChannelProvider` (`app/channels/base/provider.py`) is an ABC. Every method is abstract; there is no default implementation to inherit and forget to override.

```python
class ChannelProvider(ABC):
    channel_id: str   # stable string: "whatsapp", "instagram", ... — a class attribute

    def capabilities(self) -> CapabilitySet: ...

    def validate_credentials(self, creds: ChannelCredentials) -> ConnectionResult: ...
        # Live check against the external API. Connect/onboarding flow only —
        # never called on the per-message hot path.

    def extract_routing_key(self, raw_body: bytes) -> str: ...
        # Unauthenticated peek at a raw webhook body to find whatever id tells
        # the caller *which business* this request is for (WhatsApp's
        # phone_number_id). The caller uses this to load that business's
        # ChannelCredentials BEFORE verify_webhook_signature() — you cannot
        # verify a per-business signature without first knowing whose secret
        # to check it against. Raises WebhookVerificationFailedError if the
        # body is malformed or has nothing to route on.

    def verify_webhook_signature(
        self, headers: Mapping[str, str], raw_body: bytes, creds: ChannelCredentials
    ) -> bool: ...
        # Never raises for a bad signature — returns False.

    def verify_subscription(self, query_params: Mapping[str, str], creds: ChannelCredentials) -> str | None: ...
        # GET-time handshake (Meta's hub.challenge). Returns the value the
        # platform expects echoed back, or None if this isn't a valid
        # handshake for this channel.

    def parse_webhook(self, raw_body: bytes) -> list[NormalizedMessage]: ...
        # Empty list for payload types this channel receives but doesn't
        # represent as messages (delivery-status callbacks). Raises
        # WebhookVerificationFailedError only for genuinely malformed input.

    def send(self, message: OutboundMessage, creds: ChannelCredentials) -> DeliveryReceipt: ...
        # ONE transport attempt. No retry loop — see §5. Must not raise for
        # an ordinary delivery failure; report it via
        # DeliveryReceipt(status="failed", retryable=..., error=...).
```

### The six DTOs (`app/channels/base/`)

None of these carry a database id, an ORM relationship, or a `Session`. That is the entire discipline this architecture depends on — the moment a DTO grows a `business_id: uuid.UUID` field "just for convenience," a provider stops being testable in isolation and §3's invariants stop being enforceable by grep.

```python
# credentials.py
@dataclass(frozen=True)
class ChannelCredentials:
    channel: str
    access_token: str
    secret: str | None = None                  # e.g. app secret for signature verification
    external_account_id: str | None = None     # e.g. phone_number_id
    extra: Mapping[str, str] = field(default_factory=dict)

# message.py
@dataclass(frozen=True)
class NormalizedMessage:
    channel: str
    external_conversation_id: str    # the customer's native id — for WhatsApp, their phone number
    external_message_id: str
    external_sender_id: str
    text: str
    sender_display_name: str | None = None
    media: tuple[MediaRef, ...] = ()
    raw: Mapping[str, object] = field(default_factory=dict)   # original payload — debug/audit only

@dataclass(frozen=True)
class OutboundMessage:
    channel: str
    external_conversation_id: str
    text: str
    media: tuple[MediaRef, ...] = ()
    reply_to_external_id: str | None = None

@dataclass(frozen=True)
class MediaRef:
    kind: MediaKind          # IMAGE | VIDEO | AUDIO | DOCUMENT
    url: str
    mime_type: str | None = None
    caption: str | None = None

# results.py
@dataclass(frozen=True)
class ConnectionResult:
    success: bool
    external_account_id: str | None = None
    display_name: str | None = None
    error: str | None = None

@dataclass(frozen=True)
class DeliveryReceipt:
    status: Literal["sent", "failed"]
    external_message_id: str | None = None
    error: str | None = None
    retryable: bool = False          # see §5 — meaningless when status="sent"
    raw: Mapping[str, object] = field(default_factory=dict)

# capabilities.py
@dataclass(frozen=True)
class CapabilitySet:
    channel: str
    supported: frozenset[Capability]
    def supports(self, capability: Capability) -> bool: ...
```

### Error hierarchy (`app/channels/base/errors.py`)

```
ChannelError                         # base — catch this alone if you only care "did messaging break"
├── ProviderNotFoundError            # registry: channel_id has no registered provider
├── CapabilityNotSupportedError      # ChannelManager: message needs a capability the provider lacks
├── InvalidCredentialsError          # provider: external API rejected the credential outright
├── WebhookVerificationFailedError   # provider: can't trust this request as genuinely from the platform
├── DeliveryFailedError              # provider: send() call to the external API failed
└── ConnectionFailedError            # provider: connection lifecycle failed for a non-credential reason
```

Note on current usage: `ProviderNotFoundError` and `CapabilityNotSupportedError` are the two actively raised in the live WhatsApp path today (registry lookup, capability check). `WebhookVerificationFailedError` is raised by `WhatsAppProvider.extract_routing_key()`/`parse_webhook()`. `InvalidCredentialsError`, `DeliveryFailedError`, and `ConnectionFailedError` are declared as part of the vocabulary a provider *may* raise for a genuinely exceptional case (not an ordinary delivery failure, which goes through `DeliveryReceipt` instead) — `WhatsAppProvider` doesn't currently raise them, preferring `ConnectionResult(success=False, ...)` and `DeliveryReceipt(status="failed", ...)`. A new provider is free to raise them where they fit; nothing downstream assumes they won't.

---

## 7. Capability system

`Capability` (`app/channels/base/capabilities.py`) is a closed enum:

```
TEXT · IMAGE · VIDEO · DOCUMENT · AUDIO · REACTIONS · TYPING ·
TEMPLATES · STORY_REPLY · READ_RECEIPTS · DELIVERY_RECEIPTS
```

A provider declares what it supports via `capabilities() -> CapabilitySet`; `ChannelManager.send()` checks `provider.capabilities().supports(Capability.TEXT)` before ever calling `provider.send()` — for a media/template message, the equivalent check would be against `Capability.IMAGE`/`Capability.TEMPLATES` (not yet wired, since nothing constructs a non-text `OutboundMessage` today — see §10). This is the mechanism, not a decoration: it is what makes §1's "add a channel, change nothing above ChannelManager" claim literally true, and §3's "no layer branches on channel name" invariant enforceable.

**WhatsApp today** (`WhatsAppProvider.capabilities()`): `{TEXT}` only. This is not a limitation of Meta's platform — it is a direct read of what this codebase's send/receive path actually implements (`_extract_text` only reads a body for `type == "text"`; `send_text`/`send_text_once` only ever build `type: "text"` payloads). Update this the moment media/template support is actually built — not before.

**Instagram today** (`InstagramProvider.capabilities()`, Sprint 65 PR 6): `{TEXT, IMAGE, VIDEO, AUDIO, DOCUMENT}` — `send_instagram_message()` builds a real Meta attachment payload for a media `OutboundMessage` (mutually exclusive with `text`, per Meta's API) and `parsing.py::_extract_media()` maps inbound `attachments` onto `NormalizedMessage.media`; both directions tested. Reactions, typing indicators, read receipts, and story-reply are still not sent or received — real future work, not modeled here. `DOCUMENT` is PDF-only and `IMAGE` covers GIF (Meta has no separate GIF attachment type) — see `app/channels/instagram/send.py`'s module docstring for exact format/size limits.

**A realistic read on future channels**, useful when scoping a new provider's `capabilities()` — not a commitment, a planning aid:

| Capability | WhatsApp | Instagram | Messenger | Email | Web Chat |
|---|:---:|:---:|:---:|:---:|:---:|
| TEXT | ✓ | ✓ | ✓ | ✓ | ✓ |
| IMAGE | — | ✓ | ✓ | ✓ | ✓ |
| VIDEO | — | ✓ | ✓ | ~ | ✓ |
| DOCUMENT | — | — | ~ | ✓ | ✓ |
| TEMPLATES | — | — | ~ | — | ✓ |
| TYPING | — | ~ | ✓ | — | ✓ |
| REACTIONS | — | ✓ | ✓ | — | ~ |
| STORY_REPLY | n/a | ✓ | — | n/a | n/a |
| READ_RECEIPTS / DELIVERY_RECEIPTS | ~¹ | ✓ | ✓ | — | — |

¹ Meta's WhatsApp Cloud API sends delivery-status webhooks; this codebase deliberately ignores them today (`if not value.get("messages"): continue` in the parsing layer) — so `False` is the honest answer for *this provider's actual behavior*, not the platform's ceiling.

**Voice does not belong in this table.** No persistent "message," streamed audio turns, call-control semantics (barge-in, hold, transfer) instead of media types. Treat it as a second interface extension when it's actually scoped, not a forced fit into `ChannelProvider` as designed for text-first channels.

---

## 8. Extension guide: adding a new channel

Concrete checklist, in order. Each step names the one file it touches and nothing else it should touch.

1. **New package**: `app/channels/<channel>/` — `__init__.py`, `provider.py`, `parsing.py`, `send.py`. Mirror `app/channels/whatsapp/`'s shape; there is no reason for a second layout to exist.

2. **Implement `ChannelProvider`** (`provider.py`) — all seven methods from §6. Zero database imports (invariant 1). If the platform's inbound/outbound wire format needs its own HTTP client wrapper, keep it inside this package, DB-free, matching `channels/whatsapp/send.py`'s shape.

3. **Declare real capabilities** (`capabilities()`). Only what you have actually implemented and tested — see §7's WhatsApp note. Advertising a capability you haven't built is worse than not declaring it: `ChannelManager` will let a message through that the provider silently mishandles.

4. **Register it** — `app/channels/<channel>/__init__.py`:
   ```python
   from app.channels.registry import get_default_registry
   from app.channels.<channel>.provider import <Channel>Provider

   get_default_registry().register(<Channel>Provider())
   ```
   This is the *only* line that wires a new channel into the system. `app/channels/registry/`, `app/services/channel_manager.py`, and `app/services/messaging_service.py` do not change.

5. **Add config** (`app/core/config.py`) — new channel's credentials/secrets, following the existing `whatsapp_*` naming convention. Additive only.

6. **New webhook route** (`app/webhooks/<channel>.py`) — mirror `app/webhooks/whatsapp.py`'s `receive()` shape from §4.1: resolve provider via `ChannelManager`, resolve the business for auth, verify, parse, hand off to `MessagingService.record_inbound()`. Do not persist anything inline (invariant 5).

7. **Wire the new outbound path.** If this channel is a `sender`-shaped drop-in for existing Assisted/Autonomous Mode flows, no change is needed — `MessagingService._send()` already routes by `message.channel`. If a business can have more than one channel connected simultaneously, `MessagingService`'s credential-resolution step (currently WhatsApp-specific: `get_stored_credential`) needs a per-channel equivalent — this is real, not-yet-built work; see §10.

8. **Tests.** Match the existing pattern:
   - DB-free unit tests for the provider (`tests/test_<channel>_provider.py`) — parsing, capability reporting, routing-key extraction, webhook verification. See `tests/test_whatsapp_provider.py`.
   - DB-backed integration tests through the real webhook route, patching `httpx.Client.post` at the transport level (never inject a fake into `ChannelManager`/`MessagingService` — they don't expose that seam, by design). See `tests/test_whatsapp_cutover.py`, `tests/test_outbound_cutover.py`.
   - `ChannelManager`/`MessagingService` themselves need **no new tests** for a new channel — `tests/test_channel_manager.py` and `tests/test_messaging_service.py` already prove they're channel-agnostic via a fake provider. If adding a channel makes you want to add a test there, that's a signal something channel-specific leaked into a layer that's supposed to be generic.

9. **Run the full backend suite against real Postgres before merging.** Every PR in Sprint 64A (2 through 7) did this, and it caught real regressions twice (PR 7's two stale monkeypatch targets). `pytest -q` against `TEST_DATABASE_URL` pointed at a throwaway Postgres container; see any PR 2–7 commit message for the exact command.

10. **Re-run §3's invariant greps.** They're cheap and they're the whole point of the architecture — a green test suite proves behavior; the invariant greps prove the *shape* held.

**What you should never need to touch**: `app/channels/base/`, `app/channels/registry/`, `app/services/channel_manager.py`, `app/services/messaging_service.py`'s public methods, `app/ai/`. If a new channel forces a change to one of these, stop and reconsider the provider's design before editing the shared layer — the one exception being a genuinely new *kind* of business rule no existing capability flag covers (Voice's call-control model is the standing example — see §7).

---

## 9. File map

```
backend/app/
    channels/
        base/
            provider.py       ChannelProvider ABC — the contract every channel implements
            message.py         NormalizedMessage, OutboundMessage, MediaRef, MediaKind
            credentials.py       ChannelCredentials
            results.py            ConnectionResult, DeliveryReceipt
            capabilities.py        Capability enum, CapabilitySet
            errors.py                ChannelError hierarchy

        registry/
            __init__.py        ChannelRegistry — channel_id -> Provider, nothing else

        whatsapp/
            __init__.py        registers WhatsAppProvider into the default registry
            provider.py          WhatsAppProvider(ChannelProvider) — all 7 methods
            parsing.py             Meta JSON -> NormalizedMessage; signature_valid()
            send.py                  single-attempt Graph API call -> DeliveryReceipt
            shadow.py                 dormant (see §10) — retained for a future migration

    services/
        channel_manager.py    ChannelManager — resolve, validate capability, retry, normalize
        messaging_service.py   MessagingService — the only DB-touching layer in this pipeline
        messaging.py             send_text()/send_text_once() — legacy, still tested,
                                   zero production callers as of PR 6/7 (see §10)
        replies.py                 Assisted-Mode draft management (edit/reject/regenerate/
                                     escalate) — approve_and_send() moved out to
                                     MessagingService in PR 7

    webhooks/
        whatsapp.py            thin route: verify, resolve provider, parse, hand off

    ai/
        processing.py          decides what to say; calls MessagingService.send_reply()
                                 for Autonomous Mode, nothing further down the stack
```

---

## 10. Known limitations / not-yet-built (technical debt, honestly scoped)

Carried forward from the Sprint 64A PR 7 report — read this before assuming any of the following already works:

- **Tool execution lives inside `MessagingService`** (`execute_tool_call` is imported and called from `send_reply()`/`approve_and_send()`). A messaging-orchestration class currently also triggers calendar/CRM side effects. This is inherited from the pre-Sprint-64A design (sending and governed tool execution were already one atomic step); a cleaner AI/CRM-vs-Messaging boundary is real future work, not something this architecture pass attempted.
- **Session-window semantics (`Conversation.window_expires_at`, the 24h rule) are applied unconditionally**, not gated behind a capability check. Fine with one channel; before a channel with no such window (Email, Web Chat) shares this code path, this needs a `Capability.SESSION_WINDOW`-style check rather than an unconditional 24h extension.
- **Credential resolution** (`MessagingService._resolve_send_context()`, Sprint 65 PR 5) now dispatches WhatsApp vs. Instagram — the two channels that exist today — but is still a closed `if/elif`, not a registry a third channel plugs into automatically. Adding a third channel means extending that method, not just registering a provider. See §3's note on this invariant's one documented exception.
- **`send_text()`/`send_text_once()` retry-loop duplication**: `send_text()` has zero production callers as of PR 6/7 but is retained (and independently tested) because nothing has ported its direct tests to the transport-level stub pattern yet. Candidate for deletion once that porting happens.
- **Shadow Mode (`app/channels/whatsapp/shadow.py`) is dormant**, not deleted. It compared the legacy inline WhatsApp parser against `WhatsAppProvider` during the PR 3→5 migration; there's nothing left to compare it against now that production and the shadow path share one parser. Its comparator/metrics/logging are generic enough to repoint at a future migration (e.g., validating a rewritten provider, or an Instagram provider's first weeks in production) — see its own module docstring before reusing it.
- **The capability matrix in §7 is a planning aid, not a spec** — verify against the actual platform's current API before building a provider against it. Platform capabilities change; this table won't be kept in sync automatically.
- **Voice is out of scope for `ChannelProvider` as designed.** Don't force it in — see §7.
