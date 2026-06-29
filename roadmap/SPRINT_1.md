# Sprint 1 — MVP Foundation Build

Status: **Ready to start** — architecture/stack decisions DEC-010–015 Accepted (2026-06-29).

> ⚠️ **Gate**: Sprint 1 builds the *vertical-agnostic core* only. Founder has chosen to proceed ahead of final vertical selection (DEC-006) — acceptable because nothing here is vertical-specific. Vertical-specific prompt/KB tuning is intentionally **out of Sprint 1**. Every task follows the three-stage workflow (Explain → Build → Review) per CLAUDE.md §18 / DEC-016.

Goal of Sprint 1: a working **vertical-agnostic skeleton** — a WhatsApp message can come in, be stored, run through the AI loop, and a drafted reply can be approved and sent from the dashboard, end to end in staging. Each task is scoped to **≤ 2–3 hours**.

Conventions for every task below: write tests where applicable; update the relevant doc/journal; commit with a clear message (DEC-007); no scope bundling.

---

### S1-01 — Repo init & backend skeleton — **DONE (2026-06-29)**
- **Objective**: Version control + base backend project skeleton. (Frontend scaffold split out — see S1-01b — because Node/npm is not yet installed; consistent with backend-first.)
- **Files created**: `.gitignore`, `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py` (health endpoint).
- **Dependencies**: none (closes TASK-002).
- **Outcome**: `GET /health` returns 200 `{"status":"ok"}` locally; FastAPI `/docs` works; 3 commits pushed to private `Dev555-ux/HIRA`. ✅
- **Done via**: venv + pip (no Poetry/uv); three Conventional-Commits commits.

### S1-01b — Frontend scaffold (Next.js) — **deferred**
- **Objective**: Scaffold the Next.js + TypeScript app once Node/npm is installed.
- **Files to create**: `frontend/` via `create-next-app`.
- **Dependencies**: install Node.js + npm first.
- **Expected output**: Next.js dev server runs and renders the starter page.
- **Testing checklist**: dev server boots; default page renders.
- **Note**: pulled out of S1-01 because Node was not installed; backend-first means this isn't needed until the frontend tasks (S1-12+).

### S1-02 — CI pipeline — **DONE (2026-06-29)**
- **Objective**: Automated lint + test on push.
- **Files created**: `.github/workflows/ci.yml`; `backend/tests/test_health.py` (+ `__init__.py`); `backend/pyproject.toml` dev deps + ruff/pytest config.
- **Dependencies**: S1-01.
- **Outcome**: CI runs on push/PR to main; ruff lint + format-check + pytest all green ✓. Failure path verified locally (ruff rejects unused import, exit 1). ✅
- **Deferred**: type-check (mypy) and a frontend CI job — added later. Minor: Node20-action + httpx2 deprecation warnings noted for future cleanup.

### S1-03 — Database schema & migrations — **DONE (2026-06-29)**
- **Objective**: Implement the `DATABASE.md` schema as migrations.
- **Files created**: `app/models.py` (9 tables), `app/core/config.py`, `app/db/{base,session}.py`, `alembic/` + initial migration, `.env`/`.env.example`.
- **Dev DB**: Postgres 16 + pgvector 0.8.3 via **Colima/Docker** container `hira-postgres` (decision: Docker, founder's choice).
- **Outcome**: migration applies cleanly; all 9 tables + indexes exist; up/down round-trip verified; `embedding` is `vector(1536)`; CI green. ✅
- **Bugs fixed in-task**: missing `pgvector` import in migration; setuptools flat-layout ambiguity (alembic/ vs app/) — caught by CI on fresh install.
- **Deferred**: DB-backed tests + Postgres service in CI (no query code yet); pgvector index + final embedding dimension (pending embedding-model choice); tighten status strings into constraints.
- **Schema note**: matches `DATABASE.md`; status fields implemented as strings (flexible for MVP).

### S1-04 — Tenant scoping & config — **DONE (2026-06-29)**
- **Objective**: `business_id` scoping primitive + settings/env loading.
- **Files created**: `app/db/tenant.py` (`tenant_query`, `get_scoped`); `tests/conftest.py` (Postgres-backed `db_session` fixture); `tests/test_tenant_scoping.py`. (`config.py` done in S1-03.)
- **Outcome**: explicit scoping helpers force `business_id` filtering and reject unscoped models; 3 isolation tests prove cross-tenant reads are blocked; CI now runs a pgvector Postgres service so DB tests run on every push. All green. ✅
- **Decision**: explicit `tenant_query` helper over global/implicit query rewriting — auditable, hard to bypass silently.

### S1-05 — Clerk auth on the API
- **Objective**: Validate Clerk JWT and resolve `business_id` on dashboard routes.
- **Files to create**: `backend/app/auth/` (JWT middleware/dependency).
- **Dependencies**: S1-04.
- **Expected output**: protected test endpoint returns 401 without token, 200 with a valid token.
- **Testing checklist**: 401/200 paths tested; user→business resolution tested.
- **Docs**: confirm against `API.md` auth section.

### S1-06 — WhatsApp webhook (verify + receive) — **DONE (2026-06-29)**
- **Objective**: `GET` verification handshake + `POST` receive with signature check & dedupe.
- **Files created**: `backend/app/webhooks/whatsapp.py`; tests `tests/test_whatsapp_webhook.py`; config + `.env.example` WhatsApp vars; router wired in `main.py`.
- **Outcome**: GET handshake verifies token; POST verifies HMAC, dedupes by `wa_message_id`, creates customer/conversation, persists inbound message, returns 200. 5 tests (handshake ok/bad, bad signature, persist, dedupe). CI green. ✅
- **Deferred**: async dispatch to the AI orchestrator (S1-08+); non-text message types; status callbacks. Real Meta verify-token/app-secret go in `.env` at integration time (dev defaults in code).
- **Bug fixed**: CI lacked `DATABASE_URL` (settings load at import via webhook) — added to CI env.

### S1-07 — Outbound messaging service — **DONE (2026-06-29)**
- **Objective**: Send a WhatsApp message via Cloud API (service-window text).
- **Files created**: `backend/app/services/messaging.py`; `tests/test_messaging.py`; WhatsApp send config vars; `httpx` runtime dep.
- **Outcome**: `send_text` posts to Meta Graph API, retries transient/5xx, does not retry 4xx, injectable client for tests. 3 tests, CI green. ✅
- **Deferred**: real live send (needs WhatsApp access token); template messages for outside-window sends.

### S1-08 — AI orchestrator skeleton + intent classification
- **Objective**: The conversation loop entry point + Haiku intent classifier.
- **Files to create**: `ai/orchestrator.py`, `prompts/intent_classifier.md`.
- **Dependencies**: S1-03.
- **Expected output**: given a message, returns intent + confidence; low confidence routes to escalation stub.
- **Testing checklist**: sample messages classify into expected intents; AI inputs/outputs logged.
- **Docs**: record prompt version in `prompts/`.

### S1-09 — Knowledge base + pgvector retrieval
- **Objective**: KB CRUD + embedding on write + vector search.
- **Files to create**: `ai/kb_retrieval.py`, KB service, `prompts/faq_answer.md`.
- **Dependencies**: S1-03, S1-08.
- **Expected output**: creating a KB entry stores an embedding; a query returns the most relevant entries; Sonnet composes a grounded answer.
- **Testing checklist**: retrieval returns expected entry for a paraphrased question; answer cites retrieved content.
- **Docs**: prompt version in `prompts/`.

### S1-10 — Calendar service + booking tool
- **Objective**: Google OAuth connect + availability/book/reschedule/cancel.
- **Files to create**: `backend/app/services/calendar.py`, `ai/tools/calendar_tools.py`.
- **Dependencies**: S1-03, S1-05.
- **Expected output**: connect a Google account; book a real event into a test calendar; reschedule/cancel work; conflicts return 409.
- **Testing checklist**: availability correct; double-book prevented; tool args validated before write.
- **Docs**: OAuth setup steps in `documentation/`.

### S1-11 — Escalation service + Assisted-Mode gate
- **Objective**: Wire escalation + the pending-approval gate into the loop.
- **Files to create**: `backend/app/services/escalation.py`; approval endpoints from `API.md`.
- **Dependencies**: S1-08, S1-07.
- **Expected output**: low-confidence/human-request → escalation row; AI drafts persist as `pending_approval`; approve → send.
- **Testing checklist**: escalation path tested; approve/reject transitions tested.
- **Docs**: confirm against `ARCHITECTURE.md` §3–4.

### S1-12 — Frontend shell + Clerk auth
- **Objective**: App shell, nav, protected routes, login.
- **Files to create**: `frontend/app/` layout + nav, Clerk integration.
- **Dependencies**: S1-01, S1-05.
- **Expected output**: sign in, land on `/app/dashboard`, nav between empty pages.
- **Testing checklist**: unauthenticated redirect to sign-in; authenticated access works.
- **Docs**: none beyond code.

### S1-13 — Inbox UI (list + thread + approve)
- **Objective**: The core Assisted-Mode surface.
- **Files to create**: `frontend/app/app/inbox/` pages + components.
- **Dependencies**: S1-11, S1-12, API from `API.md`.
- **Expected output**: list conversations, open a thread, see a pending AI draft, approve/edit/reject → message sends.
- **Testing checklist**: pending draft renders; approve triggers send; reject path works; empty state shown.
- **Docs**: confirm against `FRONTEND.md`.

### S1-14 — KB & Settings UI
- **Objective**: Manage KB entries; connect integrations; toggle mode.
- **Files to create**: `frontend/app/app/knowledge-base/`, `frontend/app/app/settings/`.
- **Dependencies**: S1-09, S1-10, S1-12.
- **Expected output**: create/edit KB entries; connect Google Calendar; view WhatsApp config.
- **Testing checklist**: KB create re-embeds; Google connect flow completes; settings persist.
- **Docs**: confirm against `FRONTEND.md`.

### S1-15 — Staging deploy + end-to-end smoke
- **Objective**: Deploy backend+DB (Railway) and frontend (Vercel); run the full inbound→approve→send loop in staging.
- **Files to create**: deploy config, `deployment/README.md` runbook, env setup.
- **Dependencies**: all prior.
- **Expected output**: a real WhatsApp message to the test number produces a pending draft in the dashboard; approving it replies to the customer.
- **Testing checklist**: full E2E loop passes in staging; logs/Sentry capturing events; rollback steps documented.
- **Docs**: `PROGRESS.md` milestone (M3/M4 progress), `deployment/README.md` runbook.

---

## Sprint 1 Definition of Done
A real inbound WhatsApp message, in staging, is stored, classified, answered or escalated by the AI, surfaced in the Inbox as a pending draft, and sent to the customer on human approval — with CI green, multi-tenant scoping enforced, AI turns logged, and the architecture docs reconciled to what was actually built.

## Explicitly NOT in Sprint 1
Autonomous Mode, appointment reminders/outbound templates, vertical-specific prompt tuning, billing/pricing, advanced analytics, document-based KB, multi-number support. These wait for later sprints and validation.
