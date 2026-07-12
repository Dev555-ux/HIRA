# PROJECT_CONTEXT.md

Current state of the HIRA project: what it is, who it's for, what's built, and what constraints apply. This file describes the present, not history (see `.claude/PROGRESS.md` for session-by-session history and `.claude/DECISIONS.md` for the decision record) and not future plans (see `IMPLEMENTATION_PLAN.md` and `roadmap/` for that). Update this file whenever goals, scope, implementation status, or constraints change — keep it current, not historical.

**Authoritative documents for anything this file summarizes**: `ARCHITECTURE.md` (system as built), `IMPLEMENTATION_PLAN.md` (path to production), `.claude/DECISIONS.md` (append-only decision log), `roadmap/` (feature sequencing), `README.md` (external-facing summary). If this file ever conflicts with one of those, that document wins — file an update here.

## What HIRA Is

HIRA is an AI employee businesses hire for WhatsApp-first customer conversations — not a chatbot they install and configure. It automatically responds to customer inquiries, answers FAQs grounded in a business's own knowledge base, books and reschedules appointments via Google Calendar, manages a lead pipeline, escalates uncertain conversations to a human, and aims to ensure businesses never miss a lead. See `business/BRAND_BIBLE.md` (DEC-036) for the full positioning, voice, and vocabulary this file's language should match.

Long-term vision: an **AI Business Operating System** where businesses can "hire" AI employees across functions (the Receptionist, sales follow-up, support, and others yet to be validated). The current focus remains narrow and deliberate — becoming the best AI employee first, in the Receptionist role. Nothing beyond the Receptionist exists in the codebase today; the wider vision is direction, not a committed build plan.

## Current Implementation Status

**All four MVP milestones are complete** (see `MILESTONES.md`, `ARCHITECTURE.md` §14): WhatsApp Cloud API messaging, Clerk dashboard authentication, the Next.js dashboard, and the autonomous send loop are built and were live-verified end-to-end against Meta's real Cloud API. Well beyond MVP scope, the following are also implemented and tested (see `ARCHITECTURE.md` for the full description of each):

- Knowledge base with pgvector semantic retrieval and website import.
- Assisted Mode (default, human approves every draft) and Autonomous Mode (per-business toggle).
- Google Calendar integration — OAuth connect, booking/reschedule/cancel, working hours, availability checks, AI tool-calling.
- CRM: leads with pipeline stages, an append-only activity timeline, manual customer and manual lead creation, and AI tool calls that can create/advance a lead mid-conversation.
- Conversation memory: a context builder plus a persisted rolling summary so long conversations retain context past the raw history window.
- Multi-tenant architecture: every business-owned table scoped by `business_id` in application code (no database-level row-level security).
- A Next.js dashboard (dashboard, inbox, pending-reply review, knowledge base, customers, leads, calendar, appointments; settings and analytics are partially built) and a public marketing site.

**Test status** (verified by running the suites, not assumed): 511 backend tests (pytest), 145 frontend tests (Vitest), `tsc --noEmit` clean. One backend test is intermittently flaky (an appointment-ordering test) and not yet root-caused — this is the only known test-suite issue.

**A backend production-readiness audit was completed** (see `IMPLEMENTATION_PLAN.md`, `documentation/PRODUCTION_CHECKLIST.md`) and produced a sequenced remediation plan (Milestones 0–3). As of this writing, remediation work against that plan is in progress but not complete — check `IMPLEMENTATION_PLAN.md` and `.claude/TODOS.md`'s Infrastructure/Technical Debt sections for exactly which findings are closed before assuming any specific one is fixed.

**Project maturity**: pre-production, single-tenant validation stage. Proven to work end-to-end against one real test business; not yet deployed anywhere, not yet run with more than one tenant concurrently, and without production operational tooling (monitoring, automated backups, a secrets manager, rate limiting). Everything currently runs on a developer's laptop (`uvicorn --reload`) with a local Docker/Colima Postgres and an ngrok tunnel for the WhatsApp webhook. This is a known, tracked gap (`IMPLEMENTATION_PLAN.md` Milestone 1), not an oversight.

## Target Customers

Six verticals are still under evaluation to select **one** primary target for the first production version, based on market demand, willingness to pay, ease of sales, and product-market fit:
- Dental Clinics
- Beauty Salons
- Immigration & Study Abroad Consultants
- Gyms & Fitness Centers
- Real Estate Agencies & Property Consultants
- Cafés & Restaurants

Which vertical will be chosen: **Pending Validation** (DEC-006 — unchanged; no customer discovery has been logged in `business/` yet). The product itself has been built vertical-agnostic on purpose, so this remains a go-to-market decision, not a blocker on engineering work.

## Team / Founder

Solo founder, building with Claude acting as technical cofounder across 41 shipped sprints to date.

- **Founder**: B.Com (Hons.) student, started as a beginner-level programmer, learning software engineering while building HIRA.
- **Goals**: build a real SaaS business, learn professional software engineering deeply, build a GitHub portfolio, offer AI automation services on Fiverr, and understand every technology rather than copy code.
- **Optimization criteria for all technical decisions**: learning, simplicity, maintainability, production readiness — favor the option that maximizes long-term learning while still shipping quickly.

See `.claude/MEMORY.md` → Founder Profile for the durable version.

## Constraints

- Budget: **Low / bootstrapped** — no large budget; favor free and low-cost tiers. Still true — no hosting has been paid for or provisioned.
- Team: **Solo** — no development team.
- Timeline / target launch date: **Unknown** — no committed date.
- Legal/compliance requirements (WhatsApp Business Platform policy, data privacy per target market): **Still unresearched** — open as `RES-001` in `.claude/TODOS.md`.
- WhatsApp Business API access: **In place** — a permanent Meta System User access token is configured and in live use against Meta's Cloud API.
- Google Cloud / Calendar API access: **In place** — OAuth is configured and Google Calendar integration runs against the real Google API in normal use.
- Hosting/deployment accounts: **Not set up** — no hosting provider has been chosen or provisioned; this is the next concrete blocker before a real pilot (`IMPLEMENTATION_PLAN.md` Milestone 1).

## Technology Decisions Made So Far

Stack, architecture, and provider choices are decided and built — see `.claude/DECISIONS.md` for the full reasoning and history (including superseded choices, e.g. the LLM provider chain that ended at Groq). Current state, in brief:

- **Backend**: Python + FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL + pgvector.
- **AI**: Groq is the LLM provider in current use, behind an `LLMProvider` interface (Claude and a mock implementation also exist and are swappable by config). Embeddings run locally (`fastembed`, BAAI BGE) — no hosted embedding API.
- **Frontend**: Next.js 15 (App Router), TypeScript, Tailwind CSS v4, TanStack Query, Clerk for auth.
- **Calendar**: Google Calendar API via OAuth 2.0, behind a `CalendarProvider` interface.
- **Hosting**: not yet decided or provisioned — the original plan (Railway + Vercel, see `documentation/TECH_STACK.md`) has not been executed; everything still runs locally. Treat any hosting choice as an open decision, not a completed one, until `IMPLEMENTATION_PLAN.md`'s `DEPLOY-1` is closed.

## Open Questions

- Which of the six verticals will be the primary target? (unchanged, `DEC-006`)
- Pricing model? (unchanged, `RES-002`)
- Hosting/infrastructure provider for production deployment? (`IMPLEMENTATION_PLAN.md` `DEPLOY-1`)
- Legal/compliance research for stored customer conversations? (`RES-001`)

The WhatsApp integration path and the core backend/frontend/AI stack are **no longer open questions** — both were decided and built (see Technology Decisions above); do not re-litigate them without a real constraint or usage signal (`ARCHITECTURE.md` → Architectural Principles #9).

## How to Keep This File Accurate

- When a vertical is chosen, update "Target Customers" and close the open question.
- When a hosting/deployment decision is made and executed, update "Constraints" and "Technology Decisions Made So Far," and log it in `.claude/DECISIONS.md`.
- When implementation status changes materially (a new major system ships, a milestone in `IMPLEMENTATION_PLAN.md` closes), update "Current Implementation Status" in the same session as the change.
- Do not let this file silently drift from reality — if a fact here is found to be stale or wrong, correct it immediately rather than leaving it. A stale `PROJECT_CONTEXT.md` actively misleads future sessions; treat it as a bug.
