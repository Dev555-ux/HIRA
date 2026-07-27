# MVP Technology Stack

Status: **Accepted** (2026-06-29). See `DECISIONS.md` DEC-011.

> ✅ **Accepted 2026-06-29.** Founder confirmed: beginner programmer, accepts the two-language reality (Python backend + TypeScript frontend), backend-first development, and managed auth via Clerk. Optimization criteria locked to learning · simplicity · maintainability · production readiness.

Optimization targets: solo founder · learning · fast development · low cost · production readiness.

| Layer | Recommendation | Why |
|---|---|---|
| **Backend language/framework** | **Python + FastAPI** | AI/LLM ecosystem is Python-native (Anthropic SDK, embeddings, RAG tooling). FastAPI is async (ideal for webhooks), fast to write, auto-generates OpenAPI docs, production-grade. High learning value. |
| **AI / conversation engine** | **Anthropic Claude** — Sonnet 4.6 for reasoning/replies; Haiku 4.5 for cheap intent classification & routing | Latest, most capable models; tool-use support fits the booking/escalation actions. Two-tier (cheap classifier + capable responder) controls cost. |
| **Knowledge base / retrieval** | **PostgreSQL + `pgvector`** | Store FAQ embeddings in the same Postgres instance instead of a separate vector DB — fewer moving parts (CLAUDE.md §14). Sufficient for MVP knowledge-base sizes. |
| **Database** | **PostgreSQL (managed)** | Relational model fits businesses/conversations/appointments cleanly; reliable; `pgvector` doubles as the vector store. |
| **Frontend** | **Next.js (React) + TypeScript + Tailwind CSS** | Most learnable/employable frontend stack, excellent DX, deploys to Vercel in minutes, handles the dashboard/inbox/calendar UI well. |
| **Auth (dashboard)** | **Clerk** (or Supabase Auth if using Supabase) | Don't hand-roll auth for a production system as a solo founder. Managed auth is secure, fast, free at MVP scale. |
| **Backend + DB hosting** | **Railway** (app + managed Postgres) | Simplest path for a solo founder: managed Postgres, easy deploys, low cost, good logs. Render is an equivalent alternative. |
| **Frontend hosting** | **Vercel** | First-class Next.js host, generous free tier. |
| **Calendar** | **HIRA Calendar** (internal scheduler, no setup required), with **optional Google Calendar Sync (OAuth 2.0)** | Scheduling (book/reschedule/cancel) works out of the box via HIRA's own `Appointment` table (Sprint 78/79) — Google Calendar is an additional sync layer a business can connect later, not a dependency. |
| **Background jobs** | Start with FastAPI background tasks / a lightweight scheduler; add a queue (e.g., Redis + worker) only when reminders/volume require it | Avoid premature infra (CLAUDE.md §14). |

## Alternatives weighed (not chosen)

- **Node.js / NestJS backend** — viable and unifies language with the frontend (one language: TypeScript). Rejected as default only because Python's AI ecosystem is stronger and this is an AI-first product. **If the founder prefers a single TypeScript codebase, this is the recommended fallback.**
- **Supabase (Postgres + Auth + Storage in one)** — fewer vendors, faster auth. Strong alternative to Railway+Clerk; trade-off is more lock-in. Acceptable if the founder prefers an all-in-one.
- **Separate vector DB (Pinecone/Weaviate)** — rejected for MVP; `pgvector` is enough and avoids another service.
- **Dedicated job queue from day one** — deferred until reminders/scale justify it.

## Cost posture (MVP)

Near-zero to low: free/low tiers on Vercel, Railway, Clerk; Claude API billed per token; WhatsApp service messages largely free (see `WHATSAPP_INTEGRATION.md`). Main variable cost is LLM token usage — controlled via the Haiku/Sonnet two-tier design.
