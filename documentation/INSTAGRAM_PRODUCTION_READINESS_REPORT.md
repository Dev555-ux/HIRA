# Instagram Production Readiness Report

Status: written Sprint 65 PR 7 (final PR of Sprint 65 — production hardening / release readiness). Covers the Instagram Business Messaging integration built across PRs 1–7. Read alongside `documentation/INSTAGRAM_INTEGRATION.md` (setup/operations reference), `documentation/deployment/instagram-production-checklist.md` (execution checklist), and `documentation/testing/instagram-e2e.md` (manual validation walkthrough) — this report is the honest summary those three documents' details roll up into.

---

## Architecture

Instagram is a second, complete `ChannelProvider` implementation sitting inside the same five-layer messaging pipeline WhatsApp uses — External Platform → Webhook Route → ChannelManager → MessagingService → AI, and the reverse for outbound (`documentation/architecture/messaging-platform.md`). Nothing about this pipeline's shape changed to accommodate Instagram, and nothing changed in this PR:

- `ChannelManager`, the base DTOs (`NormalizedMessage`/`OutboundMessage`/`MediaRef`/`CapabilitySet`/`DeliveryReceipt`), the registry, and `MessagingService`'s public methods are all untouched by PR 7 (confirmed by `git diff` against each).
- The one documented exception to "no channel-name branching" — `MessagingService._resolve_send_context()` dispatching on `conversation.channel` to pick a credential table — is unchanged from PR 5, still the only place it happens.
- `InstagramProvider.capabilities()` currently advertises `TEXT, IMAGE, VIDEO, AUDIO, DOCUMENT` (PR 6) — a direct, tested read of what `send.py`/`parsing.py` actually implement, not an aspirational claim.
- Structurally, Instagram differs from WhatsApp in one real way worth remembering: **one HIRA-owned Meta App serves every business** (not bring-your-own-app), so `INSTAGRAM_APP_ID`/`INSTAGRAM_APP_SECRET`/`INSTAGRAM_VERIFY_TOKEN` are platform-wide settings, and webhook signature verification happens *before* resolving which business a delivery is for (the reverse of WhatsApp's per-business-secret ordering). See `INSTAGRAM_INTEGRATION.md` §1.

**Confirmed this PR**: every messaging-platform.md §3 invariant re-run and holds for both WhatsApp and Instagram (grep output reproduced below). No architecture document needed a correctness update — `messaging-platform.md`'s Instagram capability line was already accurate as of PR 6. `channel-development-guide.md` got one small accuracy fix (its "WhatsApp is the only implementation" framing was stale now that Instagram is a second complete one) and a pointer to where the two channels genuinely diverge — not a scope or process change to the guide itself.

```
# 1. Providers never touch the database
$ grep -rn "sqlalchemy\|db\.Session\|db\.scalars\|db\.commit" app/channels/whatsapp/ app/channels/instagram/
-> only docstring mentions, no real calls

# 2. ChannelManager never imports an ORM model
$ grep -n "from app.models" app/services/channel_manager.py
-> (empty)

# 4. AI never performs transport
$ grep -n "sender(\|ChannelManager\|WhatsAppProvider\|send_text" app/ai/processing.py
-> (empty)

# 5. Webhook routes never persist
$ grep -n "db.add\|db.commit\|db.flush\|enqueue_job\|select(Message)\|select(Customer)\|select(Conversation)" app/webhooks/whatsapp.py app/webhooks/instagram.py
-> only a docstring mention in whatsapp.py

# 6. Every outbound message routes through ChannelManager
$ grep -n "send_text(\|\.post(" app/services/messaging_service.py
-> (empty)

# 7. Every inbound message routes through MessagingService (+ documented playground.py exception)
$ grep -rn 'direction="inbound"' app/ --include="*.py"
-> exactly app/ai/playground.py and app/services/messaging_service.py

# No channel-name branching outside the one documented exception
$ grep -rn '== "whatsapp"\|== "instagram"' app/services/channel_manager.py app/services/messaging_service.py
-> exactly the two lines inside _resolve_send_context()
```

## Operational Readiness

Built this PR:

- **Logging.** Structured `logger.info`/`.warning` calls now cover OAuth connect/callback-success/reconnect/disconnect (`app/api/instagram.py`), webhook verification handshake/signature-failure/malformed-payload/unknown-account/success (`app/webhooks/instagram.py`, previously zero logging), and send retry (`app/services/channel_manager.py`, previously zero logging — channel-agnostic, so it now covers WhatsApp's retries too). Fixed two real leaks: `app/instagram/oauth.py` was building exception messages containing Meta's raw response body (`resp.text`), which then flowed into `logger.warning()` calls — now structured `status=/code=/subcode=` summaries, matching the convention `send.py`/`credentials.py` already used elsewhere in this same codebase. Verified with `caplog`-based tests asserting the expected line exists **and** that a real secret/token/body never appears in it.
- **Metrics.** No framework exists (Sentry only, for errors and one alert-worthy condition). Per this PR's explicit instruction, none was invented. `INSTAGRAM_INTEGRATION.md` §7 documents exactly which counters to add and at which call site, if/when one is adopted — every one of them sits at a log call site this PR already added, so instrumenting later is additive, not a rediscovery.
- **Health checks.** `GET /health/instagram` (new) — configuration/wiring only (registry, provider load, credential-encryption availability, OAuth/webhook config presence), never calls Meta, no DB query, stays fast by construction. Distinct in kind from `GET /health/whatsapp` (a traffic-staleness check) — there is no Instagram equivalent of "last inbound message age" yet; that gap is named, not silently absent.
- **Failure hardening.** Two real, previously-latent bugs fixed:
  1. `INSTAGRAM_VERIFY_TOKEN`'s guessable dev default was never added to the production boot guard, despite the webhook route (which the token protects the handshake for) having been live since PR 3 — a stale TODO comment in `app/core/config.py` said to add it "in the same PR that stands up the webhook route," which never happened until now. Lower severity than it sounds: POST payload forgery was never possible (the HMAC secret check fails closed when unset), only the one-time GET handshake was under-guarded.
  2. `store_credentials()`'s `IntegrityError` handling attributed *every* unique-constraint violation to "this Instagram account is already connected to a different business" — including a genuine reconnect race (two concurrent requests for the *same* business hitting its own `business_id` unique constraint), which used to surface a false, confusing "connected elsewhere" error to a business reconnecting its own account. Now disambiguates by re-querying and converges both concurrent requests on one final state.
  Every other audited failure mode (revoked credentials, expired token, Meta outage, malformed webhook, duplicate webhook, duplicate OAuth callback, retry exhaustion) was already handled correctly — see `INSTAGRAM_INTEGRATION.md` §9 for the full table and where each is implemented/tested.
- **Tests.** 40+ tests added/modified this PR (config guard, webhook/API/channel-manager logging paths, the reconnect-race fix, health endpoint). Full backend suite: **1342 passed, 0 failed** (`pytest -q` against real Postgres). Frontend suite: 430 passed, 5 pre-existing failures in `settings/page.test.tsx` confirmed present on this branch *before* this PR's changes (unrelated to Instagram, not touched by this PR).

## Repository Audit

- **No TODO/FIXME/XXX comments** found in `app/instagram/`, `app/channels/instagram/`, `app/webhooks/instagram.py`, `app/api/instagram.py` (the one `TODOS.md` reference in `oauth.py`'s docstring is a pointer to the tracked backlog file, not an inline marker).
- **Dead code found and removed**: `REQUIRED_META_PERMISSIONS` in `app/channels/instagram/credentials.py` — an inert, unused permission list left over from PR 1's scaffolding, superseded by (and inconsistent with — it listed `pages_messaging`, the real flow requests `pages_read_engagement`+`pages_manage_metadata` instead) `app/instagram/oauth.py::SCOPES`, which is the tuple actually used. Deleted, and the surrounding module docstring corrected to stop describing a "future PR" that already happened via a different module.
- **No duplicate OAuth helpers**: exactly one Instagram OAuth implementation (`app/instagram/oauth.py`). Structurally similar to `app/calendar/oauth.py` (signed-state pattern) by design, not by copy-paste — see `oauth.py`'s own module docstring for the two genuine differences (single-use enforcement, multi-Page discovery).
- **No duplicate HMAC implementation** in the sense the audit cares about: `app/channels/instagram/parsing.py::signature_valid()` and `app/channels/whatsapp/parsing.py::signature_valid()` are independently implemented (a deliberate design choice — providers are self-contained packages, messaging-platform.md's own principle), not an accidental duplicate; verified identical-by-construction via `test_signature_valid_matches_whatsapps_algorithm_by_construction`. `hmac.compare_digest` also appears in `verify_subscription()` for the (different) GET-handshake token comparison — a one-line stdlib call, not a second signature scheme.
- **Duplicate Graph API client pattern — observed, not fixed.** `graph.facebook.com` + `httpx.Client(timeout=10.0)` is built ad hoc in four places (`app/instagram/credentials.py`, `oauth.py` ×2, `app/channels/instagram/send.py`). This is consistent with WhatsApp's own established convention (`app/whatsapp/credentials.py` does the same) — not a new duplication Instagram introduced, and consolidating it would mean touching both channels' core send/auth logic, a real architecture change explicitly out of this PR's scope ("no architecture redesign," "no scope creep"). Flagged as a candidate for a future, deliberate consolidation PR, not silently left unexamined.
- **Channel-name branching**: exactly the one documented exception (`_resolve_send_context()`) plus this PR's own `health_instagram()`'s `provider.channel_id == "instagram"` check — the latter is a dedicated Instagram health endpoint asking "is the registered provider actually Instagram," which is inherently channel-specific by design (same as `/health/whatsapp` before it), not the kind of generic-layer special-casing the invariant exists to catch.
- **Identical gaps found in WhatsApp's equivalent code, explicitly out of scope for this Instagram-only PR, flagged for follow-up**: `app/webhooks/whatsapp.py` has the same zero-logging gap this PR fixed for Instagram's webhook route; `app/whatsapp/credentials.py::verify_whatsapp_credentials()` has the same raw-response-body-in-exception-message pattern this PR fixed in `oauth.py`. Neither was touched here — fixing them would be WhatsApp changes inside an Instagram-hardening PR.

## Known Limitations

Carried forward, not fixed in this PR (each already scoped/flagged in an earlier PR or explicitly deferred):

- **No AI tool for choosing to send media.** The transport pipeline fully supports a `Message` with media flowing through Autonomous Mode exactly like a human-approved one (PR 6), but nothing gives the LLM a way to *decide* to attach an image/video — that's new tool-calling/prompt work, not transport plumbing, and wasn't asked for.
- **No compose-from-scratch manual reply UI**, and no file-upload UI for attaching media to a draft — `PATCH /messages/{id}/draft` accepts a media URL via the API (PR 6), but there's no dashboard control for it yet (a deliberate scoping decision, since no file-storage infrastructure exists in this codebase to upload into).
- **No Instagram traffic-staleness health signal.** `GET /health/whatsapp` alerts via Sentry when inbound traffic goes quiet; there is no Instagram equivalent. `GET /health/instagram` checks wiring/config only. Adding a traffic check would need an "expected volume" baseline this integration doesn't have yet (Instagram traffic patterns per business are unknown pre-launch).
- **Credential resolution is a closed `if/elif`, not a registry** (`MessagingService._resolve_send_context()`) — documented since PR 5 as real, expected work for a *third* channel, not a defect specific to Instagram.
- **The Graph API client pattern duplication** noted in the Repository Audit above.
- **The two identical WhatsApp-side gaps** (webhook logging, raw-body-in-log) noted above.
- **App Review / Advanced Access** has not been obtained — this deployment can validate against the founder's own Development-Mode test accounts today; reaching real third-party businesses is blocked on a Meta approval process, not code (see `INSTAGRAM_INTEGRATION.md` §2).

## Live Meta Validation

**Not performed.** This environment has no Meta Developer App configured — `INSTAGRAM_APP_ID`/`INSTAGRAM_APP_SECRET` are empty and `INSTAGRAM_VERIFY_TOKEN` is at its local dev default. No OAuth round-trip, no live webhook delivery, no real message send/receive (text or media) against Meta's actual infrastructure was exercised as part of this PR. Everything reported as "working" above is verified by the automated test suite (1342 backend tests, including provider-level tests against mocked `httpx` transports and DB-backed integration tests against a real Postgres instance) and by code review — not by a live round-trip. `documentation/testing/instagram-e2e.md` is the step-by-step guide for whoever has real credentials to run that validation; `documentation/deployment/instagram-production-checklist.md`'s Meta section is what to confirm in the Meta App dashboard itself. Neither has been executed.

## Risk Assessment

| Risk | Severity | Mitigated by |
|---|---|---|
| Production boot with a guessable Instagram webhook handshake token | Was real, now fixed | `_INSECURE_PRODUCTION_DEFAULTS` guard (this PR) |
| False "connected to a different business" error during a reconnect race | Was real, now fixed | `store_credentials()` re-query-on-conflict (this PR) |
| Secrets/tokens/raw Graph bodies in logs | Was real (oauth.py), now fixed for Instagram; WhatsApp's identical instance remains | `_meta_error_summary()` (this PR) + flagged follow-up |
| Untested against real Meta infrastructure | Real, unmitigated | Documented explicitly here and in the e2e guide; not claimed as done |
| App Review / Advanced Access not yet granted | Real, business-process risk not engineering risk | Named in `INSTAGRAM_INTEGRATION.md` §2 and the production checklist |
| No Instagram traffic-staleness alerting | Real, low-severity gap | Named as a known limitation; `/health/instagram` covers wiring, not volume |
| Graph API client pattern duplicated 4× (Instagram) + 1× (WhatsApp) | Low — maintenance cost, not a correctness or security risk | Named for a future consolidation PR |

## Release Recommendation

**Ready to merge as engineering work; not ready to flip on for real customers until live Meta validation runs.** Every messaging-platform invariant holds for both channels, the full test suite is green, the two real bugs this audit surfaced (config guard gap, reconnect-race false-positive) are fixed and tested, and logging/health-check/documentation deliverables are in place. The one thing standing between this PR and calling Instagram "production ready" in the full sense is real: nobody has run `documentation/testing/instagram-e2e.md` against a live Meta App yet, and Meta App Review/Advanced Access hasn't been requested. Recommend merging this PR, then treating "run the e2e guide against a real Meta Developer App" and "submit for App Review" as the next concrete steps — tracked outside this PR's scope, since neither is a code change this repository can make on its own.
