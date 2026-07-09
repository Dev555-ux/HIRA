# REST API Design

Status: **Accepted** (2026-06-29). See `DECISIONS.md` DEC-014, DEC-025.
Base path: `/api/v1`. Auth: Clerk JWT (dashboard endpoints) / Meta signature (webhook). All dashboard endpoints are tenant-scoped to the caller's `business_id`.

**Implemented so far** (as of 2026-07-10): `GET /api/v1/pending`; `/messages/{id}/approve`, `/draft` (`PATCH`), `/reject`, `/regenerate`, `/escalate` (see Assisted-Mode Approvals below — Sprint 27); `GET/POST/PATCH/DELETE /api/v1/kb` (+ `/kb/website`); `GET/POST /api/v1/onboarding/*` (+ `/playground/message`); `GET/PATCH /api/v1/settings` (AI Reply Mode only); `GET /api/v1/conversations`, `/conversations/{id}`, `/conversations/{id}/messages` (see the Conversations section below for exact query params — this is a smaller slice of the originally-sketched Conversations API: the two `POST` actions there are not built); `GET/POST/PATCH/DELETE /api/v1/leads` and `GET /api/v1/customers`, `/customers/{id}`, `/customers/{id}/timeline` (CRM Foundation — Sprint 28, see below and DEC-031); `/api/v1/calendar/*` (OAuth connect/callback, status, disconnect, settings, availability) and `GET/POST /api/v1/appointments` (+ `/{id}/reschedule`, `/{id}/cancel`) (Google Calendar Integration — Sprint 29, see below and DEC-032). All protected by Clerk JWT via `get_current_principal` (resolves the Clerk user → local `User` → `business_id`), **except** the calendar OAuth callback, which is a public Google browser redirect authenticated by a signed `state` param instead. Cross-tenant access returns `404`. Verification: RS256 against Clerk JWKS (`CLERK_JWKS_URL`). A dedicated `GET /escalations` list endpoint is still to be built — escalations are created (Sprint 27) but not yet listable. Remaining endpoints below (most of Settings, Users) are still to be built.

---

## Authentication

- **Dashboard endpoints**: `Authorization: Bearer <clerk_jwt>`. Backend validates the JWT, resolves `business_id`, and scopes every query. Missing/invalid → `401`; cross-tenant access attempt → `404` (don't reveal existence). With `CLERK_JWKS_URL` unset, requests correctly `500` with an actionable error rather than being silently treated as authenticated.
- **Webhook endpoints**: no JWT; verified by Meta's HMAC signature header and verify-token handshake.
- **Local dev without a Clerk project**: set `ALLOW_MOCK_AUTH=true` in `backend/.env` (never in production) to accept a fixed `Authorization: Bearer dev-mock-token` in place of a real JWT — mirrors the frontend's own mock auth, which sends this same token when it has no Clerk publishable key. See `app/auth/dependencies.py`.

## Standard Response Structure

Success:
```json
{ "data": { ... }, "meta": { "request_id": "..." } }
```
Error:
```json
{ "error": { "code": "validation_error", "message": "Human-readable", "details": [ ... ] },
  "meta": { "request_id": "..." } }
```
Conventions: `2xx` success, `400` validation, `401` unauth, `403` forbidden, `404` not found / cross-tenant, `409` conflict (e.g., slot taken), `422` semantic validation, `429` rate limit, `5xx` server. Lists are paginated with `?limit=&cursor=`.

---

## Endpoints

### WhatsApp Webhook
- `GET /webhooks/whatsapp` — Meta subscription verification (`hub.challenge`).
- `POST /webhooks/whatsapp` — inbound messages/status. Verifies signature, dedupes, persists, returns `200` fast, processes async.

### Conversations / Inbox
- `GET /conversations` — **implemented** (2026-07-08). Query params: `search` (matches customer display name or WhatsApp number), `status` (`open` → `Conversation.status == "active"`; `closed` → `"closed"`; `pending` → has an outbound message with `status == "pending_approval"`, a derived cross-cutting view, not a `Conversation.status` value — omit for no filter, which also includes `escalated` conversations, which have no dedicated filter chip yet), `limit`/`offset` (pagination, `{"data": [...], "meta": {"total", "limit", "offset"}}`). Each row includes the joined `customer` (id/display_name/wa_phone), `last_message_at`-ordered, a `preview` (latest message body), and `has_pending_approval`.
- `GET /conversations/{id}` — **implemented**. Same summary shape as the list. Cross-tenant/unknown → `404`.
- `GET /conversations/{id}/messages` — **implemented**. Paginated (`limit`/`offset`), returns the most recent page in oldest-first order (same convention as `app/ai/orchestrator.py`'s history loader). Cross-tenant/unknown conversation → `404`.
- `POST /conversations/{id}/messages` — **not implemented** — human sends a manual reply. Originally sketched here; not part of the Inbox v1 scope.
- `POST /conversations/{id}/close` — **not implemented** — close the thread. Originally sketched here; not part of the Inbox v1 scope.

### Leads (CRM pipeline)

CRM Foundation (Sprint 28, 2026-07-09, see DEC-031). One `Lead` per `(business, customer)` — `UNIQUE(business_id, customer_id)`, so a repeat inquiry updates the existing lead rather than creating a second one. Every route sits behind `get_current_principal`, is tenant-scoped, and returns `404` if the lead/customer doesn't exist or belongs to another business (same convention as every other resource here) — see `backend/app/services/leads.py`.

- `GET /leads` — **implemented**. Query params: `search` (matches the linked customer's display name or WhatsApp number), `stage` (one of the seven values below), `limit`/`offset` (pagination, `{"data": [...], "meta": {"total", "limit", "offset"}}`, ordered by `updated_at desc`). Each row includes the joined `customer` (`id`/`display_name`/`wa_phone`).
- `POST /leads` — **implemented**. Body: `{"customer_id", "stage"?, "source"?, "estimated_value"?, "notes"?, "next_follow_up_at"?, "assigned_to"?}` (`stage` defaults to `"new"`). `404` if `customer_id` doesn't belong to this business; `409` if this business already has a lead for that customer; `422` if `assigned_to` doesn't reference a user of this business or `stage` isn't one of the seven valid values. Logs a `lead_created` `LeadEvent`.
- `GET /leads/{id}` — **implemented**.
- `PATCH /leads/{id}` — **implemented**. Body: any subset of the fields above. At least one required (`422` on an empty body). Omitting a field leaves it untouched; sending it as JSON `null` explicitly clears it (`source`/`estimated_value`/`notes`/`next_follow_up_at`/`assigned_to` are all nullable-and-clearable this way). Logs a `LeadEvent` for `stage`/`notes`/`next_follow_up_at`/`assigned_to` changes — but only when the new value actually differs from the old one, and never for `source`/`estimated_value` (treated as descriptive attributes, not pipeline activity).
- `DELETE /leads/{id}` — **implemented**. Cascades to the lead's `LeadEvent` history.

`stage` is one of `new | contacted | qualified | proposal_sent | negotiation | won | lost` — validated at this API layer (a Pydantic `Literal`), but stored as a plain string with no DB-level CHECK constraint, matching every other status field in this schema.

### Customers

Also Sprint 28 (DEC-031) — replaces the previously backend-less Customers page.

- `GET /customers` — **implemented**. Query params: `search` (name or phone), `limit`/`offset` (pagination). Each row: `{id, display_name, wa_phone, created_at, conversation_count, last_message_at, lead}`, where `lead` is `null` or `{id, stage}` (a summary — see `GET /leads/{id}` or the embedded detail below for the full record).
- `GET /customers/{id}` — **implemented**. Same shape as a list row, but `lead` (if present) is the *full* lead record (`stage, source, estimated_value, notes, next_follow_up_at, assigned_to, created_at, updated_at` — no nested `customer`, redundant here).
- `GET /customers/{id}/timeline` — **implemented**. Query params: `limit` (default 30, max 100), `offset`. Merges this customer's `Message` history with their `Lead`'s `LeadEvent` history into one newest-first, paginated list: `{"data": [...], "meta": {"total", "limit", "offset"}}`, where each item is either `{"type": "message", id, created_at, direction, body, status}` or `{"type": "lead_event", id, created_at, event_type, from_value, to_value, note}` (`event_type` is one of `lead_created | stage_change | notes_updated | follow_up_set | assigned`). Implemented as two independent queries merged in Python (see DEC-031), not a SQL `UNION`.

### Assisted-Mode Approvals

The full "Pending Approvals V2" copilot workflow (Sprint 27, 2026-07-09): every outbound AI-drafted reply is a `Message` row with `status="pending_approval"`. From there a human can edit, approve, reject, regenerate, or escalate it — see `backend/app/services/replies.py`. Every route below sits behind `get_current_principal`, is tenant-scoped via `get_scoped`, and returns `404` (not a distinguishing error) if the message doesn't exist, belongs to another business, or is no longer a pending reply (already approved/rejected/escalated) — same convention `approve` already used.

- `GET /pending` — **implemented**. Outbound messages awaiting approval, oldest first. Each row now also includes `customer` (`id`/`display_name`/`wa_phone`, joined via the conversation) and `conversation_preview` (the most recent inbound message in that conversation) — additive fields, not a breaking change to the existing shape.
- `PATCH /messages/{id}/draft` — **implemented**. Body: `{"body": "<edited text>"}`. Edits the pending draft's text in place before approval. Validates non-blank (`422`) and a max length of 4096 characters (`422`) — WhatsApp Cloud API's text message body limit, the same boundary `send_text` would eventually hit. Returns the updated `{id, body, status}`.
- `POST /messages/{id}/approve` — **implemented**. If `message.type == "tool_call"` (a proposed calendar action — Sprint 29, DEC-032), executes it via `AppointmentService` first (`409`/`404`/etc. from `map_calendar_error` if that fails, leaving the message `failed`); either way, then sends the (possibly just-edited) `body` via WhatsApp and marks it `sent`, or `failed` if the send errors (`502`).
- `POST /messages/{id}/reject` — **implemented**. Marks the message `rejected`; never calls the messaging service, never executes a proposed tool call. Returns `{id, status}`.
- `POST /messages/{id}/regenerate` — **implemented**. Re-runs the unmodified `generate_reply()` pipeline (same retrieval + prompt + LLM call the WhatsApp webhook uses, including the calendar tool schemas as of Sprint 29) against the customer message that originally triggered this draft, and replaces this message's `body`/`type`/`ai_meta` in place — a draft can flip between plain text and a proposed tool call on regenerate. Conversation history and the approval workflow are untouched. `502` if the LLM call fails; `404` if there's no customer message to respond to. Returns `{id, body, status}`.
- `POST /messages/{id}/escalate` — **implemented**. Marks the message `escalated`, marks the parent `Conversation.status = "escalated"` (a previously-unused, already-modeled status value), and creates an `Escalation` row (`reason="other"` — no UI collects a specific reason yet). Conversation history is untouched. Returns `{id, status, escalation: {id, conversation_id, reason, status, created_at}}`.

`Message.status` values as of Sprint 27: `received | pending_approval | sent | failed | rejected | escalated` — all plain strings (no CHECK constraint / migration needed to add a value, per `DATABASE.md`). `Message.type` gained `tool_call` in Sprint 29 (DEC-032) alongside the original `text` — a pending `tool_call` message's `body` is a human-readable, editable preview/confirmation string, and `ai_meta` carries `{tool_name, tool_arguments}`.

### Escalations
- `GET /escalations?status=open` — **not implemented**. `Escalation` rows are created by `POST /messages/{id}/escalate` (above) but there is no list/detail endpoint yet — see `.claude/DECISIONS.md` DEC-030.
- `POST /escalations/{id}/resolve` — **not implemented**.

### Calendar

Google Calendar Integration (Sprint 29, 2026-07-10, see DEC-032). Booking always goes through `AppointmentService` (`app/calendar/factory.py::get_appointment_service`) — there is no local-only appointment path; a business with no connected calendar gets `409` on every write below. `CalendarError` subtypes map to HTTP statuses uniformly across this section and Appointments (`app/api/calendar.py::map_calendar_error`): not-configured (missing `GOOGLE_CLIENT_ID`/`CALENDAR_ENCRYPTION_KEY`) → `503`; not-connected / auth failure (expired or revoked token) / slot conflict → `409`; event not found → `404`; provider unavailable → `502`.

- `GET /calendar/settings` — **implemented**. Returns `{timezone, working_hours}` (see `Business.working_hours` in `DATABASE.md`/`ARCHITECTURE.md`; `null` means not configured).
- `PATCH /calendar/settings` — **implemented**. Body: any subset of `{timezone, working_hours}`; at least one required (`422` on an empty body). `timezone` validated as a real IANA zone (`zoneinfo`); `working_hours` validated per-day (`HH:MM` 24-hour format, unknown day keys rejected) — both `422` on failure.
- `GET /calendar/oauth/connect` — **implemented**. Authenticated; returns `{authorization_url}` — the Google consent-screen URL to redirect the browser to, with an HMAC-signed `state` param encoding the business id (10-minute expiry). `503` if OAuth isn't configured on this deployment.
- `GET /calendar/oauth/callback` — **implemented**. **Public** — Google redirects the user's browser here directly after consent, with no Clerk session; authenticated instead by verifying `state`'s signature (same pattern as the WhatsApp webhook's HMAC signature, not a Bearer token). Exchanges the authorization `code` for a refresh token, encrypts and stores it, then **redirects** (not a JSON response) to `{FRONTEND_URL}/calendar?calendar=connected` or `?calendar=error&message=...`.
- `GET /calendar/status` — **implemented**. `{connected: bool, calendar_id: string | null}`.
- `DELETE /calendar/disconnect` — **implemented**. Removes the stored `CalendarCredential`. `204` whether or not one existed.
- `GET /calendar/availability?starts_at=&ends_at=` — **implemented**. Free slots (`[{starts_at, ends_at}, ...]`) within the given window — from `AppointmentService.list_availability()`, which computes Google's real free/busy and then clips it to the business's `working_hours`/`timezone` if configured. `422` if `ends_at <= starts_at`.

### Appointments

- `GET /appointments?from=&to=` — **implemented**. Both optional; filters `Appointment.starts_at`. No pagination — the date range is the natural bound (unlike the paginated list endpoints elsewhere in this API).
- `POST /appointments` — **implemented**. Body: `{customer_id, starts_at, ends_at, summary, conversation_id?}`. `404` if `customer_id` doesn't belong to this business; `422` if `ends_at <= starts_at`; `409` if the calendar isn't connected or the slot is taken (`GoogleCalendarProvider.create_event` pre-checks `freebusy` before inserting, since Google's API doesn't reject overlaps on its own).
- `GET /appointments/{id}` — **implemented**.
- `POST /appointments/{id}/reschedule` — **implemented**. Body: `{starts_at, ends_at}`. `404` if not found/another business's; `422` if `ends_at <= starts_at`.
- `POST /appointments/{id}/cancel` — **implemented**. No body.

`Appointment.status` values: `booked | rescheduled | cancelled` (unchanged since the original schema — DEC-013).

### AI booking tools

The orchestrator (`app/ai/orchestrator.py::generate_reply`) passes four tool schemas to the LLM (`app/ai/tools.py`): `check_availability`, `book_appointment`, `reschedule_appointment`, `cancel_appointment`. `check_availability` is read-only and resolved automatically inside `generate_reply` (executed immediately, its result fed back for one bounded follow-up model call — never surfaced as something to approve). A **write** action the model proposes is *not* executed inline — see Assisted-Mode Approvals below: in Assisted Mode it becomes a `pending_approval` message with `type="tool_call"`; approving it (`POST /messages/{id}/approve`) executes the tool via `AppointmentService` before sending the confirmation, returning `409`/`404`/etc. (via the same `map_calendar_error`) if execution fails. In Autonomous Mode the tool executes immediately, same as autonomous text-sending (DEC-027).

### Knowledge Base
- `GET /kb` — list entries.
- `POST /kb` — create entry (triggers embedding).
- `PATCH /kb/{id}` — update (re-embed).
- `DELETE /kb/{id}` — remove.

### Settings
- `GET/PATCH /settings` — **implemented**, AI Reply Mode (`mode`) only so far.
- Business profile fields (name, etc.) — **not implemented**.
- Google OAuth connect/callback and timezone/working-hours — **implemented**, but under `/calendar/*` (see the Calendar section above), not `/integrations/google/*` as originally sketched here.
- `GET /integrations/whatsapp` / `PATCH /integrations/whatsapp` — **not implemented** — WhatsApp number config (still only via `scripts/seed_business.py`/`update_business_phone.py`).

### Users
- `GET /users` — staff in the business.
- `POST /users/invite` — invite staff (owner only).

---

## Request Flow (example: approve an AI reply)

1. Dashboard `POST /api/v1/messages/{id}/approve` with Clerk JWT.
2. Backend validates JWT → resolves `business_id`.
3. Loads the `message`; verifies it belongs to that business and is `pending_approval` (else `404`/`409`).
4. Calls Messaging Service → sends via Meta Cloud API.
5. Updates `message.status = sent`; returns the updated resource.
6. Logs the action with `request_id` correlation.

## Notes

- **Versioned** under `/v1` so future breaking changes don't break clients.
- **Idempotency** on send/booking endpoints to avoid duplicates on retry.
- **Rate limiting** per business on dashboard endpoints.
- Full OpenAPI spec auto-generated by FastAPI; this doc is the human-readable contract.
