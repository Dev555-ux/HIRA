# MEMORY.md

Permanent, cross-session memory for the HIRA project. Only long-term information lives here — facts, principles, and lessons that should still be true and relevant many sessions from now. Temporary tasks, in-progress work, and short-lived notes belong in `TODOS.md` or `PROGRESS.md`, never here.

Update this file whenever something important and lasting is learned. If new information conflicts with an existing entry, update that entry in place — do not duplicate it. Never invent information; mark anything not yet confirmed as **Pending Validation**.

## Project Identity

- **Name**: HIRA
- **What it is today**: An AI Receptionist platform for WhatsApp-first businesses. Automatically responds to customer inquiries, answers FAQs from a business's knowledge base, books/reschedules appointments via Google Calendar, runs a CRM/lead pipeline, retains conversation memory across turns, and escalates uncertain conversations to a human. All four MVP milestones are complete and live-verified against real external services (see `ARCHITECTURE.md`, `MILESTONES.md`).
- **Founder/operating model**: Solo founder, building with Claude acting as technical cofounder.

## Founder Profile

- **Background**: B.Com (Hons.) student, started as a **beginner-level programmer**, learning software engineering while building HIRA.
- **Goals**: (1) build a real SaaS business; (2) learn professional software engineering deeply; (3) build a strong GitHub portfolio; (4) offer AI automation services on Fiverr; (5) **understand every technology rather than copy code**.
- **Resources**: has time to learn; **no large budget; no development team**.
- **How Claude should optimize every technical decision**: for **learning, simplicity, maintainability, and production readiness**. When multiple options exist, recommend the one that **maximizes long-term learning while still allowing a fast ship**.
- **Teaching implication**: explain the *why* and the fundamentals when depth is asked for; don't hand over copy-paste code without ensuring understanding. Concepts learned live in `learning/` (currently a handful of notes on git/CI and databases/ORM/migrations — add to it opportunistically, not on every task).

## Vision

- Long-term: an **AI Business Operating System** — a platform where businesses "hire" AI employees across different business functions.
- Near-term: deliberately narrow. The goal is to become the best AI Receptionist before expanding to any other function or role. Nothing beyond the receptionist product is built; treat "AI Employees" / "AI Business OS" as direction, not a scheduled deliverable.

## Current Architecture (summary — `ARCHITECTURE.md` is authoritative)

- **Pattern**: modular monolith. One FastAPI backend process, one Next.js frontend, one PostgreSQL database (+ pgvector) as the sole system of record. No microservices, no message queue, no separate vector store or cache — background work (AI reply generation) runs in-process via FastAPI `BackgroundTasks`.
- **Provider abstraction is the house pattern**: `LLMProvider`, `CalendarProvider`, and `EmbeddingProvider` are each a small ABC with a swappable implementation — no vendor SDK is ever imported directly into business logic.
- **Multi-tenancy**: every business-owned table carries `business_id`, enforced in application code (`tenant_query`/`get_scoped`) — there is no database-level row-level security.
- Full detail, module-by-module, lives in `ARCHITECTURE.md`; do not restate schema/API/module specifics here — link to it instead of duplicating it.

## Completed Major Systems

(All implemented and tested; see `ARCHITECTURE.md` for exact scope/limitations of each.)

- WhatsApp Cloud API integration (inbound webhook, HMAC verification, outbound send, autonomous/assisted send paths).
- Clerk-authenticated dashboard API, tenant-scoped.
- Knowledge base with pgvector retrieval + website import.
- AI conversation orchestration: retrieval-grounded replies, tool-calling for calendar and CRM actions, Assisted/Autonomous mode.
- Conversation memory (context builder + persisted rolling summary).
- Google Calendar integration (OAuth, booking/reschedule/cancel, availability, working hours).
- CRM: leads, pipeline stages, lead events timeline, manual customer/lead creation, AI-driven lead actions.
- Next.js dashboard (dashboard, inbox, pending-reply approvals, knowledge base, customers, leads, calendar, appointments; settings/analytics partially built) and a public marketing site.
- Self-service business signup/provisioning (Clerk sign-up → tenant).

**Not built**: billing, self-serve WhatsApp number connection (still manual via a script), automatic escalation on AI-generation failure, response/output guardrails, any production deployment.

## Current Stack

- **Backend**: Python + FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL + pgvector.
- **AI**: Groq (LLM, current default in use) behind `LLMProvider` — Claude and a mock provider also implemented and swappable by config. Embeddings are local (`fastembed`, BAAI BGE-small) — not a hosted embeddings API.
- **Frontend**: Next.js 15 (App Router), TypeScript, Tailwind CSS v4, TanStack Query, React Hook Form + Zod, Clerk.
- **Calendar**: Google Calendar API via OAuth 2.0.
- **Auth**: Clerk (dashboard), Meta HMAC signature (webhook).

## Current Deployment

**Nothing is deployed.** Backend and frontend both run locally (`uvicorn --reload`, `next dev`); Postgres runs in a local Docker/Colima container; the WhatsApp webhook is exposed via an ngrok tunnel. No hosting provider, secrets manager, monitoring, or automated backups exist yet. The original plan (Railway for backend/DB, Vercel for frontend — `documentation/TECH_STACK.md`) has not been executed; treat it as a proposal, not a fact, until `IMPLEMENTATION_PLAN.md`'s `DEPLOY-1` actually closes.

## Product Principles

- The MVP stayed as small as possible; new capability shipped ahead of vertical validation only when it was vertical-agnostic (per `ARCHITECTURE.md` → Architectural Principles).
- **Assisted Mode** (human reviews/approves AI actions) ships before **Autonomous Mode** (AI acts independently) for every capability — trust is earned incrementally, not assumed.
- Escalation to a human is a core feature, not a fallback — uncertainty should be handled by handing off, not guessing. (Manual escalation exists today; automatic escalation on generation failure does not yet.)

## Business Principles

- Pick one primary vertical after validation, rather than building for all customer segments at once. Still **Pending Validation** — no vertical has been chosen (`DEC-006`).
- Vertical selection criteria: market demand, willingness to pay, ease of sales, and product-market fit.
- Pricing model: **Pending Validation**.

## Target Customers

Six verticals still under evaluation for the first production version: Dental Clinics, Beauty Salons, Immigration & Study Abroad Consultants, Gyms & Fitness Centers, Real Estate Agencies & Property Consultants, Cafés & Restaurants. Which one becomes the primary target: **Pending Validation**.

## Customer Research

No findings recorded yet. **Pending Validation** for all six verticals (demand signals, willingness to pay, sales cycle, competitive landscape) — unchanged since project start.

## Important Design Decisions (see `.claude/DECISIONS.md` for full reasoning)

- Modular monolith over microservices; Postgres for everything (including vectors via pgvector) until a measured limit forces otherwise.
- Every external dependency (LLM, embeddings, calendar) sits behind a small interface, never a vendor SDK in business logic.
- A production-readiness audit (`IMPLEMENTATION_PLAN.md`) sequenced remediation into Milestones 0–3 (pre-pilot hardening → deployment → production hardening → scale readiness). Check that document, not memory, for which specific findings are currently closed.
- Architecture changes only on evidence — real usage, a real constraint, or an intentional business-direction change — not preference (`ARCHITECTURE.md` → Architectural Principles #9).

## Documentation Hierarchy

- **Authoritative / living** (reflect current reality, updated as it changes): `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `README.md`, `roadmap/`.
- **Append-only / historical** (never rewritten, only added to): `.claude/DECISIONS.md`, `.claude/PROGRESS.md`, `MILESTONES.md`, closed sprint plans.
- **This file and `PROJECT_CONTEXT.md`**: current-state summaries for session continuity — kept accurate, but not the source of truth for implementation detail. When in doubt, defer to `ARCHITECTURE.md` over this file.
- **Known doc debt**: `.claude/TODOS.md`'s "Current Sprint" section (top of file) still describes pre-build validation tasks (vertical/stack/architecture decisions) as "To Do" even though most were decided and built long ago — don't treat that section as current without cross-checking `DECISIONS.md` first. Flagged, not yet corrected as of this writing.

## How Sessions Run (Execution Mode — DEC-017, supersedes DEC-016)

Default is **Autonomous Execution Mode** (CLAUDE.md §18; DEC-017 + DEC-018): brief overview → implement immediately → explain only important architectural decisions → end-of-task summary (built / why / files / key concepts / bugs). Skip quizzes and long lessons unless asked; founder asks "Why?" for depth. Still update PROGRESS/TODOS/docs per task. Founder can switch back to Teacher Mode (DEC-016 style) any time.

**Autonomy (DEC-018):** no approval needed for routine engineering (files, dev deps, tests/linters, migrations, commits, refactors, bug fixes, non-behavioral architecture, docs). **Stop and ask only for:** business-decision change, product-feature change, required paid service, destructive/data-loss ops, credentials/API-keys/billing, legal/security/privacy decisions, or multiple valid architectures with significant trade-offs. State what you're doing and continue otherwise.

## Coding Standards

See [CLAUDE.md](CLAUDE.md) Section 4 for the full standard. Key points worth remembering long-term:
- No comments explaining *what* code does — only non-obvious *why*.
- No speculative abstractions or premature config flags.
- No error handling for cases that cannot occur; validate only at real trust boundaries.

## Current Priorities

Per `IMPLEMENTATION_PLAN.md` (the authoritative sequencing): pre-pilot hardening and closing the gap to a real deployment (Milestones 0–1) — cheap, high-severity code fixes, then getting off the developer laptop onto permanent hosting with logging/backups/monitoring. Vertical selection (`DEC-006`) remains open in parallel but is a go-to-market track, not a blocker on this engineering sequencing. Check `IMPLEMENTATION_PLAN.md` directly for exactly which milestone items are currently closed — don't assume from memory.

## Documentation Standards

- Every `.claude/` file has exactly one job; content is not duplicated across files (see [CLAUDE.md](CLAUDE.md) Section 5).
- Each repository folder carries its own `README.md` explaining purpose. Several top-level folders (`ai/`, `business/`, `database/`, `deployment/`, `infrastructure/`, `portfolio/`, `progress/`, `prompts/`, `testing/`) are still day-one scaffolding — a `README.md` only, no real content. The actual codebase lives in `backend/` and `frontend/`.
- Documentation is updated in the same session as the change that invalidates it, not deferred. A stale living doc is treated as a bug, not background noise.

## Lessons Learned

Not yet formally consolidated here. See `learning/` for concrete technical notes captured along the way (git/CI, databases/ORM/migrations) and `.claude/PROGRESS.md` for session-by-session detail on bugs found and fixed. Add a durable lesson here only once it's proven to generalize beyond a single sprint.

## Things to Avoid

- Inventing project facts (founder background, budget, timeline, tech choices, feature status) — these must be confirmed against the code or `DECISIONS.md`, not assumed.
- Building features or infrastructure ahead of validated need.
- Letting documentation drift from actual project state — verify against `backend/`/`frontend/` before restating a capability as built or not built.
- Bundling unrelated changes or scope into a single piece of work.

## Future Ideas (not decisions)

These are speculative and unconfirmed — listed here only so they aren't lost, not because they've been decided:

- Expanding beyond AI Receptionist into other "AI employee" roles once the receptionist product is validated (per the AI Business Operating System vision).
- Expanding to additional verticals beyond the first validated one, using the same core product.
- A durable `contact_memories` table for facts that outlive a single conversation (noted as a future consideration in `ARCHITECTURE.md` §15, not committed).
