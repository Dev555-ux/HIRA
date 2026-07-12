# HIRA

HIRA is an AI receptionist that answers customer messages on WhatsApp for small businesses, grounded in each business's own knowledge base, with a human able to approve, edit, or override every reply.

It runs as a modular-monolith FastAPI backend and a Next.js dashboard. The backend is functionally complete against a single real test business (WhatsApp Cloud API, Groq LLM, Google Calendar, a lead pipeline, and a memory layer all work end-to-end); it has not yet been deployed anywhere or run with more than one tenant at a time. See [Current Status](#current-status) for exactly what that means in practice.

---

## Why HIRA Exists

Small businesses that take bookings — clinics, salons, gyms, consultants — get a steady stream of repetitive WhatsApp questions: "are you open today?", "how much does X cost?", "can I move my appointment?". Answering them takes a person's attention all day, and a slow or missed reply loses the customer to whoever replies first. Hiring a receptionist is expensive and doesn't scale with message volume; ignoring WhatsApp isn't an option when that's where the customers already are.

HIRA answers those messages automatically, using facts the business itself provided (hours, pricing, policies, FAQs), and hands off to a human whenever it's uncertain or asked to. The goal is not to remove the human from the loop — it's to remove the repetitive parts of their job.

---

## What HIRA Is Today

Everything below is implemented and either live-verified against real external services or covered by the automated test suite. Nothing in this section is aspirational — see [Vision](#vision) and [Roadmap](#roadmap) for what isn't built yet.

- **AI customer conversations on WhatsApp.** A message to a business's connected WhatsApp number is received via Meta's Cloud API (webhook, HMAC-verified), stored, and answered by an LLM whose reply is grounded in that business's knowledge base — never invented pricing, hours, or policy.
- **Knowledge base.** Business facts are chunked, embedded (a local, on-device embedding model — no external call per query), and retrieved by semantic similarity search (PostgreSQL + pgvector) for every incoming message. Entries can be created directly or imported from a website.
- **Human approval mode (Assisted Mode, default).** Every AI-drafted reply is held for a human to review in the dashboard: approve & send, edit before sending, reject, regenerate, or escalate to a human — before the customer sees anything.
- **Autonomous Mode.** A per-business toggle that lets the AI send replies and execute booking/CRM actions without waiting for approval, once a business has earned that trust.
- **Appointment scheduling and calendar integration.** OAuth-connected Google Calendar per business, with availability checks, booking, rescheduling, and cancellation — reachable both from the dashboard and as tools the AI can call mid-conversation (approval-gated in Assisted Mode).
- **Lead management / CRM.** A lead record per customer with a pipeline stage (new → contacted → qualified → proposal → negotiation → won/lost), an append-only activity timeline, and AI tools that can create a lead or advance its stage during a conversation.
- **Customer management.** A searchable customer directory with a per-customer timeline that merges message history and CRM activity.
- **Conversation memory.** A context builder assembles business, customer, lead, appointment, and knowledge-base context before every AI turn, backed by a persisted rolling summary so long conversations don't lose earlier context once they scroll past the raw history window.
- **Multi-tenant architecture.** Every business-owned table is scoped by `business_id`, enforced in application code (not database row-level security); a business signs up, provisions itself, and is routed to by its own WhatsApp phone number ID. Structurally multi-tenant; validated so far with one real business.
- **Provider abstraction.** The LLM, the embedding model, and the calendar backend are each behind a small interface with a swappable implementation (currently Groq for LLM generation, a local BGE model for embeddings, Google for calendar) — not a vendor SDK wired directly into business logic.
- **A dashboard**, built with Next.js and Clerk authentication, covering pending-reply review, inbox, knowledge base, customers, leads, calendar/appointments, settings, and onboarding.
- **A public marketing site** at the root URL for signed-out visitors, describing only what's listed above.

---

## Vision

HIRA's long-term direction, in three stages:

**AI Receptionist** *(what's being built now)*
↓
**AI Employees** — additional AI roles beyond receptionist (sales follow-up, support, others to be determined by validated need)
↓
**AI Business Operating System** — a platform where a small business "hires" AI employees across its functions

This is a direction, not a plan with dates. HIRA deliberately stays narrow — proving the receptionist product works for real businesses — before any of the later stages are built. Nothing beyond "AI Receptionist" exists in the codebase today.

---

## Core Principles

- **WhatsApp-first.** Customers are met where they already are, not on a new channel they have to adopt.
- **Human-in-the-loop by default.** Assisted Mode ships before Autonomous Mode for every capability; trust is earned incrementally, not assumed.
- **Modular monolith.** One deployable codebase, not microservices. A module earns its own service only when its own scaling profile demands it.
- **Provider abstraction.** External dependencies (LLM, embeddings, calendar) sit behind a small interface with a swappable implementation, so no vendor SDK leaks into business logic.
- **PostgreSQL-first.** One database of record; JSONB for flexible fields, pgvector for retrieval. New infrastructure (a queue, a separate vector store, a cache) is added only once a real, measured limit is hit.
- **Customer value over technical elegance.** Ship the smallest thing that proves the idea; a "more correct" design that delays validation is the wrong trade.
- **Scale only when necessary.** Load-bearing decisions (async migration, a durable task queue, database-level tenant isolation) are explicitly deferred until real usage data justifies them, not built ahead of evidence.

The full, current list — with the reasoning behind each — is in [`ARCHITECTURE.md`](ARCHITECTURE.md#architectural-principles).

---

## Architecture

```
Customer (WhatsApp) → Meta Cloud API → Webhook (HMAC-verified)
                                           ↓
                                  FastAPI backend (single process)
                                           ↓
                          Context Builder → Knowledge retrieval (pgvector)
                                           ↓
                                    LLM (Groq, swappable)
                                           ↓
                     Assisted Mode: held for approval   |   Autonomous Mode: sent directly
                                           ↓
                                  Meta Cloud API → Customer

Next.js dashboard  →  REST API (Clerk-authenticated, tenant-scoped)  →  same FastAPI backend
```

One PostgreSQL database (with the pgvector extension) is the single system of record for every table — businesses, conversations, messages, the knowledge base, leads, appointments, and calendar credentials. There is no message queue, no cache layer, and no separate vector database; background work (AI reply generation) runs in-process via FastAPI's `BackgroundTasks`, not a worker queue.

Full detail — folder-by-folder module responsibilities, the request lifecycle, the database schema and ER diagram, security posture, and every external service integration — is in [`ARCHITECTURE.md`](ARCHITECTURE.md). That file is the living source of truth for the system as built; this README summarizes it.

---

## Repository Structure

The codebase lives in two places; a handful of top-level folders are day-one scaffolding that were never populated as the project's real structure took shape inside `backend/` and `frontend/` instead.

| Path | Contents |
|---|---|
| [`backend/`](backend/) | The FastAPI application: webhooks, AI pipeline, services, REST API, database models, Alembic migrations, and the pytest suite. |
| [`frontend/`](frontend/) | The Next.js dashboard and public marketing site. |
| [`documentation/`](documentation/README.md) | Human-readable reference docs: API contracts, database schema, WhatsApp/embeddings/frontend notes, the production-readiness checklist. |
| [`roadmap/`](roadmap/README.md) | Feature/vertical sequencing notes. Currently one sprint plan (`SPRINT_1.md`); see [Roadmap](#roadmap) below for where forward planning actually lives now. |
| [`.claude/`](.claude/CLAUDE.md) | The project's operating manual and running project memory — engineering standards (`CLAUDE.md`), the append-only decision log (`DECISIONS.md`), session-by-session build history (`PROGRESS.md`), and the active backlog (`TODOS.md`). |
| [`learning/`](learning/README.md) | A handful of founder notes on concepts learned while building (git/CI, databases/ORM/migrations). |
| `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `MILESTONES.md` | Living docs describing the system as built, the path to production, and MVP milestone tracking, respectively. |
| `ai/`, `business/`, `database/`, `deployment/`, `infrastructure/`, `portfolio/`, `progress/`, `prompts/`, `testing/` | Placeholder scaffolding created at project start. Each contains only a `README.md` describing its intended future purpose — no code or content lives here today. |

---

## Tech Stack

**Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL + pgvector, `pydantic-settings`. LLM generation via the Groq API by default (an `LLMProvider` interface also has Claude and a mock implementation). Embeddings via a local `fastembed`/BAAI BGE model — no external call per query. Google Calendar via OAuth (`google-api-python-client`), with Fernet-encrypted credential storage. Clerk JWT verification for the dashboard API.

**Frontend**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS v4, hand-authored Radix-based UI primitives, TanStack Query for server state, React Hook Form + Zod for forms, Clerk for auth.

**Testing**: pytest (backend), Vitest + Testing Library (frontend), both wired into GitHub Actions CI.

**Infrastructure today**: none deployed. Local PostgreSQL runs in Docker (via Colima); the backend runs via `uvicorn --reload` on a developer machine, exposed to Meta's webhook through an ngrok tunnel. See [Current Status](#current-status).

---

## Current Status

**Backend** — functionally complete for the MVP feature set described in [What HIRA Is Today](#what-hira-is-today), verified live end-to-end against the real Meta WhatsApp Cloud API, Groq, and Google Calendar with one real test business. 511 backend tests, 510 passing as of this writing (one test — an appointment-limit check — fails intermittently and hasn't been root-caused yet). No production hardening: no deployment, no secrets manager, no monitoring/alerting, no automated backups, no rate limiting, and a background-task failure currently produces silence to the customer rather than an automatic escalation.

**Frontend** — dashboard is live against real data for pending replies, inbox, knowledge base, customers, leads, calendar, and appointments; settings and analytics are partially built (some fields/metrics are still placeholders pending backend support). The public marketing site is live at the root URL. 145 frontend tests passing.

**Maturity**: pre-production, single-tenant validation stage — proven to work, not yet proven to run unattended or with more than one real business. The concrete gap between here and a real pilot is sequenced in [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).

---

## Roadmap

Forward planning is split across three living documents rather than duplicated here:

- [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) — the near-term path: pre-pilot hardening, deployment, and production-readiness work, in priority order.
- [`ARCHITECTURE.md` § Future Roadmap](ARCHITECTURE.md#15-future-roadmap) — feature-level next steps (analytics, self-service WhatsApp connection, billing, event durability, a workflow engine) and their current status.
- [`roadmap/README.md`](roadmap/README.md) — the original feature/vertical sequencing notes from project start.

None of the above should be read as committed dates — see [`.claude/DECISIONS.md`](.claude/DECISIONS.md) for the standing rule that this architecture evolves from evidence (real usage, a real constraint, a real business-direction change), not from preference.

---

## Development

Requires Python 3.11+, Node.js, and a running PostgreSQL instance with the `pgvector` extension (the project runs one locally via Docker/Colima).

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in DATABASE_URL at minimum
alembic upgrade head
uvicorn app.main:app --reload
```
`GET /health` should return `{"status": "ok"}`. Run tests with `pytest`.

**Frontend**
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```
Without a Clerk publishable key set, the frontend falls back to a mock-auth dev user (disabled outside development). Run tests with `npm test`; typecheck with `npm run typecheck`.

Full environment variable references and integration setup (WhatsApp, Google Calendar, Clerk) are in [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`documentation/`](documentation/README.md).

---

## License

No license file is currently present in this repository. All rights reserved by the author; this is not licensed for reuse or redistribution.
