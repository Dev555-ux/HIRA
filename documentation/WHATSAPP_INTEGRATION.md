# WhatsApp Integration Strategy

Status: **Accepted** (2026-06-29). See `DECISIONS.md` DEC-010.

## TL;DR Recommendation

**Use the Meta WhatsApp Cloud API directly for the MVP.** Optionally use the **Twilio Sandbox** for the very first throwaway spike (to validate the AI loop in an afternoon without Meta Business verification), then move to Cloud API before any real customer. Revisit **360dialog** later, when multi-tenant client number provisioning becomes the bottleneck.

## Why this matters less on cost than it first appears

HIRA is an *inbound* AI receptionist. The dominant message type is a **service message** — a reply to a customer who messaged the business — sent within WhatsApp's **24-hour customer service window**. Per Meta's post–July 2025 per-message pricing:

- Service replies inside the 24-hour window are **free**.
- Every WhatsApp Business Account gets **1,000 free service conversations/month**.
- Paid **template messages** apply only to *business-initiated* outbound *outside* the window (e.g., an appointment reminder sent the day before). In India these are the cheapest globally (~$0.0094 marketing; utility cheaper).

So for the MVP, **messaging cost is near zero**. The decision is driven by setup friction, developer experience, control, and learning — not per-message price. Per-message markup (Twilio's +$0.005/msg, ~20–40% over Meta base) only starts to bite at scale and on outbound templates.

## Option Comparison

| Criterion | Meta Cloud API (direct) | Twilio | 360dialog | Other BSPs (Wati, Gupshup, etc.) |
|---|---|---|---|---|
| **Messaging cost** | Meta base rate only (free service window; ~$0.0094 IN marketing) | Meta rate **+ $0.005/msg** markup | Meta rate + **flat ~€49/mo**, no per-msg markup | Varies; often markup + platform fee |
| **Ease of setup** | Hardest — Meta Business verification, embedded signup, webhook config | Easiest — sandbox in minutes, managed onboarding | Medium — provisioning API, still need Meta assets | Easy–Medium (managed onboarding, vendor UI) |
| **API quality** | Raw but well-documented; you own the integration | Excellent SDKs, abstractions, helpers | Thin pass-through to Meta; clean | Higher-level, opinionated; varies |
| **Reliability** | Source of truth (Meta-hosted) | High, adds a hop/dependency | High, minimal abstraction | Varies by vendor |
| **Scaling** | Scales with Meta directly; you manage throughput | Scales but markup compounds on cost | Designed for multi-number/multi-client provisioning | Vendor-dependent caps |
| **India availability** | Full | Full | Full | Most have IN presence |
| **Dev experience** | More upfront work, maximum control & learning | Fastest to "hello world" | Good for technical teams comfortable building the rest | Fastest if you adopt their stack, least control |
| **Future scalability** | Best long-term economics & control | Cost grows; lock-in to Twilio abstractions | Strong for onboarding many client numbers (multi-tenant) | Lock-in risk to vendor features |

## Reasoning for the recommendation

Against the founder's stated optimization targets:

- **Learning**: Cloud API teaches the actual WhatsApp platform — webhooks, message objects, template management, the 24h window — not a vendor's abstraction over it. Highest learning value.
- **Low cost**: No platform fee, no per-message markup, cheapest Indian rates, free service window covers most MVP traffic. Lowest cost.
- **Production readiness**: It *is* the production platform; nothing to migrate off later.
- **Fast development**: This is the one axis where Cloud API loses — Meta Business verification and embedded signup are slower than Twilio's sandbox. Mitigation: spike the AI conversation loop against the **Twilio sandbox** first if verification will block early progress, then cut over.

**When to revisit 360dialog**: once HIRA onboards many businesses, each needing its own WhatsApp number provisioned programmatically, 360dialog's no-markup multi-number provisioning becomes attractive. That is a post-validation, multi-tenant-scaling concern — logged as a future review, not an MVP decision.

## Sources

- [Meta — Pricing on the WhatsApp Business Platform](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)
- [WhatsApp Business API Pricing 2026: Conversation Categories & What Changed (Blueticks)](https://blueticks.co/blog/whatsapp-business-api-pricing-2026)
- [Twilio WhatsApp Messaging Pricing](https://www.twilio.com/en-us/whatsapp/pricing)
- [Twilio — Notice: Changes to WhatsApp's Pricing (July 2025)](https://help.twilio.com/articles/30304057900699-Notice-Changes-to-WhatsApp-s-Pricing-July-2025)
- [360dialog Pricing](https://360dialog.com/pricing)
- [WhatsApp API Pricing comparison: Meta vs Twilio vs 360dialog (EZContact)](https://ezcontact.ai/en/blog/whatsapp-api-pricing-comparison-meta-twilio-360dialog-ezcontact/)

> Pricing figures above are current as of June 2026 research and **change frequently** — re-verify against Meta's official rate card before committing to financial projections.

---

## Operational integration (implemented)

### Self-serve connect (Sprint 69 guided-manual v1, hardened Sprint 71)

Everything below this point (env vars, Meta app setup, curl testing) describes the underlying platform mechanics. In production, an individual business does **not** set any of this via `.env`/Railway variables — each business brings its own Meta App and connects through the dashboard's Settings → WhatsApp wizard (`POST /api/v1/whatsapp/connect`), per DEC-038.

That wizard now also solves the step this doc's own instructions below leave implicit: after credentials verify, it shows a **Webhook Configuration** step with the exact Callback URL and Verify Token to paste into the business's own Meta App (App → WhatsApp → Configuration → Webhooks → subscribe to `messages`) — sourced from `GET /api/v1/whatsapp/webhook-config`, not hardcoded. It then verifies the connection for real: a **verify** step polls `GET /api/v1/whatsapp/status`'s `last_inbound_at` until an actual inbound message has been processed, rather than treating "credentials verified" as proof the webhook is receiving traffic. See DEC-041.

### The autonomous loop (no manual intervention)

```
Customer → Meta → POST /webhooks/whatsapp → verify signature → dedupe → store inbound
       → background task → orchestrator (KB retrieval + Groq) → reply
       → [business.mode == "autonomous"] → send_text() → WhatsApp Cloud API → Customer
```

- **Assisted Mode** (default): the reply is stored as `pending_approval` and sent only when a human approves it in the dashboard (`POST /api/v1/messages/{id}/approve`).
- **Autonomous Mode** (`businesses.mode = "autonomous"`): the reply is sent immediately by the background processor — no human step. Set a business to autonomous to get the fully-automatic loop.

Code map:
- Verify + receive + signature + dedupe + ignore status callbacks: `app/webhooks/whatsapp.py`
- Generate + (autonomous) auto-send: `app/ai/processing.py`
- Outbound Cloud API call: `app/services/messaging.py::send_text`
- Approve-then-send (assisted): `app/services/replies.py::approve_and_send`

### Environment variables (all from `.env`, never hardcoded)

| Var | Meaning | Where to get it |
|---|---|---|
| `WHATSAPP_VERIFY_TOKEN` | Arbitrary string; must match Meta's webhook config | You choose it |
| `WHATSAPP_APP_SECRET` | Verifies `X-Hub-Signature-256` on every payload | Meta App → Settings → Basic → App Secret |
| `WHATSAPP_ACCESS_TOKEN` | Bearer token for outbound sends | Meta → WhatsApp → API Setup (temp) or a System User token (permanent) |
| `WHATSAPP_API_BASE` | Graph API base (default `https://graph.facebook.com`) | default |
| `WHATSAPP_GRAPH_VERSION` | Graph API version (default `v21.0`) | default |

**No global `PHONE_NUMBER_ID`.** The sender phone-number-id is stored per business in `businesses.whatsapp_phone_number_id`, resolved from the inbound webhook's `metadata.phone_number_id`. This preserves multi-tenancy (each business sends from its own number).

### Meta configuration required (to go live)

1. **Meta app** with the **WhatsApp** product added; note the **App Secret** → `WHATSAPP_APP_SECRET`.
2. **A WhatsApp phone number** (test or production) → note its **Phone number ID**.
3. Seed a `businesses` row whose `whatsapp_phone_number_id` = that Phone number ID (and `mode = "autonomous"` for the no-approval loop).
4. **Access token** → `WHATSAPP_ACCESS_TOKEN` (temp 24h token for testing, or a System User permanent token).
5. **Webhook**: expose the backend over HTTPS (e.g. `ngrok http 8000`), then in Meta → WhatsApp → Configuration set:
   - Callback URL: `https://<public-host>/webhooks/whatsapp`
   - Verify token: the same string as `WHATSAPP_VERIFY_TOKEN`
   - Subscribe to the **messages** field.

### Conversions API for Business Messaging (Sprint 73)

HIRA reports **one** conversion event to Meta: `LeadSubmitted`, sent when a `Lead` moves into the `qualified` stage *and* its conversation originated from a Click-to-WhatsApp ad. No other event (Purchase, Schedule, …) is implemented, and nothing is backfilled.

**Token permission**: the System User token must additionally grant **`whatsapp_business_manage_events`** on top of `whatsapp_business_messaging` + `whatsapp_business_management`. Without it both Graph calls below return a 4xx; the rest of the product is unaffected (the conversion job fails permanently and is visible in `job_outbox`, nothing else breaks).

**Flow**:

1. Meta puts `referral.ctwa_clid` on the **first** inbound message of an ad-originated thread. `app/channels/whatsapp/parsing.py` lifts it onto `NormalizedMessage.ctwa_clid`; `MessagingService.record_inbound` writes it once to `conversations.ctwa_clid` and never overwrites it.
2. `update_lead` (stage → `qualified`) calls `enqueue_lead_submitted`, which enqueues an outbox job **inside the caller's transaction** under `idempotency_key = "ctwa_lead_submitted:{lead_id}"`. No `ctwa_clid` → nothing is queued and nothing is sent; the lead is simply *not attributable to a Click-to-WhatsApp ad*. Meta does **not** deduplicate these events, so that unique key is the only thing standing between a re-qualified lead and a duplicate conversion.
3. The worker runs `app/whatsapp/conversion_tasks.py`, which resolves the dataset id if it isn't cached yet and posts the event:
   - `GET  /{version}/{WABA_ID}/dataset` → cached on `businesses.whatsapp_dataset_id` (never fabricated; a WABA with no dataset fails the job rather than inventing an id).
   - `POST /{version}/{DATASET_ID}/events` with `action_source: "business_messaging"`, `messaging_channel: "whatsapp"`, `user_data: {whatsapp_business_account_id, ctwa_clid}`, `partner_agent: "hira"`.

Both calls reuse `WHATSAPP_API_BASE` + `WHATSAPP_GRAPH_VERSION` and the business's own stored `WhatsAppCredential` token — no new environment variable, no new credential store.

**Live verification status**: ⚠️ **deferred, and confirmed blocked**. Every path above is covered by unit/integration tests against a mocked Graph transport (`backend/tests/test_whatsapp_conversions.py`, 29 tests). Nothing in the code simulates or asserts a successful live send.

A live `GET /{version}/debug_token` against the currently configured System User token (2026-08-24) returns `type: SYSTEM_USER`, `is_valid: true`, `expires_at: 0`, scopes:

```
public_profile, whatsapp_business_management, whatsapp_business_messaging
```

`whatsapp_business_manage_events` is **not** granted.

A live `GET /v21.0/{WABA_ID}/dataset` against the real test WABA (`2511632579311134`, "HIRA Test Business") on 2026-08-24 returned **`200 {"data": []}`** — *not* a 4xx. So the failure mode here is "no dataset exists," not "permission denied": `resolve_dataset_id()` raises `ConversionEventError(retryable=False)` on the empty list, and the job fails permanently rather than reporting a false success. That branch is now verified against the live Graph API, not just against a mock.

**Known gap this surfaced**: a dataset is *created* by `POST /{WABA_ID}/dataset` (per Meta's onboarding guide). This implementation only reads (`GET`) — it can use a dataset that exists but cannot provision one. Deliberate: creating an ads dataset on a business's account is a side effect worth an explicit decision, not something a background job should do silently on first qualify. Decide before the live demo (see TODOS.md ONBOARD-G).

**Known gap — attribution window**: Meta drops events sent more than **7 days** after the ad click, and accepts only one CAPI event per ad click. The one-event rule is enforced (outbox `idempotency_key`); the 7-day rule is **not** — `conversations.ctwa_clid` has no timestamp, so a lead qualified two weeks after the click still enqueues a job that Meta will silently discard. Add `ctwa_clid_at` and skip past-window events if that waste matters.

Closing live verification needs (a) Advanced Access for `whatsapp_business_messaging` (which auto-grants `whatsapp_business_manage_events`), (b) a regenerated System User token carrying the new scope, (c) a provisioned dataset, and (d) a real Click-to-WhatsApp ad driving a real click, so an actual `ctwa_clid` exists to report against. Nothing here is fabricated anywhere in the code or the tests.

### Test with curl

Webhook verification (GET handshake):
```bash
curl "http://localhost:8000/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=$WHATSAPP_VERIFY_TOKEN&hub.challenge=12345"
# → 12345
```

Simulate an inbound message (signature must match the raw body):
```bash
BODY='{"entry":[{"changes":[{"value":{"metadata":{"phone_number_id":"<PHONE_NUMBER_ID>"},"contacts":[{"wa_id":"15551230000","profile":{"name":"Test"}}],"messages":[{"id":"wamid.test1","from":"15551230000","type":"text","text":{"body":"Are you open on Sunday?"}}]}}]}]}'
SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$WHATSAPP_APP_SECRET" | sed 's/^.* //')"
curl -X POST http://localhost:8000/webhooks/whatsapp \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIG" \
  --data "$BODY"
# → {"status":"received"}; in autonomous mode the reply is generated (Groq) and sent via the Cloud API.
```

Outbound send directly against the Cloud API (sanity-check token/number):
```bash
curl -X POST "https://graph.facebook.com/v21.0/<PHONE_NUMBER_ID>/messages" \
  -H "Authorization: Bearer $WHATSAPP_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messaging_product":"whatsapp","to":"<CUSTOMER_WA_NUMBER>","type":"text","text":{"body":"Hello from HIRA"}}'
```
