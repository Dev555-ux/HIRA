# Sprint 1 — MVP Foundation Build

Status: **Ready to start** — architecture/stack decisions DEC-010–015 Accepted (2026-06-29).

> ⚠️ **Gate**: Sprint 1 builds the *vertical-agnostic core* only. Founder has chosen to proceed ahead of final vertical selection (DEC-006) — acceptable because nothing here is vertical-specific. Vertical-specific prompt/KB tuning is intentionally **out of Sprint 1**. Every task follows the three-stage workflow (Explain → Build → Review) per CLAUDE.md §18 / DEC-016.

Goal of Sprint 1: a working **vertical-agnostic skeleton** — a WhatsApp message can come in, be stored, run through the AI loop, and a drafted reply can be approved and sent from the dashboard, end to end in staging. Each task is scoped to **≤ 2–3 hours**.

Conventions for every task below: write tests where applicable; update the relevant doc/journal; commit with a clear message (DEC-007); no scope bundling.

---

### S1-01 — Repo init & project scaffolding
- **Objective**: Version control + base backend/frontend project skeletons.
- **Files to create**: `.gitignore`, `backend/pyproject.toml` (FastAPI app skeleton), `backend/app/main.py` (health endpoint), `frontend/` (Next.js app), root `Makefile`/scripts.
- **Dependencies**: none (closes TASK-002).
- **Expected output**: `GET /health` returns 200 locally; Next.js dev server runs; first commit pushed.
- **Testing checklist**: backend boots; `/health` 200; frontend renders; lint passes.
- **Docs**: `PROGRESS.md` session entry; mark TASK-002 done in `TODOS.md`.

### S1-02 — CI pipeline
- **Objective**: Automated lint + type-check + test on push.
- **Files to create**: `.github/workflows/ci.yml`, `infrastructure/` notes.
- **Dependencies**: S1-01.
- **Expected output**: CI green on a trivial PR.
- **Testing checklist**: CI runs on push; fails on a deliberately broken lint, passes when fixed.
- **Docs**: note pipeline in `infrastructure/README.md`.

### S1-03 — Database schema & migrations
- **Objective**: Implement the `DATABASE.md` schema as migrations.
- **Files to create**: migration files, ORM models (`backend/app/models/`), DB session setup.
- **Dependencies**: S1-01.
- **Expected output**: migrations apply cleanly to a local/staging Postgres; tables + indexes exist.
- **Testing checklist**: migrate up/down works; model CRUD smoke test passes.
- **Docs**: reconcile any schema deviations back into `DATABASE.md`.

### S1-04 — Tenant scoping & config
- **Objective**: `business_id` scoping primitive + settings/env loading.
- **Files to create**: `backend/app/core/config.py`, a tenant-scoping dependency/helper.
- **Dependencies**: S1-03.
- **Expected output**: a helper that guarantees queries are business-scoped; secrets loaded from env.
- **Testing checklist**: unit test proving cross-tenant access is blocked.
- **Docs**: none beyond code.

### S1-05 — Clerk auth on the API
- **Objective**: Validate Clerk JWT and resolve `business_id` on dashboard routes.
- **Files to create**: `backend/app/auth/` (JWT middleware/dependency).
- **Dependencies**: S1-04.
- **Expected output**: protected test endpoint returns 401 without token, 200 with a valid token.
- **Testing checklist**: 401/200 paths tested; user→business resolution tested.
- **Docs**: confirm against `API.md` auth section.

### S1-06 — WhatsApp webhook (verify + receive)
- **Objective**: `GET` verification handshake + `POST` receive with signature check & dedupe.
- **Files to create**: `backend/app/webhooks/whatsapp.py`.
- **Dependencies**: S1-03.
- **Expected output**: Meta verification succeeds; a posted sample payload is signature-verified, deduped, and persisted as a `message`.
- **Testing checklist**: bad signature → rejected; duplicate `wa_message_id` → not double-stored; valid → 200.
- **Docs**: note webhook setup steps in `documentation/`.

### S1-07 — Outbound messaging service
- **Objective**: Send a WhatsApp message via Cloud API (service-window text).
- **Files to create**: `backend/app/services/messaging.py`.
- **Dependencies**: S1-06.
- **Expected output**: a test send delivers a message to a test number; failures handled with retry/backoff.
- **Testing checklist**: success path (mocked + one real sandbox/live send); failure → graceful error, no crash.
- **Docs**: none beyond code.

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
