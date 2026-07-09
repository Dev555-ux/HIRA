# REST API Design

Status: **Accepted** (2026-06-29). See `DECISIONS.md` DEC-014, DEC-025.
Base path: `/api/v1`. Auth: Clerk JWT (dashboard endpoints) / Meta signature (webhook). All dashboard endpoints are tenant-scoped to the caller's `business_id`.

**Implemented so far** (as of 2026-07-09): `GET /api/v1/pending`; `/messages/{id}/approve`, `/draft` (`PATCH`), `/reject`, `/regenerate`, `/escalate` (see Assisted-Mode Approvals below — Sprint 27); `GET/POST/PATCH/DELETE /api/v1/kb` (+ `/kb/website`); `GET/POST /api/v1/onboarding/*` (+ `/playground/message`); `GET/PATCH /api/v1/settings` (AI Reply Mode only); `GET /api/v1/conversations`, `/conversations/{id}`, `/conversations/{id}/messages` (see the Conversations section below for exact query params — this is a smaller slice of the originally-sketched Conversations API: the two `POST` actions there are not built). All protected by Clerk JWT via `get_current_principal` (resolves the Clerk user → local `User` → `business_id`). Cross-tenant access returns `404`. Verification: RS256 against Clerk JWKS (`CLERK_JWKS_URL`). A dedicated `GET /escalations` list endpoint is still to be built — escalations are created (Sprint 27) but not yet listable. Remaining endpoints below (Appointments/Calendar, most of Settings) are still to be built.

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

### Assisted-Mode Approvals

The full "Pending Approvals V2" copilot workflow (Sprint 27, 2026-07-09): every outbound AI-drafted reply is a `Message` row with `status="pending_approval"`. From there a human can edit, approve, reject, regenerate, or escalate it — see `backend/app/services/replies.py`. Every route below sits behind `get_current_principal`, is tenant-scoped via `get_scoped`, and returns `404` (not a distinguishing error) if the message doesn't exist, belongs to another business, or is no longer a pending reply (already approved/rejected/escalated) — same convention `approve` already used.

- `GET /pending` — **implemented**. Outbound messages awaiting approval, oldest first. Each row now also includes `customer` (`id`/`display_name`/`wa_phone`, joined via the conversation) and `conversation_preview` (the most recent inbound message in that conversation) — additive fields, not a breaking change to the existing shape.
- `PATCH /messages/{id}/draft` — **implemented**. Body: `{"body": "<edited text>"}`. Edits the pending draft's text in place before approval. Validates non-blank (`422`) and a max length of 4096 characters (`422`) — WhatsApp Cloud API's text message body limit, the same boundary `send_text` would eventually hit. Returns the updated `{id, body, status}`.
- `POST /messages/{id}/approve` — **implemented**. Sends the (possibly just-edited) draft via WhatsApp and marks it `sent`, or `failed` if the send errors (`502`).
- `POST /messages/{id}/reject` — **implemented**. Marks the message `rejected`; never calls the messaging service. Returns `{id, status}`.
- `POST /messages/{id}/regenerate` — **implemented**. Re-runs the unmodified `generate_reply()` pipeline (same retrieval + prompt + LLM call the WhatsApp webhook uses) against the customer message that originally triggered this draft, and replaces this message's `body`/`ai_meta` in place — conversation history and the approval workflow are untouched. `502` if the LLM call fails; `404` if there's no customer message to respond to. Returns `{id, body, status}`.
- `POST /messages/{id}/escalate` — **implemented**. Marks the message `escalated`, marks the parent `Conversation.status = "escalated"` (a previously-unused, already-modeled status value), and creates an `Escalation` row (`reason="other"` — no UI collects a specific reason yet). Conversation history is untouched. Returns `{id, status, escalation: {id, conversation_id, reason, status, created_at}}`.

`Message.status` values as of Sprint 27: `received | pending_approval | sent | failed | rejected | escalated` — all plain strings (no CHECK constraint / migration needed to add a value, per `DATABASE.md`).

### Escalations
- `GET /escalations?status=open` — **not implemented**. `Escalation` rows are created by `POST /messages/{id}/escalate` (above) but there is no list/detail endpoint yet — see `.claude/DECISIONS.md` DEC-030.
- `POST /escalations/{id}/resolve` — **not implemented**.

### Appointments / Calendar
- `GET /appointments?from=&to=` — calendar view.
- `POST /appointments` — manual create.
- `PATCH /appointments/{id}` — reschedule/cancel.
- `GET /calendar/availability?date=` — free slots (proxies Google Calendar).

### Knowledge Base
- `GET /kb` — list entries.
- `POST /kb` — create entry (triggers embedding).
- `PATCH /kb/{id}` — update (re-embed).
- `DELETE /kb/{id}` — remove.

### Settings
- `GET /business` / `PATCH /business` — profile, timezone, `mode` (assisted/autonomous).
- `POST /integrations/google/connect` — start Google OAuth.
- `GET /integrations/google/callback` — OAuth callback, stores encrypted refresh token.
- `GET /integrations/whatsapp` / `PATCH /integrations/whatsapp` — WhatsApp number config.

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
