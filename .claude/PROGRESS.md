# PROGRESS.md

Execution journal for HIRA. This is an append-only record of what has actually happened. Update it after every meaningful work session.

**Rules:**
- Never overwrite history — append new sessions.
- Keep progress factual; never inflate completion percentages.
- Percentages are rough estimates of work done against the *currently known* scope, not against the full long-term vision.

---

## Project Status

- **Current Stage**: Foundation / Pre-MVP (concept stage — no application code yet)
- **Current Milestone**: M1 — Foundation & Project Setup
- **Current Sprint**: Sprint 0 — pre-MVP preparation (customer validation, vertical selection, architecture, dev environment). See `TODOS.md`.
- **Overall Progress**: ~5% of the path to a shipped MVP. Project scaffolding and operating system are in place; no validation, architecture, or code work has begun.

---

## Session History

### Session 1 — 2026-06-29

- **Objectives**: Establish the `.claude/` project memory system, build the professional repository structure, and create foundational documentation before any code.
- **Work completed**:
  - Created the `.claude/` directory and six memory files.
  - Authored `CLAUDE.md` — 17-section operating manual (role, philosophy, standards, workflow, definition of done, review checklist).
  - Built 14 top-level folders, each with a `README.md` (documentation, backend, frontend, infrastructure, ai, prompts, database, testing, deployment, roadmap, business, learning, progress, portfolio).
  - Wrote the root `README.md` (overview, vision, MVP, goals, structure, tech philosophy, roadmap summary, contribution guidelines, dev workflow).
  - Populated `PROJECT_CONTEXT.md`, `MEMORY.md`, `DECISIONS.md` (DEC-001–009), and `TODOS.md`.
- **Decisions made**: Logged DEC-001 through DEC-009 in `DECISIONS.md` (vision, AI Receptionist first product, MVP-first, validation-before-scaling, WhatsApp-first, six-vertical research, Git+GitHub, `.claude/` memory, documentation-first).
- **Files changed**: `.claude/CLAUDE.md`, `.claude/PROJECT_CONTEXT.md`, `.claude/MEMORY.md`, `.claude/DECISIONS.md`, `.claude/TODOS.md`, `.claude/PROGRESS.md`; root `README.md`; 14 folder `README.md` files.
- **Lessons learned**: None of engineering substance yet. Process note: project facts (founder background, budget, timeline, stack) were deliberately left as "Unknown / Pending Validation" rather than invented.
- **Next actions**: Capture founder/project constraints (TASK-001) and initialize Git (TASK-002); begin customer discovery prep (TASK-005, TASK-006).

---

### Session 2 — 2026-06-29

- **Objectives**: Shift to engineering planning. Recommend WhatsApp integration + tech stack, design MVP architecture/database/API/frontend, produce Sprint 1.
- **Work completed**:
  - Researched current (June 2026) WhatsApp API landscape (Meta Cloud API, Twilio, 360dialog) and grounded pricing/availability claims with sources.
  - Authored `documentation/WHATSAPP_INTEGRATION.md`, `TECH_STACK.md`, `ARCHITECTURE.md`, `DATABASE.md`, `API.md`, `FRONTEND.md`.
  - Authored `roadmap/SPRINT_1.md` (15 tasks, each ≤2–3h, with testing + docs checklists).
  - Logged DEC-010–015 as **Proposed**.
- **Decisions made**: All **Proposed**, pending approval — WhatsApp via Meta Cloud API (DEC-010); stack = Python/FastAPI + Claude + Postgres/pgvector + Next.js + Clerk + Railway/Vercel (DEC-011); architecture/database/API/frontend (DEC-012–015).
- **Files changed**: 6 new `documentation/*.md`, `roadmap/SPRINT_1.md`, `.claude/DECISIONS.md`, `.claude/PROGRESS.md`.
- **Lessons learned**: Key insight — for an inbound AI receptionist, most WhatsApp traffic is free service-window replies, so the integration choice is driven by setup/DX/control, not per-message price. Per CLAUDE.md §11, re-verified pricing rather than trusting memory (Meta moved to per-message pricing July 2025).
- **Next actions**: Founder to (1) confirm technical background/language preference (gates DEC-011), (2) approve or amend DEC-010–015, (3) decide whether to start Sprint 1's vertical-agnostic core ahead of final vertical selection. Still open: Git init (TASK-002), vertical selection (TASK-004), compliance research (RES-001).

---

### Session 3 — 2026-06-29

- **Objectives**: Capture founder profile; finalize the engineering plan; establish the working method.
- **Work completed**: Recorded founder profile (beginner, B.Com student, learning-first goals) in `MEMORY.md` and `PROJECT_CONTEXT.md`. Confirmed and **Accepted** DEC-010–015 (stack/architecture). Added DEC-016 and CLAUDE.md §18 — the mandatory three-stage feature workflow (Explain → Build → Review). Flipped all `documentation/` design docs and Sprint 1 to Accepted/Ready.
- **Decisions made**: DEC-010–015 → Accepted; DEC-016 (three-stage workflow) Accepted.
- **Files changed**: `.claude/CLAUDE.md`, `.claude/DECISIONS.md`, `.claude/MEMORY.md`, `.claude/PROJECT_CONTEXT.md`, `.claude/PROGRESS.md`; `documentation/*` headers; `roadmap/SPRINT_1.md`.
- **Lessons learned (process)**: The stack survived the beginner lens — main cost is two languages, mitigated by backend-first sequencing, not by changing tools.
- **Next actions**: Begin Sprint 1 with **S1-01 (repo init & scaffolding)** using the three-stage workflow — starting with Stage 1 (Explain). Still open: vertical selection (TASK-004, deferred by choice), compliance research (RES-001).

---

### Session 4 — 2026-06-29

- **Objectives**: Begin Sprint 1. Complete S1-01 (repo init & backend skeleton) via the three-stage workflow.
- **Work completed**:
  - Added Task Closeout section to CLAUDE.md §18 (What I learned / Knowledge check / Eng tip / HIRA connection).
  - Verified toolchain: Git ✓, Python 3.14 ✓, **Node/npm not installed** → frontend scaffold split into S1-01b (deferred), backend-first.
  - Built backend skeleton: `.gitignore` (first), `backend/pyproject.toml`, `app/main.py` with `/health`. Created venv, installed fastapi+uvicorn, ran server, verified `GET /health` → 200 and `/docs` → 200.
  - `git init` + 3 Conventional-Commits commits.
  - Created/reconciled GitHub remote: an existing **public placeholder** `Dev555-ux/HIRA` was found; with founder consent, set it **private** and force-pushed our history to replace 3 trivial placeholder commits. Remote now in sync.
- **Decisions made**: Repo kept **private** (founder choice). Frontend scaffold deferred (S1-01b) pending Node install.
- **Files changed**: `.gitignore`, `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`; `.claude/CLAUDE.md`, `.claude/TODOS.md`, `.claude/PROGRESS.md`; `roadmap/SPRINT_1.md`.
- **Lessons learned (process)**: Always verify the toolchain before scoping; a missing dependency (Node) legitimately reshaped the task. Found a pre-existing public repo — surfaced it and got consent before any destructive/visibility change rather than force-pushing blindly.
- **Next actions**: S1-02 (CI pipeline) — or install Node and do S1-01b first if the founder prefers. TASK-002 closed.

---

### Session 5 — 2026-06-29

- **Objectives**: S1-02 — CI pipeline (three-stage workflow).
- **Work completed**: Added dev deps (pytest, ruff, httpx) + ruff/pytest config to `pyproject.toml`; wrote first behaviour test for `/health` via FastAPI TestClient; created `.github/workflows/ci.yml` (lint + format-check + tests on push/PR to main, Python 3.14). Ran all checks locally (pass), pushed, confirmed CI green on GitHub, and verified the failure path locally (ruff rejects unused import).
- **Decisions made**: Real behaviour test in CI (not lint-only); CI Python pinned to 3.14 to match local; verified failure path without committing broken code.
- **Files changed**: `.github/workflows/ci.yml`, `backend/tests/__init__.py`, `backend/tests/test_health.py`, `backend/pyproject.toml`, `roadmap/SPRINT_1.md`, `.claude/PROGRESS.md`, `learning/02-ci-and-testing.md`.
- **Lessons learned (process)**: A green CI check is only meaningful if it tests real behaviour. Verify the *failing* path too, but keep `main` clean by proving failures locally.
- **Next actions**: S1-03 — database schema & migrations (needs a Postgres decision: local Docker vs. managed dev DB).

---

### Session 6 — 2026-06-29

- **Objectives**: S1-03 — database schema & migrations (three-stage workflow).
- **Work completed**: Chose Docker for dev DB (founder). Installed Colima + docker CLI; ran Postgres 16 + pgvector 0.8.3 container. Added SQLAlchemy 2.0 models for all 9 tables, pydantic-settings config (`DATABASE_URL` from `.env`), engine/session. Set up Alembic, autogenerated + hand-corrected the initial migration (added `import pgvector`, `CREATE EXTENSION` for fresh-DB reproducibility). Applied migration; verified all tables, indexes, `vector(1536)` column, and up/down round-trip. Fixed two bugs (pgvector import; setuptools flat-layout — the latter caught by CI on fresh install). CI green.
- **Decisions made**: Dev DB via Docker/Colima; status fields as strings (not enums) for MVP flexibility; migration enables pgvector itself.
- **Files changed**: `backend/app/models.py`, `backend/app/core/`, `backend/app/db/`, `backend/alembic/` + migration, `backend/pyproject.toml`, `backend/.env.example`, `.gitignore`, `roadmap/SPRINT_1.md`, `.claude/PROGRESS.md`, `learning/03-databases-orm-migrations.md`.
- **Lessons learned (process)**: "Works on my machine" is real — the setuptools bug passed locally (cached build) and only failed on CI's fresh install. CI is the safety net that caught it. Always make migrations self-sufficient (enable their own extensions).
- **Next actions**: S1-04 — tenant scoping & config helper (build the `business_id`-scoping primitive + a unit test proving cross-tenant access is blocked).

---

### Session 7 — 2026-06-29

- **Objectives**: Switch to Execution Mode (DEC-017); complete S1-04 (tenant scoping & config).
- **Work completed**: Recorded Execution Mode as default workflow (CLAUDE.md §18, DEC-017 supersedes DEC-016, MEMORY updated). Built `app/db/tenant.py` (`tenant_query`/`get_scoped`, rejects unscoped models). Added Postgres-backed pytest fixture (`conftest.py`) + 3 multi-tenant isolation tests. Added a pgvector Postgres service to CI so DB tests run on every push. CI green (4 tests).
- **Decisions made**: DEC-017 Execution Mode; explicit tenant-scoping helpers over implicit query rewriting.
- **Files changed**: `.claude/CLAUDE.md`, `.claude/DECISIONS.md`, `.claude/MEMORY.md`, `backend/app/db/tenant.py`, `backend/tests/conftest.py`, `backend/tests/test_tenant_scoping.py`, `.github/workflows/ci.yml`, `roadmap/SPRINT_1.md`, `.claude/PROGRESS.md`.
- **Lessons learned (process)**: SQLite can't stand in for Postgres here (pgvector/JSONB) — DB tests need a real Postgres, now provided in CI.
- **Next actions**: S1-05 — Clerk auth on the API (validate Clerk JWT, resolve business_id on dashboard routes).

---

### Session 8 — 2026-06-29

- **Objectives**: Adopt Autonomous Execution Mode (DEC-018); complete S1-06 (WhatsApp webhook).
- **Work completed**: Recorded DEC-018 autonomy rules. Built WhatsApp webhook (`app/webhooks/whatsapp.py`): GET token handshake, POST HMAC signature verification, dedupe by `wa_message_id`, get-or-create customer/conversation, persist inbound message, fast 200. Wired router into `main.py`; added WhatsApp config vars. 5 webhook tests; CI green (14 tests total).
- **Decisions made**: DEC-018 (autonomous execution); webhook persists synchronously and acknowledges fast, defers AI dispatch.
- **Files changed**: `.claude/CLAUDE.md`/`DECISIONS.md`/`MEMORY.md`, `backend/app/webhooks/whatsapp.py`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/tests/test_whatsapp_webhook.py`, `backend/.env.example`, `.github/workflows/ci.yml`, `roadmap/SPRINT_1.md`, `.claude/PROGRESS.md`.
- **Lessons learned (process)**: Module-level `Settings()` means any import path that reaches config requires its env vars present — CI needed `DATABASE_URL`, not just `TEST_DATABASE_URL`.
- **Next actions**: S1-05 (Clerk auth) is blocked on Clerk credentials (founder). Unblocked alternatives: S1-08 (AI orchestrator + intent classification — needs Anthropic API key, also a credential) or S1-09/S1-10. **Most AI/integration tasks now need a credential (stop-list #5).** Recommend founder provides Anthropic + Clerk keys to unblock S1-05/S1-08.

---

### Session 9 — 2026-06-29

- **Objectives**: Prioritize the end-to-end AI receptionist loop (DEC-019); build what doesn't need the Anthropic key.
- **Work completed**: Logged DEC-019 (AI-core-first, pause Clerk). Built S1-07 outbound messaging service (`send_text`, retry policy, injectable client) + 3 tests; CI green (12 tests total).
- **Decisions made**: DEC-019.
- **Open decision (BLOCKING S1-09)**: embeddings provider for KB semantic search — Anthropic doesn't do embeddings. Options: local open-source (recommended, free, no extra key), Voyage AI, or OpenAI. **Founder dismissed the question — awaiting their choice before KB work.**
- **Files changed**: `.claude/DECISIONS.md`, `backend/app/services/messaging.py`, `backend/app/core/config.py`, `backend/pyproject.toml`, `backend/tests/test_messaging.py`, `roadmap/SPRINT_1.md`, `.claude/PROGRESS.md`.
- **Next actions**: Awaiting (a) Anthropic API key → unblocks S1-08 generation; (b) embeddings-provider decision → unblocks S1-09 KB retrieval. Then wire S1-08 + S1-09 into the webhook for the full loop.

---

### Session 10 — 2026-06-29

- **Objectives**: Implement the embedding layer (local, swappable) — DEC-020.
- **Work completed**: Verified `fastembed` + bge-small install/run on Python 3.14 (384d). Built `EmbeddingProvider` ABC + `LocalBGEProvider` (fastembed, lazy load, retry on load, logging), config-driven cached factory. Migration switched `kb_entries.embedding` to `vector(384)`. Tests (factory, dimension, real embed [CI-skipped]). Docs `EMBEDDINGS.md`. CI green.
- **Decisions made**: DEC-020 (local bge-small behind EmbeddingProvider abstraction).
- **Files changed**: `backend/app/ai/embeddings/*`, `backend/app/models.py`, `backend/app/core/config.py`, `backend/pyproject.toml`, new migration, `backend/tests/test_embeddings.py`, `documentation/EMBEDDINGS.md`, `.claude/DECISIONS.md`, `roadmap/SPRINT_1.md`, `.claude/PROGRESS.md`.
- **Bugs fixed**: `pytest.mark.skipif` given a string evaluated it as an expression (CI value "true" → NameError) — coerced to bool.
- **Next actions**: S1-09 KB indexing/retrieval (uses EmbeddingProvider; the search half needs no key). Full grounded answer + S1-08 generation need the **Anthropic API key**.

---

### Session 11 — 2026-06-29

- **Objectives**: Capability-driven delivery toward the first AI receptionist; build the KB→retrieval pipeline (no key needed).
- **Work completed**: Added `MILESTONES.md` (capability tracking). Built KB ingestion (`index_entry`: chunk→embed→store per-chunk rows), text chunking (`app/ai/chunking.py`), tenant-scoped pgvector cosine search + `retrieve_context` (`app/ai/knowledge_base.py`), and an HNSW index migration. 8 new tests (chunking + KB, via deterministic fake provider). CI green (24 tests).
- **Decisions made**: KB chunks stored as individual `kb_entries` rows (matches schema); character-based chunking for MVP (upgradeable to token-aware); retrieval depends only on `EmbeddingProvider`.
- **Files changed**: `MILESTONES.md`, `backend/app/ai/chunking.py`, `backend/app/ai/knowledge_base.py`, HNSW migration, `backend/tests/test_chunking.py`, `backend/tests/test_knowledge_base.py`, `.claude/PROGRESS.md`, `roadmap/SPRINT_1.md`.
- **Next actions**: Milestone 1 is complete through "retrieve relevant knowledge." Remaining items — **Claude grounded response** (BLOCKED on Anthropic API key) and final **send-reply wiring** (orchestrator + WhatsApp access token). Awaiting the Anthropic key to proceed.

---

### Session 12 — 2026-06-29

- **Objectives**: Build the complete LLM orchestration layer (provider-agnostic, mock default) so only the API key is missing.
- **Work completed**: `LLMProvider` interface + `LLMResponse`/`ChatMessage`; `MockProvider` (default) + `ClaudeProvider` (Anthropic, retries, lazy import); config-driven cached factory. Prompt builder + versioned system prompt + knowledge injection + history assembly (`app/ai/prompts.py`). Orchestrator `generate_reply` (`app/ai/orchestrator.py`). Background `generate_and_store_reply` storing outbound `pending_approval` (`app/ai/processing.py`). Wired webhook → background dispatch via overridable dependency. 11 new tests (LLM, orchestrator, processing, updated webhook). Verified full loop with real local embeddings + mock LLM. CI green (31 tests).
- **Decisions made**: DEC-021 (provider-agnostic LLM layer).
- **Files changed**: `backend/app/ai/llm/*`, `backend/app/ai/prompts.py`, `backend/app/ai/orchestrator.py`, `backend/app/ai/processing.py`, `backend/app/webhooks/whatsapp.py`, `backend/app/core/config.py`, `backend/pyproject.toml`, tests (`test_llm`, `test_orchestrator`, `test_whatsapp_webhook`), `documentation/LLM_ORCHESTRATION.md`, `MILESTONES.md`, `.claude/DECISIONS.md`, `.claude/PROGRESS.md`.
- **Next actions**: Loop runs end-to-end offline. To go live: `ANTHROPIC_API_KEY` + `LLM_PROVIDER=claude` (real Claude), and the approval→send step + WhatsApp access token (real outbound). Both credential-gated.

---

## Milestone Progress

| ID | Milestone | Status |
|----|-----------|--------|
| M1 | Foundation & Project Setup (memory system, structure, docs, Git) | In Progress |
| M2 | Customer Validation & Vertical Selection | Not Started |
| M3 | MVP Architecture & Tech Decisions Finalized | Not Started |
| M4 | Development Environment Ready | Not Started |
| M5 | Assisted-Mode MVP Built | Not Started |
| M6 | Pilot with Early Customers | Not Started |
| M7 | Autonomous Mode | Not Started |

---

## Metrics

Rough, honest estimates against currently-known scope. Not inflated.

| Area | Progress | Notes |
|------|----------|-------|
| Documentation | ~85% | Memory system, structure, READMEs, and full MVP design docs done; onboarding docs pending. |
| Architecture | ~80% (design Accepted) | Design documented & accepted; implementation underway (DB schema live). |
| Code | ~30% | Backend, CI+DB, schema, tenant scoping, WhatsApp webhook in/out, embeddings, KB ingestion+chunking+pgvector retrieval. Milestone 1: 9/11 capabilities done. |
| Customer interviews | 0% | 0 of a target-not-yet-set number completed. |
| MVP | 0% | No MVP work begun. |
| Testing | ~5% | CI pipeline live; 1 behaviour test (/health). |
| Deployment | 0% | No environments or pipelines. |

---

## Risks

Active risk list. Severity: High / Medium / Low.

- **R-001 (High)** — Building before validation. Risk of investing engineering effort in the wrong vertical/feature. *Mitigation*: validation gates in Sprint 0 (DEC-004); no implementation tasks until a vertical is chosen.
- **R-002 (Medium)** — WhatsApp Business API dependency. Approval process, policy constraints, and pricing are outside our control and not yet researched (TASK-008, RES-001). *Mitigation*: research integration path early before committing architecture.
- **R-003 (Medium)** — Key project facts unknown. Founder constraints, budget, and timeline are undefined, making planning estimates soft. *Mitigation*: TASK-001 captures these early.
- **R-004 (Medium)** — Compliance/data-privacy for stored conversations is unresearched (RES-001) and may constrain architecture. *Mitigation*: research before finalizing data model.
- **R-005 (Low)** — Documentation drift as the project evolves. *Mitigation*: update rules in `CLAUDE.md` §12 and append-only journals.
- **R-006 (Low)** — Vision scope creep diluting the narrow first product. *Mitigation*: MVP-first discipline (DEC-003) and separation of "Future Ideas" in `MEMORY.md`.

---

## Next Session

**Recommended starting point**: Begin Sprint 0 execution with the two unblocked P0 operations tasks:
1. **TASK-001** — capture founder & project constraints (budget, timeline, existing accounts, technical background) so planning rests on facts, not unknowns.
2. **TASK-002** — initialize Git and the GitHub remote, committing the current scaffolding (this repo is not yet under version control).

In parallel, start validation prep — **TASK-005** (scoring criteria) and **TASK-006** (interview script) — since customer discovery (TASK-003) is the longest-lead, highest-priority work and gates vertical selection.

Defer architecture/stack decisions (TASK-007–011) until the integration and model research (TASK-008, TASK-009) is underway.
