# REST API Design

Status: **Accepted** (2026-06-29). See `DECISIONS.md` DEC-014, DEC-025.
Base path: `/api/v1`. Auth: Clerk JWT (dashboard endpoints) / Meta signature (webhook). All dashboard endpoints are tenant-scoped to the caller's `business_id`.

**Implemented so far** (as of 2026-07-10): `GET /api/v1/pending`; `/messages/{id}/approve`, `/draft` (`PATCH`), `/reject`, `/regenerate`, `/escalate` (see Assisted-Mode Approvals below — Sprint 27); `GET/POST/PATCH/DELETE /api/v1/kb` (+ `/kb/website`); `GET/POST /api/v1/onboarding/*` (+ `/playground/message`); `GET/PATCH /api/v1/settings` (AI Reply Mode only); `GET /api/v1/conversations`, `/conversations/{id}`, `/conversations/{id}/messages` (see the Conversations section below for exact query params — this is a smaller slice of the originally-sketched Conversations API: the two `POST` actions there are not built); `GET/POST/PATCH/DELETE /api/v1/leads` and `GET /api/v1/customers`, `/customers/{id}`, `/customers/{id}/timeline` (CRM Foundation — Sprint 28, see below and DEC-031); `/api/v1/calendar/*` (OAuth connect/callback, status, disconnect, settings, availability) and `GET/POST /api/v1/appointments` (+ `/{id}/reschedule`, `/{id}/cancel`) (Google Calendar Integration — Sprint 29, see below and DEC-032). No new REST endpoints in Sprint 30 (2026-07-10, DEC-033) — that sprint only registered `create_lead`/`update_lead_stage`/`set_lead_follow_up` as AI tools against the existing Leads API/schema (see AI booking & CRM tools below). No new REST endpoints in Sprint 31 either (2026-07-10, DEC-034) — the AI Memory & Context Engine (`app/ai/context.py`, `app/ai/memory.py`) is purely an internal AI-pipeline capability with no API surface of its own; it only changes what's assembled before an LLM call, not any endpoint's request/response shape. All protected by Clerk JWT via `get_current_principal` (resolves the Clerk user → local `User` → `business_id`), **except** the calendar OAuth callback, which is a public Google browser redirect authenticated by a signed `state` param instead. Cross-tenant access returns `404`. Verification: RS256 against Clerk JWKS (`CLERK_JWKS_URL`). A dedicated `GET /escalations` list endpoint is still to be built — escalations are created (Sprint 27) but not yet listable. Remaining endpoints below (most of Settings, Users) are still to be built.

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
- `GET /conversations` — **implemented** (2026-07-08; `escalated` filter added Sprint 69). Query params: `search` (matches customer display name or WhatsApp number), `status` (`open` → `Conversation.status == "active"`; `closed` → `"closed"`; `escalated` → `"escalated"`; `pending` → has an outbound message with `status == "pending_approval"`, a derived cross-cutting view, not a `Conversation.status` value — omit for no filter), `limit`/`offset` (pagination, `{"data": [...], "meta": {"total", "limit", "offset"}}`). Each row includes the joined `customer` (id/display_name/wa_phone), `last_message_at`-ordered, a `preview` (latest message body), and `has_pending_approval`.
- `GET /conversations/{id}` — **implemented**. Same summary shape as the list. Cross-tenant/unknown → `404`.
- `GET /conversations/{id}/messages` — **implemented**. Paginated (`limit`/`offset`), returns the most recent page in oldest-first order (same convention as `app/ai/orchestrator.py`'s history loader). Cross-tenant/unknown conversation → `404`.
- `POST /conversations/{id}/messages` — **not implemented** — human sends a manual reply. Originally sketched here; not part of the Inbox v1 scope.
- `POST /conversations/{id}/close` — **not implemented** — close the thread. Originally sketched here; not part of the Inbox v1 scope.

### Leads (CRM pipeline)

CRM Foundation (Sprint 28, 2026-07-09, see DEC-031). One `Lead` per `(business, customer)` — `UNIQUE(business_id, customer_id)`, so a repeat inquiry updates the existing lead rather than creating a second one. Every route sits behind `get_current_principal`, is tenant-scoped, and returns `404` if the lead/customer doesn't exist or belongs to another business (same convention as every other resource here) — see `backend/app/services/leads.py`. As of Sprint 30 (2026-07-10, DEC-033), the AI can also create/update leads via tool calls during a conversation, through this exact same service layer — see AI booking & CRM tools below.

- `GET /leads` — **implemented**. Query params: `search` (matches the linked customer's display name or WhatsApp number), `stage` (one of the seven values below), `limit`/`offset` (pagination, `{"data": [...], "meta": {"total", "limit", "offset"}}`, ordered by `updated_at desc`). Each row includes the joined `customer` (`id`/`display_name`/`wa_phone`).
- `POST /leads` — **implemented**. Body: `{"customer_id", "stage"?, "source"?, "estimated_value"?, "notes"?, "next_follow_up_at"?, "assigned_to"?}` (`stage` defaults to `"new"`). `404` if `customer_id` doesn't belong to this business; `409` if this business already has a lead for that customer; `422` if `assigned_to` doesn't reference a user of this business, `stage` isn't one of the seven valid values, or `estimated_value` is negative (Sprint 35 — previously unvalidated). Logs a `lead_created` `LeadEvent`.
- `GET /leads/{id}` — **implemented**.
- `PATCH /leads/{id}` — **implemented**. Body: any subset of the fields above (same `estimated_value >= 0` validation as `POST`). At least one required (`422` on an empty body). Omitting a field leaves it untouched; sending it as JSON `null` explicitly clears it (`source`/`estimated_value`/`notes`/`next_follow_up_at`/`assigned_to` are all nullable-and-clearable this way). Logs a `LeadEvent` for `stage`/`notes`/`next_follow_up_at`/`assigned_to` changes — but only when the new value actually differs from the old one, and never for `source`/`estimated_value` (treated as descriptive attributes, not pipeline activity).
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
- `POST /messages/{id}/approve` — **implemented**. If `message.type == "tool_call"` (a proposed calendar action — Sprint 29, DEC-032 — or CRM action — Sprint 30, DEC-033), executes it first via the single `execute_tool_call` dispatcher (`app/ai/tools.py`), which routes to `AppointmentService` or `app/ai/lead_tools.py` by tool name (`409`/`404`/etc. from `map_calendar_error` if a calendar tool fails, leaving the message `failed`; a CRM tool failure — e.g. a lead already exists — also leaves the message `failed` with the failure reason in `ai_meta.tool_result`); either way, then sends the (possibly just-edited) `body` via WhatsApp and marks it `sent`, or `failed` if the send errors (`502`).
- `POST /messages/{id}/reject` — **implemented**. Marks the message `rejected`; never calls the messaging service, never executes a proposed tool call. Returns `{id, status}`.
- `POST /messages/{id}/regenerate` — **implemented**. Re-runs the unmodified `generate_reply()` pipeline (same retrieval + prompt + LLM call the WhatsApp webhook uses, including the calendar and CRM tool schemas as of Sprint 29/30) against the customer message that originally triggered this draft, and replaces this message's `body`/`type`/`ai_meta` in place — a draft can flip between plain text and a proposed tool call on regenerate. Conversation history and the approval workflow are untouched. `502` if the LLM call fails; `404` if there's no customer message to respond to. Returns `{id, body, status}`.
- `POST /messages/{id}/escalate` — **implemented**. Marks the message `escalated`, marks the parent `Conversation.status = "escalated"` (a previously-unused, already-modeled status value), and creates an `Escalation` row (`reason="other"` — no UI collects a specific reason yet). Conversation history is untouched. Returns `{id, status, escalation: {id, conversation_id, reason, status, created_at}}`.

`Message.status` values as of Sprint 27: `received | pending_approval | sent | failed | rejected | escalated` — all plain strings (no CHECK constraint / migration needed to add a value, per `DATABASE.md`). `Message.type` gained `tool_call` in Sprint 29 (DEC-032) alongside the original `text` — a pending `tool_call` message's `body` is a human-readable, editable preview/confirmation string, and `ai_meta` carries `{tool_name, tool_arguments}`. Sprint 30 (DEC-033) reuses this exact same convention for CRM tool calls (`create_lead`/`update_lead_stage`/`set_lead_follow_up`) — no new `Message.type` value.

### Escalations (Escalation Queue Workspace, Sprint 69 — DEC-040)
- `GET /escalations` — **implemented**. Query params: `status` (`open`/`resolved`), `assigned` (`mine` → `Escalation.assigned_to == principal.user_id`; `unassigned` → `assigned_to IS NULL`), `limit`/`offset`. Each row joins its `Conversation`/`Customer` for context and includes `assigned_to`/`resolved_by` as `{id, email} | null` (not a bare UUID). `{"data": [...], "meta": {"total", "limit", "offset"}}`.
- `POST /escalations/{id}/assign` — **implemented**. Self-claim only — always assigns to the calling principal, since there is no team roster/user-picker UI to assign a colleague's escalation for them.
- `POST /escalations/{id}/unassign` — **implemented**. Clears `assigned_to`.
- `POST /escalations/{id}/resolve` — **implemented**. Sets `status="resolved"`, `resolved_by=principal.user_id`, `resolved_at=now()`. No reopen endpoint (out of scope this sprint).
- All four routes are tenant-scoped via `get_scoped`/an explicit `business_id` filter and return `404` (not a distinguishing error) for another business's escalation, same convention as `dashboard.py`.

### Calendar

HIRA Calendar, with optional Google Calendar Sync (Sprint 29, 2026-07-10, DEC-032; promoted to the default scheduling experience in Sprint 78/79 — see DEC-032's own update). Booking always goes through `AppointmentService` (`app/calendar/factory.py::get_appointment_service`), which now resolves to one of two providers transparently: `GoogleCalendarProvider` if the business has connected Google Calendar, otherwise `InternalSchedulerProvider` ("HIRA Calendar" — internal-only name, never customer-facing) backed directly by this business's own `Appointment` rows. Neither this route nor its callers know or care which is active. `CalendarError` subtypes map to HTTP statuses uniformly across this section and Appointments (`app/api/calendar.py::map_calendar_error`): not-configured (missing `GOOGLE_CLIENT_ID`/`CALENDAR_ENCRYPTION_KEY` — only reachable while actually connecting Google Sync, never for a plain HIRA Calendar booking) → `503`; auth failure (expired/revoked Google token) / slot conflict (either provider) → `409`; event not found → `404`; provider unavailable → `502`.

- `GET /calendar/settings` — **implemented**. Returns `{timezone, working_hours}` (see `Business.working_hours` in `DATABASE.md`/`ARCHITECTURE.md`; `null` means not configured).
- `PATCH /calendar/settings` — **implemented**. Body: any subset of `{timezone, working_hours}`; at least one required (`422` on an empty body). `timezone` validated as a real IANA zone (`zoneinfo`); `working_hours` validated per-day (`HH:MM` 24-hour format, unknown day keys rejected, and — Sprint 35 — `close` must be after `open`; previously unvalidated, so a business could silently save backwards hours) — all `422` on failure.
- `GET /calendar/oauth/connect` — **implemented**. Authenticated; returns `{authorization_url}` — the Google consent-screen URL to redirect the browser to, with an HMAC-signed `state` param encoding the business id (10-minute expiry). `503` if OAuth isn't configured on this deployment.
- `GET /calendar/oauth/callback` — **implemented**. **Public** — Google redirects the user's browser here directly after consent, with no Clerk session; authenticated instead by verifying `state`'s signature (same pattern as the WhatsApp webhook's HMAC signature, not a Bearer token). Exchanges the authorization `code` for a refresh token, encrypts and stores it, then **redirects** (not a JSON response) to `{FRONTEND_URL}/calendar?calendar=connected` or `?calendar=error&message=...`.
- `GET /calendar/status` — **implemented**. `{connected: bool, calendar_id: string | null}`.
- `DELETE /calendar/disconnect` — **implemented**. Removes the stored `CalendarCredential`. `204` whether or not one existed.
- `GET /calendar/availability?starts_at=&ends_at=` — **implemented**. Free slots (`[{starts_at, ends_at}, ...]`) within the given window — from `AppointmentService.list_availability()`, which computes Google's real free/busy and then clips it to the business's `working_hours`/`timezone` if configured. `422` if `ends_at <= starts_at`.

### Appointments

- `GET /appointments?from=&to=` — **implemented**. Both optional; filters `Appointment.starts_at`. No pagination — the date range is the natural bound (unlike the paginated list endpoints elsewhere in this API).
- `POST /appointments` — **implemented**. Body: `{customer_id, starts_at, ends_at, summary, conversation_id?}`. `404` if `customer_id` doesn't belong to this business; `422` if `ends_at <= starts_at`; `409` if the slot is taken — either provider pre-checks for conflicts before writing (`GoogleCalendarProvider.create_event` via `freebusy`, since Google's API doesn't reject overlaps on its own; `InternalSchedulerProvider.create_event` via a direct query over this business's own `Appointment` rows).
- `GET /appointments/{id}` — **implemented**.
- `POST /appointments/{id}/reschedule` — **implemented**. Body: `{starts_at, ends_at}`. `404` if not found/another business's; `422` if `ends_at <= starts_at`.
- `POST /appointments/{id}/cancel` — **implemented**. No body.

`Appointment.status` values: `booked | rescheduled | cancelled` (unchanged since the original schema — DEC-013).

### AI booking & CRM tools

The orchestrator (`app/ai/orchestrator.py::generate_reply`) passes the model only the tool schemas `app/ai/plan.py::build_execution_plan()` decides are relevant to the message (Sprint 57 tool routing, generalized to multiple domains in Sprint 75/DEC-045 — see `ExecutionPlan` below) — never an unconditional fixed set. The full catalog those schemas are drawn from is the four calendar tools from Sprint 29 — `check_availability`, `book_appointment`, `reschedule_appointment`, `cancel_appointment` — and three CRM tools added in Sprint 30 (DEC-033, `app/ai/lead_tools.py`):

- `create_lead` — logs the customer as a lead (optional `source`, `notes`). Fails gracefully (not surfaced as an error to the customer) if a lead already exists for them (`UNIQUE(business_id, customer_id)`, DEC-031).
- `update_lead_stage` — moves the customer's existing lead to a new pipeline stage (same seven-value set as `PATCH /leads/{id}`). Fails gracefully if no lead exists yet.
- `set_lead_follow_up` — schedules `next_follow_up_at` on the customer's existing lead. Fails gracefully if no lead exists yet.

`check_availability` is read-only and resolved automatically inside `generate_reply` (executed immediately, its result fed back for one bounded follow-up model call — never surfaced as something to approve). Every other tool — the three calendar writes and all three CRM tools — is *not* executed inline: see Assisted-Mode Approvals above. In Assisted Mode it becomes a `pending_approval` message with `type="tool_call"`; approving it (`POST /messages/{id}/approve`) executes the tool — via `AppointmentService` for a calendar tool, via `app/services/leads.py` for a CRM tool, both through the single `execute_tool_call` dispatcher — before sending the confirmation. In Autonomous Mode the tool executes immediately, same as autonomous text-sending (DEC-027).

**Multiple actions per turn (Sprint 74/75, DEC-043/DEC-045)**: the model may propose up to `app/ai/tools.py::MAX_TOOL_CALLS_PER_TURN` (2) tool calls in one response — `response_to_message_fields()` turns each into its own independent Message row, attributed to the Employee Registry role that owns it (`app/ai/roles.py::role_for_tool`, e.g. `scheduler`, `sales_executive`). Each call still goes through the exact same approval/execution path as a single call. A cross-domain turn (e.g. "reschedule my appointment and log this as a lead") is only offered both domains' tools if the *first* domain's action already cleared readiness and governance (`app/ai/plan.py::build_execution_plan`, DEC-046) — a policy-gated first action means the second domain's tools are withheld entirely for that turn, never offered "alongside" an ungoverned one. `regenerate_draft` (`POST /messages/{id}/regenerate`) is the one exception: it only ever consumes the first proposed action, since it replaces one already-existing Message in place.

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

### Founder Operations Dashboard (Sprint 73)

Internal-only, read-only, cross-tenant (see `app/api/founder_ops.py`, `app/services/founder_ops.py`). Not part of the tenant-scoped convention above — deliberately spans every business, for the founder's own operational visibility during beta. **Not customer-facing.**

- **Auth**: `Authorization: Bearer <clerk_jwt>`, same as every other dashboard endpoint — but checked against `FOUNDER_CLERK_USER_IDS` (a comma-separated allowlist of Clerk user ids in Railway's Variables tab / `backend/.env`), not resolved to a `business_id`. Any authenticated caller not on the allowlist gets `404` (not `403`) — same "don't confirm a resource exists" convention as cross-tenant access elsewhere in this API. No token → `401`, same as everywhere else. An empty/unset allowlist means every caller gets `404` — the feature is off by default, not open by default.
- `GET /founder/overview` — **implemented**. One response covering every section of the dashboard:
  - `data.summary` — `total_businesses`, `connected_businesses`, `active_businesses` (at least one message in the last 24h), `messages_today`/`ai_responses_today`/`failed_responses_today` (UTC calendar-day boundary), `avg_response_time_seconds` (platform-wide average, see below).
  - `data.businesses[]` — one row per business (all businesses, newest-created first — no pagination yet, see Notes below), each with:
    - `name`, `created_at`, `onboarding_status` (raw `Business.onboarding_status`), `onboarding_complete` (derived: published KB entries exist **and** WhatsApp is connected — the same two prerequisites the customer-facing onboarding checklist already gates "Go Live" on).
    - `whatsapp`: `status`, `display_phone_number`, `credential_stored` (a `WhatsAppCredential` row exists), `last_inbound_at`, `last_outbound_at`.
    - `knowledge_base`: `published_count`, `draft_count`, `last_updated_at`.
    - `ai_activity`: `conversations`, `ai_responses` (outbound message count), `failed_responses` (all-time `Message.status == "failed"` count), `avg_response_time_seconds`.
    - `last_activity_at` — most recent message of either direction.
    - `alerts[]` — any of `whatsapp_disconnected`, `missing_knowledge_base` (zero published entries — a business with only unreviewed drafts still triggers this), `ai_failures` (a failed message in the last 24h — an old failure alone does not), `no_recent_activity` (a *connected* business with no message in the last 7 days; not applied to businesses that were never connected, since that's already covered by `whatsapp_disconnected` and isn't a meaningful additional signal).
  - **Response time** is computed per conversation turn (an outbound message immediately following an inbound one, via a `LAG()` window function — not fetched into Python and paired by hand), then averaged — both per-business and platform-wide. Two outbound messages in a row are not counted as a turn.

**Notes**: No mutation endpoints exist on this router by design ("read-only, no destructive actions"). No pagination on `businesses[]` yet — fine at current beta scale (all aggregate queries are grouped/bulk, not per-business, so query *count* doesn't grow with business count; only response *size* would, eventually) — add `limit`/`offset` here first if that becomes a real constraint, matching every other list endpoint's convention.

### AI Employee Observability (Sprint 76)

Also on the Founder Operations router — same auth, same `FOUNDER_CLERK_USER_IDS` allowlist, same 404-not-403 convention as above.

- `GET /founder/ai-metrics` — **implemented**. Platform-wide aggregates over every `ExecutionTrace` row (see `app/services/execution_traces.py`, `app/services/founder_ops.py::get_ai_metrics`):
  - `total_turns`, `employee_utilisation` (`{role: count}`, from `proposed_tool_calls[].agent_role`), `most_used_employee`, `most_used_tools` (top 5, `[{tool_name, count}]`), `avg_plan_length` (mean steps per plan), `avg_execution_time_ms`.
  - `failed_tool_executions` — traces with at least one proposed tool call whose result Message currently resolves to `outcome == "failed"` (see below). **Known asymmetry**: Demo Chat never sets a Message's status to `"failed"` for a failed tool call (it resolves the failure into ordinary `"sent"` text instead — pre-existing Sprint 74 behavior), so this undercounts failures that happened in Demo Chat specifically; real WhatsApp/Autonomous Mode failures are captured correctly.
  - `governance_blocks` — a **proxy**, not an exact count: traces where `plan.clarification_hint` is non-null. This covers both "governance withheld an action" and "planning wasn't ready yet" (missing details) — the two aren't distinguishable from a trace alone today.
- `GET /founder/traces` — **implemented**. Conversation Replay list. Query params: `business_id` (optional, filters to one business), `limit` (default 50, max 200), `offset` (default 0). Returns `data: [{id, business_id, business_name, category, plan_step_count, roles, outcome, duration_ms, created_at}]`, newest first.
- `GET /founder/traces/{id}` — **implemented**. Conversation Replay detail — the full "why did HIRA do that" view for one turn: `data: {id, business_id, business_name, conversation_id, category, customer_message, plan, proposed_tool_calls, result_messages, outcome, duration_ms, created_at}`. `plan` is the `ExecutionPlan` actually built (`{category, steps: [{domain, action, role, tools}], clarification_hint}`). `result_messages` is each turn's outbound `Message` row(s), resolved to their *current* state at request time (`{id, type, body, status, ai_meta}`), not frozen at trace-write time. `404` for an unknown id, same as any other not-found resource.
- `outcome` (both endpoints above) is derived at read time from `result_messages`' current statuses, one of: `sent`, `pending_approval`, `sending`, `failed`, `rejected`, `escalated`, `no_result` (no Message was ever produced — a non-action turn). Priority order when a turn produced more than one Message: `failed` > `escalated` > `rejected` > `pending_approval` > `sending` > `sent`.

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
