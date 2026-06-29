# MVP Architecture

Status: **Accepted** (2026-06-29). See `DECISIONS.md` DEC-012.
Scope: the Assisted-Mode AI Receptionist MVP. Vertical-agnostic core; no vertical-specific logic hard-coded.

Related: `WHATSAPP_INTEGRATION.md`, `TECH_STACK.md`, `DATABASE.md`, `API.md`, `FRONTEND.md`.

---

## 1. System Architecture (high level)

```
                        ┌─────────────────────────────────────────────┐
   Customer (WhatsApp)  │                  HIRA Backend                │
        │               │                 (FastAPI, Railway)           │
        │  inbound msg   │                                             │
        ▼               │   ┌──────────────┐    ┌──────────────────┐  │
  ┌───────────┐ webhook │   │  Webhook     │───▶│  Conversation    │  │
  │ Meta Cloud│────────▶│   │  Handler     │    │  Orchestrator    │  │
  │   API     │◀────────│   │ (verify sig) │    │  (AI engine)     │  │
  └───────────┘ send    │   └──────────────┘    └────────┬─────────┘  │
                        │                                 │            │
                        │        ┌────────────────────────┼─────────┐ │
                        │        ▼            ▼            ▼         ▼ │
                        │   ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌────────┐
                        │   │ Claude  │ │ KB        │ │ Calendar│ │Escala- │
                        │   │ (LLM)   │ │ retrieval │ │ service │ │ tion   │
                        │   └─────────┘ │ (pgvector)│ │(Google) │ │ service│
                        │               └──────────┘ └────┬────┘ └───┬────┘
                        │                                  │          │
                        │        ┌─────────────────────────┼──────────┘
                        │        ▼                          ▼
                        │   ┌───────────────────────────────────────┐
                        │   │     PostgreSQL (+ pgvector)            │
                        │   │  businesses, conversations, messages,  │
                        │   │  appointments, kb_entries, escalations │
                        │   └───────────────────────────────────────┘
                        └─────────────────────────────────────────────┘
                                          ▲
                                          │ REST API (JWT via Clerk)
                                          │
                        ┌─────────────────┴───────────────┐
                        │   Dashboard (Next.js, Vercel)    │
                        │  Inbox · Calendar · KB · Settings │
                        └──────────────────────────────────┘
                              ▲
                              │ Business owner / staff
```

External dependencies: **Meta Cloud API** (messaging), **Anthropic Claude** (reasoning), **Google Calendar API** (scheduling), **Clerk** (dashboard auth).

---

## 2. Components

| Component | Responsibility |
|---|---|
| **Webhook Handler** | Receives Meta webhooks, verifies signature (`X-Hub-Signature-256`), deduplicates by message ID, enqueues for processing, returns 200 fast. |
| **Conversation Orchestrator (AI engine)** | The core loop. Loads conversation context, classifies intent, retrieves KB, decides: answer / call a tool / escalate. Lives in `ai/`. |
| **KB Retrieval** | Embeds the incoming question, vector-searches `kb_entries` (pgvector), returns top matches as grounding context. |
| **Calendar Service** | Wraps Google Calendar API: check availability, create, reschedule, cancel events. |
| **Escalation Service** | Flags a conversation for human handling, surfaces it in the dashboard Inbox, pauses autonomous replies. |
| **Messaging Service** | Sends outbound WhatsApp messages via Cloud API; manages the 24h-window vs. template distinction. |
| **Dashboard API** | REST endpoints the Next.js frontend consumes (see `API.md`). |
| **Persistence** | PostgreSQL; all state of record (see `DATABASE.md`). |

---

## 3. Data Flow — inbound customer message

1. Customer sends a WhatsApp message → Meta delivers a webhook POST to HIRA.
2. **Webhook Handler** verifies the signature, dedupes by `wa_message_id`, persists the inbound `message`, returns `200` immediately.
3. Message is dispatched to the **Conversation Orchestrator** (async/background task).
4. Orchestrator loads the `conversation` + recent `messages` for context and the `business` config.
5. **Intent classification** (Haiku): FAQ / booking / reschedule / cancel / human-request / unknown.
6. Branch:
   - **FAQ** → KB retrieval → Claude composes a grounded answer.
   - **Booking/Reschedule/Cancel** → Claude calls the matching tool → Calendar Service executes → confirmation drafted.
   - **Uncertain / low confidence / explicit human request** → **Escalation Service**.
7. **Assisted Mode gate**: the drafted reply/action is saved as `pending` and surfaced in the Inbox for human approval; on approval (or auto-approve per business setting) the **Messaging Service** sends it. *(Autonomous Mode later removes the gate for high-confidence actions.)*
8. Outbound `message` persisted; conversation state updated.

---

## 4. AI Workflow

```
inbound text
   │
   ▼
[Haiku] intent + confidence ──low conf──▶ Escalation
   │ high conf
   ▼
route by intent
   ├─ FAQ ─────▶ pgvector KB search ─▶ [Sonnet] grounded answer
   ├─ booking ─▶ [Sonnet] + tool: check_availability / book_appointment
   ├─ reschedule▶ [Sonnet] + tool: reschedule_appointment
   ├─ cancel ───▶ [Sonnet] + tool: cancel_appointment
   └─ human ────▶ Escalation
   │
   ▼
draft reply/action ─▶ Assisted-Mode approval gate ─▶ send
```

**Tools exposed to the model** (defined in `ai/`, schemas version-controlled): `search_knowledge_base`, `check_availability`, `book_appointment`, `reschedule_appointment`, `cancel_appointment`, `escalate_to_human`.

**AI-specific safeguards** (CLAUDE.md §11): every model input/output is logged; low-confidence → escalate rather than guess; KB answers are grounded in retrieved entries to limit hallucination; prompts live in `prompts/` and are versioned.

---

## 5. Authentication

- **Dashboard users** (business owner/staff): **Clerk** issues JWTs; backend validates the JWT on every dashboard API request and resolves the user → `business_id` for tenant scoping.
- **Meta webhooks**: verified via `hub.verify_token` (subscription) and `X-Hub-Signature-256` HMAC on every payload.
- **Google Calendar**: per-business **OAuth 2.0**; refresh tokens stored encrypted, scoped to that business.
- **Anthropic / Meta secrets**: server-side only, via environment/secret manager — never in the frontend or repo.

---

## 6. Storage

- **PostgreSQL** — system of record (see `DATABASE.md`).
- **pgvector** — KB embeddings, same instance.
- **Object storage** (only if needed for KB document uploads, e.g., PDFs) — deferred until a real need; start with text KB entries.
- **Secrets** — Railway/Vercel env vars (or a secret manager); OAuth refresh tokens encrypted at rest.

---

## 7. Deployment

- **Backend + Postgres**: Railway. Two environments — `staging` and `production`.
- **Frontend**: Vercel (preview deploys per branch, production on main).
- **CI**: lint + type-check + tests on every push (see Sprint 1).
- **Secrets** per environment; no shared prod credentials in staging.
- **Rollback**: redeploy previous build; DB changes via reversible migrations.

---

## 8. Error Handling

- **Webhooks**: always return `200` once persisted; never let downstream failures cause Meta retries to pile up. Processing failures are retried via the job/background layer with backoff.
- **External APIs (Meta, Google, Anthropic)**: timeouts + bounded retries with exponential backoff; on persistent failure, **escalate to human** rather than drop the customer.
- **LLM tool calls**: validate tool arguments before execution; never trust model output as a side-effect command without validation (e.g., confirm the slot is free before booking).
- **User-facing failures**: the customer gets a graceful "let me get a colleague to help" and the conversation escalates.
- **Idempotency**: dedupe inbound by `wa_message_id`; booking writes guarded against duplicates.

---

## 9. Logging & Observability

- **Structured logs** (JSON) with a correlation/conversation ID across the whole message lifecycle.
- **AI audit log**: for each turn, store model, prompt version, inputs given, tool calls, and output — required for debugging AI behavior (CLAUDE.md §11).
- **Error tracking**: Sentry (or equivalent) on backend and frontend.
- **Minimal metrics** for the pilot: messages handled, escalation rate, bookings created, AI failures. (Detailed analytics deferred.)

---

## 10. Security

- **Multi-tenant isolation**: every query scoped by `business_id`; no cross-tenant data access. This is the highest-risk area for a multi-tenant SaaS — enforced at the data-access layer, not just the route.
- **Secrets**: never in code/logs/frontend; OAuth refresh tokens encrypted at rest.
- **Webhook authenticity**: HMAC signature verification on all Meta payloads.
- **Input validation** at every trust boundary (webhook payloads, dashboard API, tool arguments).
- **PII / conversation data**: customer conversations are sensitive; retention and access policy is a **compliance open item** (RES-001) to resolve before launch — flagged, not yet answered.
- **Least privilege**: Google OAuth scopes limited to calendar; Clerk roles limited to a business's own data.
- **Transport**: HTTPS everywhere; HSTS on the dashboard.

---

## Open items feeding this design

- Compliance/data-privacy for stored conversations — **RES-001, unresolved**; may constrain retention and storage region.
- Final vertical — **Pending Validation**; affects KB structure and booking nuances but not the core architecture.
- Confirm founder language preference before locking the backend stack (see `TECH_STACK.md`).
