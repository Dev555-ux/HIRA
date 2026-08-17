# Channel Development Guide

**Status**: Accepted (2026-08-18)
**Scope**: The practical "how do I add a new channel" playbook — Messenger, Email, Website Chat, Telegram, whatever's next.
**Read first**: `documentation/architecture/messaging-platform.md` — this guide assumes you already know the five layers, the invariants, and why `ChannelProvider` is shaped the way it is. This document doesn't re-explain the architecture; it walks you through building against it.

If `messaging-platform.md` is the map, this is the turn-by-turn directions.

---

## Before you start

Read `app/channels/whatsapp/` end to end first. It's the only implementation that exists, and every step below points back to the specific file in it that does the equivalent thing. You are not designing a new shape — you're filling in an existing one.

Decide your channel's id now (a short lowercase string — `"messenger"`, `"email"`, `"webchat"`, `"telegram"`). It shows up as `channel_id` on your provider class, as the `channel` field on every DTO you construct, and in every file/directory name below. Pick it once, don't rename it later — it becomes load-bearing the moment `ChannelRegistry.register()` is called.

---

## 1. Create the provider package

```
backend/app/channels/<channel>/
    __init__.py
    provider.py
    parsing.py
    send.py
```

Mirror `app/channels/whatsapp/`'s four files exactly — there's no reason for a different shape to exist, and a future contributor comparing two providers side by side shouldn't have to learn two layouts.

- `provider.py` — the `ChannelProvider` subclass (step 3–6 below).
- `parsing.py` — pure functions translating your platform's native webhook payload into `NormalizedMessage`. No database import. See `app/channels/whatsapp/parsing.py`.
- `send.py` — a pure function wrapping your platform's outbound API call, returning a `DeliveryReceipt`. See `app/channels/whatsapp/send.py`.

**Done when**: the four files exist, importable, empty stubs are fine at this point.

---

## 2. Register the provider

`app/channels/<channel>/__init__.py`:

```python
from app.channels.registry import get_default_registry
from app.channels.<channel>.provider import <Channel>Provider

get_default_registry().register(<Channel>Provider())

__all__ = ["<Channel>Provider"]
```

This is the **only** line that wires your channel into the system. If you find yourself editing `app/channels/registry/`, `app/services/channel_manager.py`, or `app/services/messaging_service.py`'s public methods to make your channel work, stop — that's a sign your provider is leaking a channel-specific assumption into a layer that's supposed to be generic. Re-read `messaging-platform.md` §2 before continuing.

**Done when**: `python -c "import app.channels.<channel>; from app.channels.registry import get_default_registry; print(get_default_registry().available())"` includes your channel id. (It won't be reachable from anything yet — that's expected until step 6.)

---

## 3. Define capabilities

In `provider.py`:

```python
def capabilities(self) -> CapabilitySet:
    return CapabilitySet(channel=self.channel_id, supported=frozenset({Capability.TEXT, ...}))
```

**The rule, stated once because it matters more than anything else in this guide: declare only what you have actually implemented in `send.py`/`parsing.py` and covered with a test.** `ChannelManager.send()` trusts this set completely — it will let a message through to your `send()` the instant you advertise a capability, whether or not your code actually handles it. An over-declared capability isn't a TODO, it's a silent production bug the moment MessagingService or a future feature starts using it.

Start with `{Capability.TEXT}` only, exactly like `WhatsAppProvider` does today. Add more only when you've built and tested the code that backs them. See `messaging-platform.md` §7 for the full `Capability` enum and a planning-only estimate of what each target platform's API actually supports — verify against that platform's current docs before trusting the table, it's explicitly not a spec.

**Done when**: `<Channel>Provider().capabilities().supports(Capability.TEXT)` is `True`, and every other capability is `False` unless you've built it.

---

## 4. Implement DTO mapping (parsing.py)

Write the pure function(s) that turn your platform's native inbound payload into `list[NormalizedMessage]`. Study `app/channels/whatsapp/parsing.py::parse_inbound_payload()`/`parse_messages()` for the shape.

Field-by-field guidance, since getting `NormalizedMessage` wrong here is the single most common way a new channel silently corrupts customer identity downstream:

| Field | What goes here |
|---|---|
| `channel` | Your channel id constant. |
| `external_conversation_id` | Whatever your platform uses as the *thread* identity — for WhatsApp, that's the customer's phone number (WhatsApp has no separate thread id). For a platform with a real thread/conversation id distinct from the sender, use that instead. |
| `external_message_id` | The platform's own message id — this is your dedup key (`MessagingService.record_inbound()` dedupes on it). Must be stable and unique per message. Never synthesize one; if your platform doesn't provide one, that's a design problem to solve before writing this function, not something to paper over here. |
| `external_sender_id` | The customer's native id. Often the same value as `external_conversation_id` (true for WhatsApp); don't assume they're always equal for your platform. |
| `text` | Best-effort plain text. Empty string for anything you don't extract text from (matches WhatsApp's `_extract_text` convention for non-text message types) — never `None`. |
| `sender_display_name` | Optional; `None` if unavailable. |
| `media` | `()` unless you've actually implemented media handling (see step 3 — don't populate this without declaring the matching `Capability`). |
| `raw` | The original native message object, unmodified. Not optional — `MessagingService` and any future debugging tooling reads specific fields back out of `.raw` (see `messaging-platform.md` §4.1's note on why `wa_message_id`/`wa_phone` are read from `.raw` rather than the normalized fields). |

Write the outbound direction too: a function taking `OutboundMessage` and producing whatever your platform's send API needs (a request body, form fields, whatever) — this lives in `send.py`, covered in step 6.

**Done when**: a unit test feeds a realistic sample payload (a real webhook body from your platform's docs or a sandbox account, not an invented one) into your parsing function and asserts every `NormalizedMessage` field is correct.

---

## 5. Implement credential handling

Decide what your channel's `ChannelCredentials` needs:

```python
ChannelCredentials(
    channel="<channel>",
    access_token=...,           # required
    secret=...,                  # optional — only if you verify webhook signatures
    external_account_id=...,     # optional — your platform's equivalent of phone_number_id
    extra={...},                 # optional overflow for anything else
)
```

Implement `validate_credentials(creds) -> ConnectionResult` — a **live** call to your platform's API proving the credential actually works, used only during connect/onboarding, never on the per-message hot path. See `app/channels/whatsapp/provider.py::validate_credentials()`, which delegates to `app/whatsapp/credentials.py::verify_whatsapp_credentials()` — a plain function taking a token and an account id, no database, no `Session`. Write yours the same way: DB-free, testable by injecting a mock HTTP client.

**Do not** write the code that loads a business's *stored* credential from Postgres here — that's `MessagingService`'s job (§8 of `messaging-platform.md` flags this as a real gap today: credential resolution is currently WhatsApp-specific inside `MessagingService`, and a business with two connected channels needs a per-channel lookup that doesn't exist yet). If you're the first channel after WhatsApp, you may need to generalize that lookup as part of your PR — check `messaging-platform.md`'s "Known limitations" section before assuming it's already generic.

**Done when**: `validate_credentials()` is tested against both a successful and a rejected credential, using an injected fake HTTP client — no real network call in the test suite.

---

## 6. Implement transport

**Inbound** (`provider.py`, delegating to `parsing.py`):

```python
def extract_routing_key(self, raw_body: bytes) -> str: ...
    # Unauthenticated peek to find which business this request is for.
    # Raise WebhookVerificationFailedError if the body is malformed or has
    # nothing to route on. See WhatsAppProvider's implementation — this
    # must NOT touch a database or trust anything beyond finding the key.

def verify_webhook_signature(self, headers, raw_body, creds) -> bool: ...
    # Your platform's signing scheme. Never raise for a bad signature —
    # return False.

def verify_subscription(self, query_params, creds) -> str | None: ...
    # Only if your platform has a GET-time handshake (Meta's hub.challenge
    # equivalent). Return None if this isn't a valid handshake request.

def parse_webhook(self, raw_body: bytes) -> list[NormalizedMessage]: ...
    # Decode raw_body, delegate to parsing.py.
```

**Outbound** (`send.py`, called from `provider.py::send()`):

```python
def send(self, message: OutboundMessage, creds: ChannelCredentials) -> DeliveryReceipt: ...
    # EXACTLY ONE transport attempt. No loop, no sleep, no internal retry —
    # see messaging-platform.md §5. Retry is ChannelManager's job.
```

The retryable/non-retryable classification is the part most likely to need real thought, not a copy-paste: figure out, from your platform's API docs, which failure modes are safe to retry (typically: 5xx, network/timeout errors) and which aren't (typically: 4xx, and any 2xx whose body indicates the message was already accepted — retrying that risks a duplicate send to a real customer). Set `DeliveryReceipt.retryable` accordingly. See `messaging-platform.md` §5's table for exactly how `WhatsAppProvider` does this, as a worked example — don't just default everything to `True` or `False`.

**Done when**: `send()` returns `DeliveryReceipt(status="sent", ...)` on success and a correctly-classified `DeliveryReceipt(status="failed", retryable=...)` on every failure mode you can enumerate from the platform's docs, all covered by tests against an injected fake HTTP client (no real network calls).

---

## 7. Add tests

Match the existing pattern — don't invent a new one:

- **`tests/test_<channel>_provider.py`** (DB-free): parsing correctness (step 4), capability reporting (step 3), routing-key extraction, webhook signature verification, `send()`'s success/failure/retryable classification (step 6) — all against injected fakes, no real HTTP, no database fixture. Model directly on `tests/test_whatsapp_provider.py`.

- **Webhook route + integration tests** (DB-backed, real Postgres): once you've written `app/webhooks/<channel>.py` (mirroring `app/webhooks/whatsapp.py`'s `receive()` — verify, resolve provider via `ChannelManager`, parse, hand off to `MessagingService.record_inbound()`), write end-to-end tests posting realistic payloads through the real route and asserting persistence. Patch `httpx.Client.post` at the transport level for outbound assertions, exactly as `tests/test_outbound_cutover.py` and `tests/test_ai_reply_worker_idempotency.py::_stub_whatsapp_transport` do — **never** try to inject a fake into `ChannelManager` or `MessagingService` directly; they don't expose that seam, on purpose (see `messaging-platform.md` §2).

- **`ChannelManager` and `MessagingService` need no new tests for your channel.** `tests/test_channel_manager.py` and `tests/test_messaging_service.py` already prove both are channel-agnostic, using a fake provider that isn't WhatsApp. If you find yourself wanting to add a test there for your channel specifically, that's the same signal as in step 2 — something channel-specific has leaked into a generic layer.

**Done when**: `pytest tests/test_<channel>_provider.py tests/test_<channel>_webhook.py -v` is green, and the new files add to the suite without modifying any existing test.

---

## 8. Run the architecture invariants

Before opening a PR, re-run every check from `messaging-platform.md` §3, substituting your channel:

```bash
# 1. Provider never touches the database
grep -rn "sqlalchemy\|db.Session\|db.scalars\|db.commit" app/channels/<channel>/
# -> only docstring mentions asserting the invariant, never a real import/call

# 5. Webhook route never persists
grep -n "db.add\|db.commit\|db.flush\|enqueue_job\|select(Message)\|select(Customer)\|select(Conversation)" app/webhooks/<channel>.py
# -> nothing, except the one legitimate select(Business) for auth (see §4.1)

# 7. Inbound Message rows only come from MessagingService (+ the documented
#    Demo Chat exception, app/ai/playground.py — see §3's note on this)
grep -rn 'direction="inbound"' app/ --include="*.py"
# -> exactly messaging_service.py and playground.py, nothing new from your channel
```

Also confirm the two you didn't touch still hold — they should, since you shouldn't have edited these files at all:

```bash
# 2. ChannelManager still doesn't import an ORM model
grep -n "from app.models" app/services/channel_manager.py

# 4. AI still performs no transport
grep -n "sender(\|ChannelManager\|WhatsAppProvider\|send_text" app/ai/processing.py
```

**Done when**: every command above returns exactly what its comment says, no more, no less. If a command returns something unexpected, that's not a doc bug to shrug off — it means the layer boundary broke. Fix the code, not the grep.

---

## 9. Verify no channel-name branching

The specific check that proves the capability system (step 3) is actually doing its job, not just decorating the code:

```bash
grep -rn '== "<channel>"' app/services/channel_manager.py app/services/messaging_service.py
```

This should return **nothing**. If either file needed an `if channel == "<channel>"` branch to make your channel work, the right fix is almost always a new `Capability` flag (or, for something genuinely novel — a new *kind* of business rule, not just a new platform — see `messaging-platform.md` §7's Voice example, which is the one acknowledged case where this pattern doesn't stretch far enough) — not a conditional bolted onto a layer that's supposed to work identically for every channel.

**Done when**: the grep is empty, and you can explain, for anything your channel needed that WhatsApp didn't, which `Capability` flag or DTO field carries that difference generically.

---

## 10. Done

Final checklist before merging:

- [ ] `app/channels/<channel>/` exists, matches WhatsApp's four-file shape
- [ ] Registered in `<channel>/__init__.py`, and only there
- [ ] `capabilities()` declares only what's actually implemented and tested
- [ ] `parsing.py` maps every `NormalizedMessage` field correctly, tested against a real sample payload
- [ ] `validate_credentials()` is DB-free and tested against success + rejection
- [ ] `send()` is a single attempt, correctly classifies `retryable` per failure mode
- [ ] Provider-level tests pass, DB-free, no real HTTP
- [ ] Webhook route + integration tests pass against real Postgres
- [ ] Full backend suite green (`pytest -q` against a real `TEST_DATABASE_URL` — not sqlite, not `create_all()`; see any Sprint 64A PR's commit message for the exact setup)
- [ ] Every §8 invariant grep returns exactly what it should
- [ ] §9's channel-name-branching grep is empty
- [ ] `app/channels/base/`, `app/channels/registry/`, `app/services/channel_manager.py`, `app/services/messaging_service.py`'s public methods, and `app/ai/` are untouched (diff them explicitly — `git diff main -- app/services/channel_manager.py` should be empty)

If every box is checked, your channel is done, and nothing above `ChannelManager` had to change to get there. That's the whole architecture working as designed.
