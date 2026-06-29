# Database Design

Status: **Accepted** (2026-06-29). See `DECISIONS.md` DEC-013.
Engine: PostgreSQL + `pgvector`. Multi-tenant; every business-owned row carries `business_id`.

---

## Entities

### `businesses`
The tenant. One row per customer business using HIRA.
- `id` (PK, uuid)
- `name`, `vertical` (nullable until vertical strategy firms up), `timezone`
- `whatsapp_phone_number_id`, `whatsapp_business_account_id`
- `mode` enum(`assisted`, `autonomous`) — default `assisted`
- `created_at`, `updated_at`

### `users`
Dashboard users (owner/staff) belonging to a business. Auth identity lives in Clerk; this mirrors it.
- `id` (PK, uuid), `business_id` (FK → businesses)
- `clerk_user_id` (unique), `email`, `role` enum(`owner`, `staff`)
- `created_at`

### `customers`
End customers who message the business on WhatsApp.
- `id` (PK, uuid), `business_id` (FK)
- `wa_phone` (the customer's WhatsApp number), `display_name` (nullable)
- `created_at`
- unique(`business_id`, `wa_phone`)

### `conversations`
A thread between a customer and the business.
- `id` (PK, uuid), `business_id` (FK), `customer_id` (FK)
- `status` enum(`active`, `escalated`, `closed`)
- `window_expires_at` (timestamp — the 24h service window)
- `last_message_at`, `created_at`

### `messages`
Individual inbound/outbound messages.
- `id` (PK, uuid), `conversation_id` (FK), `business_id` (FK, denormalized for scoping)
- `direction` enum(`inbound`, `outbound`)
- `wa_message_id` (unique — dedupe key), `body`, `type` (text/template/etc.)
- `status` enum(`received`, `pending_approval`, `sent`, `failed`) — `pending_approval` drives Assisted Mode
- `ai_meta` (jsonb — model, prompt version, intent, confidence, tool calls) for the AI audit log
- `created_at`

### `kb_entries`
Knowledge-base items powering FAQ answers.
- `id` (PK, uuid), `business_id` (FK)
- `question`/`title`, `content`
- `embedding` (vector, pgvector) — for semantic search
- `created_at`, `updated_at`

### `appointments`
Bookings made on the business's behalf.
- `id` (PK, uuid), `business_id` (FK), `customer_id` (FK), `conversation_id` (FK, nullable)
- `google_event_id` (nullable), `starts_at`, `ends_at`, `status` enum(`booked`, `rescheduled`, `cancelled`)
- `created_at`, `updated_at`

### `escalations`
Conversations handed to a human.
- `id` (PK, uuid), `business_id` (FK), `conversation_id` (FK)
- `reason` enum(`low_confidence`, `customer_request`, `external_failure`, `other`)
- `status` enum(`open`, `resolved`), `resolved_by` (FK → users, nullable)
- `created_at`, `resolved_at`

### `calendar_credentials`
Per-business Google OAuth tokens.
- `id` (PK, uuid), `business_id` (FK, unique)
- `refresh_token_encrypted`, `calendar_id`, `scopes`
- `created_at`, `updated_at`

---

## Relationships

```
businesses 1───∞ users
businesses 1───∞ customers
businesses 1───∞ conversations          customers 1───∞ conversations
conversations 1───∞ messages
businesses 1───∞ kb_entries
businesses 1───∞ appointments           customers 1───∞ appointments
conversations 1───∞ appointments (0..1 per booking)
conversations 1───∞ escalations
businesses 1───1 calendar_credentials
```

## Indexes

- `messages (wa_message_id)` unique — dedupe.
- `messages (conversation_id, created_at)` — thread loading.
- `conversations (business_id, status, last_message_at)` — Inbox queries.
- `customers (business_id, wa_phone)` unique — lookup on inbound.
- `appointments (business_id, starts_at)` — calendar views.
- `escalations (business_id, status)` — open-escalation list.
- `kb_entries` — pgvector index (e.g., HNSW/IVFFlat) on `embedding`.
- Every tenant-scoped table indexed on `business_id`.

## Future Expansion Strategy

- **Autonomous Mode**: already modeled via `businesses.mode` and `messages.status` — no schema change needed to relax the approval gate.
- **AI Business OS (multiple AI roles)**: introduce an `agents`/`roles` table; `conversations` and `messages` gain an optional `agent_id`. Receptionist becomes one role among many. Additive, non-breaking.
- **Multiple WhatsApp numbers / locations per business**: extract a `channels` table rather than columns on `businesses`.
- **Document-based KB**: add a `kb_documents` table + object storage reference; `kb_entries` become chunks of a document.
- **Analytics**: derive from `messages`/`appointments`/`escalations`; add rollup tables only if query cost demands it.
- All changes via reversible migrations; never destructive in place.
