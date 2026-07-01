# MILESTONES.md

Progress tracked by **product capability**, not sprint number. The first MVP is the end-to-end AI receptionist loop below.

## Milestone 1 — First Working AI Receptionist

Customer → WhatsApp message → verified → stored → knowledge retrieved → Claude grounded response → reply sent.

- [x] Receive WhatsApp message — webhook `POST /webhooks/whatsapp`
- [x] Verify webhook — token handshake + HMAC signature
- [x] Store customer — get-or-create on inbound
- [x] Store conversation — get-or-create active thread
- [x] Store message — inbound persisted, deduped by `wa_message_id`
- [x] Index knowledge — KB ingestion with chunking
- [x] Generate embeddings — local bge-small via `EmbeddingProvider`
- [x] Semantic search — pgvector cosine similarity
- [x] Retrieve relevant knowledge — retrieval pipeline returns grounding context
- [x] Grounded response — orchestrator assembles context + injects knowledge + history and calls the LLM. **Verified live with Groq** (`llama-3.3-70b-versatile`); also runs via MockProvider; Claude available by config.
- [x] Send WhatsApp reply — `approve_and_send` sends a pending reply via the WhatsApp messaging service and marks it sent/failed (tenant-scoped, tested). Real outbound to a live number still needs the **WhatsApp access token**; an authenticated approve endpoint arrives with Clerk.

**Milestone 1 capabilities are all implemented.** The full loop works end to end: WhatsApp inbound → store → retrieve knowledge → generate grounded reply (Groq, live) → store pending → approve & send.

Remaining to run against real WhatsApp traffic (not new capabilities): the **WhatsApp access token** for live outbound, and an authenticated approval endpoint (with Clerk).

## Blocked on (stop conditions)
- **WhatsApp access token** → real outbound send to live numbers (send + approve_and_send built & tested with mocks).
- **Clerk** → authenticated approval endpoint on top of `approve_and_send`.
- LLM generation: **unblocked — Groq live** (`GROQ_API_KEY` + `LLM_PROVIDER=groq`).

## Milestone 2 — Clerk Authentication

- [x] Verify Clerk JWTs (RS256 via JWKS, `CLERK_JWKS_URL`) — real crypto, tested with self-signed keys
- [x] Resolve authenticated user → `business_id` (`get_current_principal` → `Principal`)
- [x] Protect dashboard/API routes (`/api/v1/*`) — 401 without a valid token
- [x] Authenticated approval endpoint on top of `approve_and_send` (`POST /api/v1/messages/{id}/approve`)
- [x] Tenant isolation enforced — cross-tenant access → 404 (tested)
- [x] `GET /api/v1/pending` — tenant-scoped list of pending replies

**Live use** needs Clerk app credentials in `.env` (`CLERK_JWKS_URL`) + a `User` row per Clerk user (provisioning via Clerk webhook is a later step).

## Milestone 3 — Next.js Dashboard UI

- [x] Next.js 15 (App Router) + TS + Tailwind v4 + shadcn-style UI + TanStack Query + RHF/Zod + Lucide
- [x] Clerk integration, production-ready, with dev **mock-auth fallback** (never in production; auth-misconfigured screen instead)
- [x] All API requests attach the Clerk session token; centralized typed API client (auth/retries/errors/loading)
- [x] App shell: sidebar, top nav, user menu, mobile nav, dark mode, loading skeletons, error boundaries
- [x] Pages: Dashboard, Inbox, Pending Replies (live), Knowledge Base, Customers, Analytics, Settings
- [x] Pending Replies live against real API (list + approve, optimistic update, auto-refresh)
- [x] Tests (Vitest + Testing Library), typecheck, eslint, build all pass; frontend CI job added

Backend untouched (AI, retrieval, Groq, embeddings, tenant isolation, WhatsApp all unchanged). Pages needing not-yet-built endpoints show polished placeholders.

## After Milestone 3 (deferred)
Backend endpoints for inbox/customers/KB-list/analytics + reply reject; Clerk user-provisioning webhook; billing; Google Calendar booking. WhatsApp production integration stays paused until a dedicated phone number is available.
