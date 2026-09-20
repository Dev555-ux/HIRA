# WhatsApp Onboarding v2 — Founder-First Design (Sprint 81)

Status (updated Sprint 83, 2026-09-19): **Implemented, awaiting live validation.** The flow described below is built end to end — provider, Graph API calls, frontend screens, error recovery (DEC-061) — on Sprint 82's foundation (DEC-060). It has not yet run against Meta's real API: everything is verified against a mocked Graph API built from Meta's documented response shapes. Guided-manual v1 remains the default entry point until a live pilot confirms this one (§10 steps 6-7).

This document is the complete design for replacing HIRA's current WhatsApp connection flow — where a business owner creates their own Meta App and pastes four values into a form — with Meta's Embedded Signup: a hosted, one-popup flow that removes that manual step entirely. It does not contain implementation code. It is written to be reviewed and approved before any code is written.

## 0. The fact that used to gate everything below — now resolved

**Embedded Signup requires Meta Tech Provider approval, and Stoneveil now has it.** Meta's dashboard confirms Tech Provider onboarding is complete (2/2 steps) and Partner Tools are available. The external, non-engineering approval process that this document was written around — and that DEC-038, DEC-042 and DEC-052 all deferred to — is done.

What remains is engineering, entirely within HIRA's control. As of Sprint 82 the foundation is built (see the Status line above); §10's roadmap steps 3–7 are what's left.

Everything in Phases 1–7 below is the destination, unchanged by the approval landing.

---

## 1. Phase 1 — Research (Meta's official, current requirements)

Researched against Meta's official developer documentation (`developers.facebook.com/documentation/business-messaging/whatsapp`) and current as of this writing. **One important, time-sensitive finding: Embedded Signup v2 is being deprecated on October 15, 2026 — any implementation must target v4, not the (more commonly blogged-about) v2 flow.**

### 1. Is Embedded Signup the recommended integration today?

Yes. It's Meta's official, purpose-built onboarding mechanism for a Tech Provider (an app that onboards *other* businesses' WhatsApp numbers, which is exactly HIRA's shape) — not a workaround or a third-party convenience layer. Every competitor researched for §7 (Interakt, WATI, AiSensy, Gupshup, Respond.io, Zoko) already builds on it. It replaces the "business owner creates their own Meta App" pattern guided-manual v1 uses today.

### 2. What steps are mandatory because Meta requires them?

- The business owner authenticates with their own Meta/Facebook credentials (Facebook Login for Business) — this cannot be delegated to HIRA; it's how Meta establishes that the *actual business owner* consented.
- Accept Meta's WhatsApp Business/Commerce Platform terms of service.
- Select or create a Meta Business Portfolio (what most people know as "Business Manager").
- Select or create a WhatsApp Business Account (WABA).
- Enter and verify the business phone number via a one-time code (SMS or automated voice call).
- Set a WhatsApp display name (subject to Meta's own review — can be pending or rejected on Meta's own timeline, not HIRA's).
- Set a Two-Step Verification PIN for the number (mandatory 6-digit PIN).
- **Two backend-only steps that are easy to miss and are *not* automatic even with Embedded Signup**:
  - Exchange the authorization code Embedded Signup returns for a long-lived business token (server-to-server call).
  - Call `PHONE_NUMBER_ID/register` with the 2FA PIN — without this explicit call, the number is created but **cannot send or receive messages yet**.
  - Subscribe HIRA's app to that WABA's webhooks via `POST /{WABA_ID}/subscribed_apps` — Embedded Signup does **not** wire this up automatically; skipping it means messages arrive at Meta and nowhere else.

### 3. Which steps can HIRA automate?

Everything after the business owner finishes Meta's own screens:
- Token exchange — fully automatic, invisible to the founder.
- Phone number registration (`/register` call) — fully automatic; HIRA generates the 2FA PIN itself and stores it encrypted, so the founder never has to invent or remember one.
- Webhook subscription (`subscribed_apps`) — fully automatic, one call, right after token exchange.
- Sensible defaults going into Meta's flow (e.g. pre-filling the suggested WhatsApp display name from the business's HIRA account name) — Meta's screens still render, but pre-filled, reducing typing.

What HIRA **cannot** automate, by Meta's own design (and shouldn't try to): the owner's own Meta login, entering the OTP sent to their phone, and Meta's own business-name review queue.

### 4. Which permissions are requested?

Three scopes, granted to HIRA's Tech Provider app when the business completes the flow:
- `whatsapp_business_management` — read/manage the business's WABA settings and message templates. Also required to look up the WABA's Conversions API `dataset_id`.
- `whatsapp_business_messaging` — send and receive messages on the business's behalf (the one HIRA's core product depends on).
- `whatsapp_business_manage_events` — log Business Messaging conversion events (Sprint 73: `LeadSubmitted` for leads that originated from a Click-to-WhatsApp ad). Without it the dataset lookup and the event POST both fail with a 4xx; nothing else in the product is affected.

### 5. What tokens are issued?

The frontend JavaScript SDK receives a short-lived **authorization code** (not a usable token) via the popup's callback. HIRA's backend exchanges that code, server-to-server, for a **Business Integration System User token** — scoped to that one business's WABA and phone number, not a personal user token and not HIRA's own app-level token.

### 6. Token lifecycle and refresh behavior

System User tokens (the category Business Integration tokens belong to) are long-lived by design — built to back an unattended, automated integration rather than expire every few hours the way personal user tokens do. **This needs re-verification against Meta's exact current documentation at implementation time** — official sources describe the token *category's* general behavior clearly but don't state an exact, guaranteed lifetime for Embedded-Signup-issued Business Integration tokens specifically. Regardless of nominal lifetime, a business can revoke HIRA's access at any time from their own Meta Business Settings — so the system must be designed to detect a suddenly-invalid token (a permission-denied response from Meta) and prompt reconnection gracefully, not assume "long-lived" means "immortal." See §5 (Connection Health Monitoring).

### 7. Webhook requirements

A public HTTPS callback URL and a verify token, for Meta's one-time GET handshake — HIRA already has this working (`app/webhooks/whatsapp.py`, DEC-038). The material change under Embedded Signup: because HIRA becomes **one Tech Provider app serving many businesses' WABAs** (rather than today's one-Meta-App-per-business model), HIRA can use a **single shared callback URL and verify token across every business**, with `subscribed_apps` doing the per-WABA wiring server-side. This is a genuine simplification, not just a relabeling — see §5.

### 8. Phone number registration requirements

Inside Meta's own screens: enter the number → receive and enter a one-time code (SMS or voice) → set the 2FA PIN. Immediately after, on HIRA's backend: call `/register` with that PIN to finish activating the number for Cloud API use. A number cannot send or receive real messages until that backend call succeeds — this is the exact step DEC-042's spike flagged as unautomatable within guided-manual v1's architecture, but which becomes straightforward under Embedded Signup's Tech Provider model.

### 9. Business verification requirements

Optional, but consequential, and **separate from the connection flow itself**. A newly connected number can send immediately at a base tier (250 messages/24h) without it. Completing Meta's Business Verification (submitting business identity documents) unlocks materially higher tiers — and per Meta's 2026 rollout, a verified business can jump much faster toward the 100K/day tier instead of climbing 1K → 10K → 100K sequentially. It's also a prerequisite for HIRA itself moving from the default 10-new-businesses-per-7-days onboarding cap to 200/7-days (see §11). Recommendation: don't block onboarding on it, but actively prompt it right after a successful connection (see Success screen, §3.7).

### 10. Common failure scenarios

Phone number already registered elsewhere (personal WhatsApp app, another WABA, or a different platform); wrong/unintended Meta Business selected; Meta Business Portfolio account limits reached; a too-new personal Facebook account not yet trusted enough by Meta to create a Business Portfolio; business-verification document mismatches; the browser/tab closing mid-flow (a WABA may exist on Meta's side with no token ever exchanged on HIRA's); hitting HIRA's own pre-approval 10-businesses/7-days onboarding cap. Full recovery design for each is in §4.

### 11. Official limitations and constraints

- **10 new businesses per rolling 7 days**, by default, until HIRA completes Business Verification + App Review + Access Verification as a Tech Provider — after which the cap rises to 200/7 days. This is a real, external constraint on HIRA's own go-to-market pace during early rollout, not just a business's individual limit — flagged prominently in §11 (Risks).
- Messaging tier limits are shared **per Meta Business Portfolio**, not per phone number, since October 2025 — relevant if a business ever wants a second number.
- Display-name review runs on Meta's own timeline; HIRA cannot expedite it.

### 12. Best practices recommended by Meta

Use System User (Business Integration) tokens, never short-lived personal tokens, for the ongoing integration. Call `subscribed_apps` immediately after token exchange so no inbound messages are lost in the gap. Store tokens as opaque strings with no assumed structure (matches HIRA's existing Fernet-encrypted-at-rest pattern exactly — see §5). Actively monitor for token/permission revocation rather than discovering it only when a send fails silently. Encourage Business Verification early, since 2026's faster tier-progression rollout rewards it quickly.

**Sources**: [Embedded Signup Overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/overview) · [Become a Tech Provider](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/get-started-for-tech-providers) · [Access Tokens Guide](https://developers.facebook.com/documentation/business-messaging/whatsapp/access-tokens/) · [Register a Business Phone Number](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/registration) · [Messaging Limits](https://developers.facebook.com/documentation/business-messaging/whatsapp/messaging-limits) · [Embedded Signup Flow Errors](https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/errors/)

---

## 2. Phase 2 — Founder Journey (end to end)

```
Business owner has a HIRA account, sees "Connect WhatsApp" on their onboarding checklist
        ↓ click
[HIRA] Welcome screen — sets expectation, explains what's about to happen
        ↓ click "Connect WhatsApp"
[META, hosted popup] Sign in with Facebook  →  Select/create Business  →  Select/create WABA
   →  Enter phone number + OTP  →  Set display name  →  Set 2FA PIN  →  Review & confirm
        ↓ popup closes automatically
[HIRA] Connecting… (backend: exchange token → register number → subscribe webhook — a few seconds)
        ↓ success
[HIRA] Success screen — confirms the number, offers a real first test message, links to Settings
        ↓ auto-return or click "Go to Dashboard"
[HIRA] Dashboard — checklist item complete, WhatsApp status badge live, AI Receptionist active
```

Everything inside the "[META, hosted popup]" block is Meta's own UI — HIRA cannot reskin, reorder, or shorten those six screens; they render in Meta's own visual language inside a popup/iframe HIRA embeds. **HIRA's actual design surface is the screen before the popup and the screens after it** — the Welcome screen has to fully prepare the founder for what they're about to see (so a Facebook login screen doesn't feel like a bait-and-switch), and the Connecting/Success screens have to make the invisible backend work (token exchange, number registration, webhook subscription) feel like *fast, confident progress*, not a black box.

**Every click, every state:**

| # | Actor | Screen/Action | State before | State after |
|---|---|---|---|---|
| 1 | Owner | Views onboarding checklist | Not connected | — |
| 2 | Owner | Clicks "Connect WhatsApp" | — | Welcome screen opens |
| 3 | Owner | Reads Welcome, clicks "Connect WhatsApp" (primary button) | Welcome screen | Meta popup opens, HIRA screen dims behind it |
| 4 | Owner | Signs in to Meta (or is already signed in) | Meta login | Meta business selection |
| 5 | Owner | Selects/creates Business Portfolio | — | Meta WABA selection |
| 6 | Owner | Selects/creates WABA | — | Meta phone number entry |
| 7 | Owner | Enters phone number, requests code | — | OTP entry screen |
| 8 | Owner | Enters OTP, sets display name, sets 2FA PIN | — | Meta's final review screen |
| 9 | Owner | Confirms | Meta popup, final screen | Popup closes automatically |
| 10 | System | Backend: exchange code → register number → subscribe webhook | Connecting screen (HIRA) | Success or Failure screen |
| 11 | Owner | Reads Success, optionally sends a test message | Success screen | Dashboard |

**Target: under 2 minutes, and as few clicks as Meta's own flow allows** — HIRA's own screens (Welcome, Connecting, Success) add exactly one click each (Connect, none, Continue) on top of whatever Meta's six screens require, which is the realistic floor given Meta owns that portion.

---

## 3. Phase 3 — UX Design (every screen)

Each screen below is described as: purpose, what it says, the one primary action, and the states it can be in. No wireframe images — this is a text specification a designer or engineer can build directly from.

### 3.1 Welcome

**Purpose**: set expectations before handing off to Meta's own screens, so nothing that follows feels unexpected.
**Says**: "Connect your WhatsApp Business number. You'll be asked to sign in with Facebook and confirm your business details — that's Meta's own verification, not something we can skip. Takes about 2 minutes. You'll need: access to the Facebook account for your business, and your business phone number handy to receive a confirmation code."
**Primary action**: "Connect WhatsApp" button.
**States**: default. No loading/error state here — it's static until clicked.

### 3.2 Connect Business WhatsApp (the launch point)

This is the same as 3.1 in HIRA's implementation — listed separately in the brief, treated here as the single Welcome/launch screen rather than two, since splitting them would add a click with no new information between them.

### 3.3 Meta Sign In

Not HIRA's screen — Meta's own hosted login. HIRA's only responsibility: open it in a way that feels intentional (a centered popup, not a jarring full-page redirect), and detect if the popup is closed without completing (see §4, "User closes browser halfway").

### 3.4 Business Selection

Meta's own screen (choose or create a Business Portfolio). HIRA's only lever: the Welcome screen already told the owner this is coming, so it reads as expected, not alarming.

### 3.5 Phone Number Selection

Meta's own screen (enter/select the number, receive and enter the OTP, set the display name and 2FA PIN). Same as above — HIRA's job was already done in the Welcome screen.

### 3.6 Connecting…

**Purpose**: bridge the moment between the Meta popup closing and HIRA confirming success — this is where token exchange, number registration, and webhook subscription actually happen (a few seconds, not instant).
**Says**: "Setting up your AI receptionist…" with a short sequence of sub-states so it never looks stuck: "Confirming your number" → "Activating messaging" → "Almost there." (These map directly to the three real backend calls — token exchange, `/register`, `subscribed_apps` — turned into founder-legible language, not exposed as steps 1/2/3 of an API.)
**Primary action**: none — this screen is non-interactive by design; a founder shouldn't be able to double-submit mid-flow.
**States**: in-progress (default) → success (auto-advances to 3.7) → failure (advances to 3.11, Failure Recovery).

### 3.7 Success

**Purpose**: confirm the connection is real, not just "credentials accepted" — and give the founder one immediate, satisfying action.
**Says**: "You're connected! Messages to [masked phone number] will now be answered by your AI receptionist." Shows the connected number (masked, e.g. `+91 98••• •••10`) and the WhatsApp display name Meta approved (or "pending Meta's review" if the name is still processing — see §4).
**Primary action**: "Send yourself a test message" (deep-links to a WhatsApp chat with the connected number) — the single most convincing proof a non-technical owner can get, more convincing than any dashboard status text. Secondary: "Go to Dashboard."
**States**: default. If the display name is still pending Meta's review, an inline note explains that messaging already works while the name finishes review — the founder isn't blocked, just informed.

### 3.8 Reconnect

**Purpose**: recover from a broken connection (revoked permission, expired session) without making the founder repeat the whole flow if avoidable.
**Says**: "We've lost the connection to your WhatsApp number. This can happen if access was removed in Meta, or your business changed something on their end. Reconnect to pick up right where you left off — your AI receptionist's setup, knowledge, and history are all still here." Primary action: "Reconnect" (relaunches the same Embedded Signup popup — Meta typically recognizes the already-linked WABA and shortens the flow, but this isn't guaranteed, so copy never promises "in one click").

### 3.9 Disconnect

**Purpose**: an honest, low-friction way to turn HIRA off for this number — trust is built by making this easy to find, not by hiding it.
**Says**: "Disconnect WhatsApp? Your AI receptionist will stop answering messages to this number immediately. Nothing else is deleted — your knowledge base, appointments, and conversation history stay exactly as they are, and you can reconnect anytime." Requires an explicit confirm (not a silent single click) given the real consequence (customers stop getting answered).

### 3.10 Connection Health

**Purpose**: a persistent, at-a-glance answer to "is this actually working right now," living on the Settings page and as a Dashboard widget (§3.13).
**Says**: three states only, in plain language: "Connected and receiving messages" (green) — last real inbound message seen recently; "Connected, but we haven't seen a message yet" (neutral) — reuses the existing `last_inbound_at`-based verification HIRA already built in DEC-041, now generalized to the v2 flow; "Needs attention" (amber/red) — token invalid, permission revoked, or Meta reports the number is no longer reachable, with a direct "Reconnect" action right there, not a separate hunt through Settings.

### 3.11 Permission Expired

**Purpose**: the specific "needs attention" case where Meta has explicitly revoked or expired access, as distinct from "we just haven't seen traffic yet."
**Says**: "Your WhatsApp connection needs to be renewed. This usually happens when access is changed on Meta's side — it's not something you did wrong." Primary action: "Renew connection" (same relaunch as Reconnect, 3.8) — deliberately not framed as an error the founder caused.

### 3.12 Failure Recovery

**Purpose**: the generic landing point when the Connecting screen (3.6) fails for any reason — routes to the specific messaging defined per-scenario in §4, never a raw error code.
**Says**: scenario-specific (see §4's "User message" column for each case) — always ends with one clear next action, never a dead end.

### 3.13 Settings Page (WhatsApp section)

Shows: Connection Health (3.10) at the top; the connected number (masked) and display name; "Disconnect" (secondary, not prominent — findable, not tempting); a link to Business Verification status/prompt if not yet completed (ties to §1.9's recommendation).

### 3.14 Dashboard Widget

A compact version of Connection Health (3.10) — one line, one status dot, clickable through to Settings. Exists so a founder never has to go looking for whether WhatsApp is working; it's part of the page they already open every day.

**Language rule applied throughout**: no screen in §3.6–3.14 (the screens HIRA fully controls) uses the words webhook, callback URL, API, Graph API, access token, App Secret, or OAuth. "Connect," "reconnect," "renew," "connection," and "confirm" carry the entire vocabulary. The one unavoidable exception is Meta's own screens (3.3–3.5), which HIRA does not control and which do use Meta's own terminology (e.g. "Business Portfolio," "WhatsApp Business Account") — the Welcome screen's plain-language framing is what shields the founder from that shift in register.

---

## 4. Phase 4 — Error Handling

| Scenario | User message | Recovery flow | Internal handling |
|---|---|---|---|
| **User closes browser halfway** | On return to HIRA: "Looks like you didn't finish connecting WhatsApp. No problem — pick up where you left off." | "Connect WhatsApp" restarts the flow from Welcome. If Meta already created a WABA with no token ever exchanged, Meta's own flow typically re-recognizes it and shortens the repeat. | No partial state persisted on HIRA's side (nothing was ever written — token exchange is the first write, and it never happened). Nothing to clean up. |
| **Wrong Meta account** | "This looks like the wrong Facebook account for [Business Name]. Sign out of Meta and try again with the account that manages your business's WhatsApp." | "Try a different account" relaunches the popup; Meta's own account switcher handles the rest. | No business data written until token exchange; a wrong-account attempt never touches HIRA's DB. |
| **No Business Manager** | "You'll need a Meta Business account first — this is a one-time Meta setup, not a HIRA one. Meta can create one for you as part of this flow." | Meta's own flow offers Business Portfolio creation inline — no separate HIRA step needed; the Welcome screen's expectation-setting already primed this. | None — entirely on Meta's side. |
| **No WhatsApp Business Account** | Same as above — Meta's flow offers WABA creation inline. | Continue through Meta's flow; no HIRA intervention needed. | None. |
| **Phone number already registered** | "That number is already connected somewhere else — either another WhatsApp app, or another business tool. To use it with HIRA, it needs to be freed up first: [link to a short, plain-language explainer], or use a different number." | Founder resolves on Meta's side (disable 2FA, remove from the old WABA/app) and retries — HIRA cannot do this on their behalf, since it requires access to whatever the *other* account is. | Detected from the specific Meta error code Embedded Signup returns for this case; mapped to this message rather than shown raw. |
| **Phone already connected elsewhere (to a different HIRA business, or revoked and reused)** | "This number is already connected to a different HIRA account. If that's you, disconnect it there first, then reconnect here." | Founder resolves via the other account's Disconnect (3.9), or contacts support if it isn't theirs. | Backend checks `whatsapp_phone_number_id` uniqueness across businesses before finalizing — same integrity check DEC-038 already enforces today. |
| **Permission denied** | "We weren't able to get the access we need to manage messages for this number. This usually means a permission was unchecked during setup — try again and make sure all requested permissions are approved." | "Try again" relaunches the popup. | Logged with which specific scope was missing, for support/debugging — never surfaced to the founder as a scope name. |
| **Expired token** | See Permission Expired (3.11). | "Renew connection." | Detected reactively: a send/read call returns a permission/auth error → Connection Health flips to "needs attention" → next dashboard load surfaces it, not silently retried forever. |
| **Lost connection** | Connection Health (3.10): "Needs attention." | "Reconnect." | Same detection path as Expired Token — HIRA doesn't try to distinguish every possible Meta-side cause in the founder-facing copy, since the fix (reconnect) is identical either way. |
| **Webhook failure** *(HIRA-side or Meta-side delivery issue, not a founder action)* | Only surfaces if it persists: Connection Health drops to "Connected, but we haven't seen a message yet" past a reasonable threshold, or "Needs attention" if HIRA's own subscription call itself failed. | "Reconnect" re-runs the subscription step; if the failure is HIRA-side infrastructure, this is an on-call/monitoring concern, not a founder-facing flow at all. | Alerting on `subscribed_apps` call failures at connection time (should never silently succeed-looking while actually failing) — a monitoring requirement, not a UI screen. |
| **Verification delay** *(display name pending Meta's review)* | Handled inline on the Success screen (3.7), not as an error: "messaging already works; your display name is still being reviewed by Meta." | None needed — not blocking. | Poll or webhook-driven update to reflect the name once Meta approves it; no founder action required. |
| **Rate limiting** *(HIRA's own 10-businesses/7-days onboarding cap, pre-approval)* | If hit: "We're onboarding a lot of new businesses this week — you're on the list, and we'll have you connected within [X]." Never a raw 429 or "try again later" with no timeframe. | Founder is queued; HIRA's own backend retries the connection attempt once capacity frees up, or notifies to retry. | This is the one failure mode that isn't really the founder's to fix — flagged prominently in §11 as a business risk requiring proactive Tech Provider approval progress, not just good error copy. |

---

## 5. Phase 5 — Technical Architecture

No implementation — this section explains the shape and the reasoning, for review before any code exists.

**Authentication flow**: Facebook Login for Business, launched via Meta's JavaScript SDK (`FB.login` with `config_id`, targeting embedded-signup v4 — v2 is deprecated Oct 15, 2026). The SDK returns an authorization code to a `message` event listener on the page that launched it — HIRA's frontend never sees or handles a token directly, only the short-lived code, which is immediately handed to HIRA's backend.

**Embedded Signup**: rendered as a popup (not a full-page redirect) so the founder never leaves HIRA's own page context — the Welcome screen stays visible, dimmed, behind it, reinforcing that this is still part of one continuous HIRA flow even though the content is Meta's.

**Backend responsibilities** (all new, replacing guided-manual v1's credential-form endpoint):
- Receive the authorization code from the frontend.
- Exchange it server-to-server for a Business Integration System User token (one Graph API call).
- Call `PHONE_NUMBER_ID/register` with a HIRA-generated 2FA PIN (never asked of the founder).
- Call `POST /{WABA_ID}/subscribed_apps` with HIRA's **single, shared** callback URL and verify token.
- Persist the token, encrypted, associated with that business.
- Return a simple success/failure signal to the frontend — the frontend never talks to Meta's Graph API directly for any of this.

**Frontend responsibilities**: render Welcome/Connecting/Success/error screens; launch and listen for the Embedded Signup popup's callback; hand the returned code to HIRA's backend; poll or subscribe for the Connecting screen's resolution. No Graph API calls, no token handling, ever, on the frontend — this mirrors DEC-038's existing principle that credentials never transit further than necessary.

**Token storage**: same shape as today's `WhatsAppCredential` table (DEC-038) — one row per business, encrypted at rest. The *meaning* of the stored value changes (a Business Integration System User token issued via Embedded Signup, not a founder-pasted access token + app secret pair), but the storage mechanism doesn't need to change.

**Encryption**: continue reusing `settings.calendar_encryption_key`/Fernet, the same "one key, multiple uses" reasoning already established in DEC-032/DEC-038 — no new required env var, no new key-management surface, for the same encryption need.

**Webhook registration**: the single most significant architectural shift from guided-manual v1. Today, each business's own Meta App can (in principle) have its own webhook config; DEC-038 made the verify token global for simplicity anyway. Under Embedded Signup, HIRA is **one Tech Provider app** subscribing to *many* businesses' WABAs — so one shared callback URL and verify token, registered per-WABA via `subscribed_apps` at connection time, is not just simpler but the architecturally correct shape for this model (this is exactly what DEC-042's spike concluded `subscribed_apps` is *for*, and exactly why it didn't fit guided-manual v1). The inbound webhook handler itself (`app/webhooks/whatsapp.py`) barely changes: it still looks up the business by `phone_number_id` from the payload and verifies the signature against that business's own stored secret — only *how the subscription got registered* changes, not how inbound messages are authenticated.

**Permission renewal**: no proactive renewal flow needed if Business Integration tokens are genuinely long-lived as designed (see §1.6's caveat) — the system instead reactively detects failure (a permission-denied response on any Graph API call) and flips Connection Health to "needs attention," rather than trying to predict expiry.

**Reconnect flow**: relaunches the identical Embedded Signup popup. Meta's own flow generally recognizes an already-linked WABA and shortens the repeat automatically — HIRA doesn't need to build any special "reconnect mode," just re-run the same connect flow.

**Connection health monitoring**: derived from two signals, not a new polling subsystem — (1) the existing `last_inbound_at` timestamp HIRA already tracks (DEC-041), reused as-is; (2) any Graph API call (a send, a status check) returning a permission/auth error, which flips status immediately rather than waiting for the next scheduled check.

**Future multi-number support**: because Embedded Signup already operates at the WABA level, and a WABA can hold more than one phone number, adding a second number to an already-connected business is largely "run the phone-number-selection portion of the same flow again against the existing WABA" — not a new architecture, a narrower re-entry point into this one.

**Future multi-location support**: if "location" maps to "a business with multiple physical branches sharing one WhatsApp presence," that's a product/data-model question (routing, not connection) — orthogonal to this design. If it instead means "each location gets its own number," it's the multi-number case above, repeated per location.

**Future multi-agent support**: also orthogonal to the *connection* architecture described here — this document is about how a number gets connected and stays healthy, not about how many AI Employees or human staff operate once it is. No changes anticipated here to support it.

**Why Embedded Signup over improving guided-manual v1 further**: guided-manual v1's core friction — asking a non-technical owner to create their own Meta App and find four raw values — is not a copy or UI problem DEC-041 could fully solve (it already tried, adding webhook visibility); it's structural to the "business owns its own App" model. Embedded Signup removes the App-creation step entirely by making HIRA itself the one Meta App, which is the actual fix DEC-038 named and deferred, not a new idea.

---

## 6. Phase 6 — Founder Experience

The three questions every screen in §3 answers, made explicit per screen type:

- **HIRA's own screens (Welcome, Connecting, Success, Reconnect, error states)**: "What is happening?" is answered in the first sentence, in business language, never in the passive voice that lets the founder wonder if something's wrong. "What do I need to do?" is exactly one action, never a menu of options presented as equally valid. "What happens next?" is stated even when the answer is "nothing — this finishes on its own," so the founder is never left guessing whether to wait or act.
- **Meta's own screens**: HIRA cannot answer these questions *inside* Meta's UI, so the Welcome screen answers them *in advance* — "you'll sign in with Facebook, confirm your business, and verify your number" is the founder's advance notice for exactly what's coming, so nothing on Meta's side reads as a surprise or a trick.

**Target time (under 2 minutes) and target clicks**, honestly scoped: HIRA's own screens add 2 required clicks total (Welcome's "Connect," Success's "Go to Dashboard" — the test-message button is optional). Everything else is Meta's own flow, which HIRA does not control the length of and should not promise to shorten beyond what's realistic — the 2-minute target is achievable for a founder who already has their business's Meta account and phone in hand (exactly what the Welcome screen asks them to confirm before starting), not universal.

---

## 7. Phase 7 — Competitive Research

| Provider | Onboarding mechanism | Steps (founder-facing) | Developer complexity (theirs, hidden from customer) | User friction | Recovery flow | Overall experience |
|---|---|---|---|---|---|---|
| **Interakt** | Embedded Signup (Facebook login → Meta's own screens) | Meta's standard flow; Interakt reports "minutes," no credit card for trial | Low for the business — Interakt built the Tech Provider integration | Business Verification (GST/equivalent docs) adds real friction for full activation, separate from the connect step itself | Not deeply documented; standard Meta-side recovery | Reviewed as smooth for connecting; complaints cluster around automation/support afterward, not the connect step |
| **WATI** | Embedded Signup, dashboard-first | "Minutes," no-code | Low for the business | Minimal — positioned as its core simplicity selling point | Standard | Praised specifically for SMB-friendly simplicity |
| **AiSensy** | Embedded Signup, guided | Claims ~10 minutes including Meta Business Verification | Low for the business | Low — explicitly markets speed as the differentiator | Standard | Strong marketing claim of "10 minutes," consistent with an Embedded-Signup-based flow |
| **Gupshup** | Embedded Signup + developer console | Account signup → Meta connection → provisioning via console | Higher — positioned toward developers/enterprises, not pure SMB self-serve | Higher for a non-technical owner specifically because of the console step | Developer-support-oriented | Strong for technical teams, weaker fit for a solo small-business owner |
| **Respond.io** | Embedded Signup, or a free Meta-hosted virtual number | Purchase/select number → connect to Meta → connect to platform | Low for the business | Low — the "display-name-only, free virtual number" option is a notably lower-friction variant worth studying further | Standard | Clear three-step framing, easy to follow |
| **Zoko** | Embedded Signup, e-commerce-flavored | Connect number → connect Shopify → configure inbox/routing | Low for the connect step itself; complexity is in the e-commerce setup *after* | Low for connect; the real friction is post-connect configuration, not onboarding | Standard | Fast to connect; total time-to-value quoted elsewhere as 2–8 working days, mostly for Business Verification and store setup, not the connect flow |

**Where HIRA can be meaningfully simpler, without violating Meta's requirements:**

1. **Nobody researched frames Business Verification as optional-but-encouraged the way §1.9/§3.13 does here.** Most either bundle it into "setup" ambiguously (making the founder unsure if they're blocked) or treat it as a hard prerequisite. Being explicit that messaging works *now* and verification is a fast-follow for higher limits — the Success screen's honest framing in §3.7 — is a real, buildable differentiator, not a marketing claim.
2. **Every competitor's post-connect experience defaults to a dashboard status line.** None reviewed offer a one-tap "send yourself a test message" as the primary confirmation (§3.7) — this is a small, concrete idea a non-technical owner will trust more than any status text, and costs nothing extra to build (it's just a `wa.me` deep link).
3. **Gupshup's console step is the one clear example of complexity leaking through to the founder.** HIRA's explicit language rule (§3, no webhook/API/token vocabulary) is a direct, deliberate contrast to that pattern, not a nice-to-have.
4. Respond.io's "display-name-only, free virtual number" option is worth a dedicated future spike (not part of this design) — it may let a founder start receiving messages *before* even owning a dedicated business number, which could meaningfully lower the barrier for the smallest businesses HIRA targets. Flagged as a future research item, not designed here.

---

## 8. Screen-by-screen wireframe descriptions

Covered inline with each screen in §3 (purpose / copy / primary action / states) rather than duplicated here — per-screen visual layout (exact spacing, component hierarchy) is an implementation-time design task once this content spec is approved, not part of this document's scope.

---

## 9. Risks and Limitations

- **Meta Tech Provider approval is the critical path**, not an implementation detail — see §0. This entire design is inert until that approval exists.
- **The 10-businesses-per-7-days onboarding cap** applies even after approval, until Business Verification + App Review + Access Verification are *all* complete — a real constraint on HIRA's own early growth pace, worth planning launch cohorts around rather than discovering mid-rollout.
- **Business Integration token lifetime is not fully confirmed** from public documentation alone (§1.6) — the reactive Connection Health design (§5) is deliberately robust to this uncertainty, but the exact behavior should be confirmed against a real test integration before launch, not assumed.
- **Meta's own six screens are entirely outside HIRA's design control** — the "under 2 minutes" target depends on Meta's flow performing as documented; if Meta changes it (as they are doing with the v2→v4 migration), this document's Phase 2 timeline should be re-validated, not assumed to still hold.
- **Guided-manual v1 should not be deleted** the moment this ships — it remains a legitimate fallback for a business that, for whatever reason, can't or won't complete Embedded Signup (e.g. no Business Manager access at all, edge cases Meta's flow doesn't smoothly handle) — DEC-038's original framing of guided-manual as a fallback, not guided-manual v2's obsolescence, still applies here once v2 exists.

---

## 10. Implementation Roadmap

1. ~~**Confirm Meta Tech Provider approval status with the founder**~~ — done. Approval granted (confirmed on Meta's dashboard, Sprint 82).
2. ~~**Submit the Tech Provider application**~~ — done, and approved.
   **2b. Foundation (Sprint 82, DEC-060)** — done: Tech Provider configuration centralized in `app/meta.py`, the webhook verifying both architectures, the schema and `WhatsAppOnboardingAttempt` model the callback will write, rate limits, and structured onboarding logs. No Meta call implemented.
3. ~~**Backend**: build the Embedded Signup callback endpoint~~ — done (Sprint 83, DEC-061), alongside the guided-manual v1 endpoints, which are untouched.
4. ~~**Frontend**: build the Welcome/Connecting/Success/error screens per §3, wire the JS SDK popup launch~~ — done (Sprint 83).
5. **Connection Health**: generalize the existing `last_inbound_at` signal (DEC-041) to also react to permission/auth errors, per §5. **Still open** — the reactive half doesn't exist yet; a revoked token is currently discovered only when a send fails.
6. **Pilot**: connect a small number of real businesses through the new flow while guided-manual v1 stays available, to validate the 10/7-days cap doesn't block early rollout and that Meta's real screens behave as documented.
7. **Cut over**: make Embedded Signup the default entry point once validated; keep guided-manual v1 as the documented fallback (§9).

## 11. Final Recommendation

Build Embedded Signup as designed here, the moment Tech Provider approval allows it — it is a genuine, structural fix to guided-manual v1's core friction (DEC-038 named this exact gap and deferred it for exactly this reason), not a redesign of something that's already working well. Do not let it block or replace guided-manual v1 in the interim; the two should coexist, with Embedded Signup becoming the default only once real-world pilot traffic confirms it behaves as documented. The single highest-leverage next action is not a design decision at all — it's finding out, and if needed starting, where HIRA stands on Meta Tech Provider approval, since every other date in this roadmap depends on it.
