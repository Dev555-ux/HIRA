# TODOS.md

Living execution backlog for HIRA. Tasks move between sections as their status changes — they are never deleted or rewritten. Completed work is appended to the Completed section, never removed.

**Rules:**
- Never delete completed tasks; move tasks between sections rather than rewriting history.
- Keep priorities realistic.
- Do not add speculative features to the MVP — implementation tasks only enter the backlog after the relevant validation/decision is done.
- Customer validation tasks are kept separate from engineering tasks.
- Blockers are highlighted clearly in the Blocked section with what they wait on.

Task fields: ID · Title · Description · Priority · Category · Estimated effort · Dependencies · Status · Success criteria.

Categories: Business · Product · Technical · Architecture · Research · Operations · Validation.
Priority: P0 (critical) · P1 (high) · P2 (medium) · P3 (low).

---

## Current Sprint

> Focus: prepare for the MVP — validate customers, select the first vertical, finalize architecture, and set up the development environment. No application/implementation tasks until validation completes.

### TASK-001 — Define founder & project constraints
- **Description**: Capture currently-unknown facts in `PROJECT_CONTEXT.md`: founder technical background, budget, timeline/target launch, existing accounts (WhatsApp Business API, Google Cloud, hosting).
- **Priority**: P0
- **Category**: Operations
- **Estimated effort**: S (1 short session)
- **Dependencies**: None
- **Status**: To Do
- **Success criteria**: `PROJECT_CONTEXT.md` "Constraints" and "Team / Founder" sections contain confirmed values or an explicit reason each remains unknown.

### TASK-002 — Initialize Git repository and GitHub remote
- **Description**: Per DEC-007, `git init`, add an appropriate `.gitignore`, make the first commit of the current structure, and connect a GitHub remote.
- **Priority**: P0
- **Category**: Operations
- **Estimated effort**: S
- **Dependencies**: None
- **Status**: **Done (2026-06-29)** — see S1-01. Repo initialized, 3 commits, pushed to private `Dev555-ux/HIRA`.
- **Success criteria**: Repo is under version control, current scaffolding is committed, and the GitHub remote is set and pushed. ✅

### TASK-003 — Customer discovery interviews across candidate verticals
- **Description**: Conduct structured conversations with businesses in the six candidate verticals (DEC-006) to gather demand, willingness-to-pay, and sales-cycle signals. Validation work only — not engineering.
- **Priority**: P0
- **Category**: Validation
- **Estimated effort**: L (ongoing over the sprint)
- **Dependencies**: TASK-005 (criteria), TASK-006 (interview script) recommended first
- **Status**: To Do
- **Success criteria**: Comparable notes captured per vertical in `business/`, enough to score each on the DEC-006 criteria.

### TASK-004 — Select the first primary vertical
- **Description**: Using discovery findings, score the six verticals on market demand, willingness to pay, ease of sales, and product-market fit; choose one. Record as a new decision and update `PROJECT_CONTEXT.md` / `MEMORY.md`.
- **Priority**: P0
- **Category**: Business
- **Estimated effort**: S
- **Dependencies**: TASK-003
- **Status**: To Do
- **Success criteria**: One vertical chosen with documented rationale; DEC-006 review closed and a new "vertical selected" decision logged.

### TASK-005 — Define vertical scoring criteria
- **Description**: Make the DEC-006 criteria (demand, willingness to pay, ease of sales, PMF) concrete and measurable so verticals can be compared consistently.
- **Priority**: P1
- **Category**: Validation
- **Estimated effort**: S
- **Dependencies**: None
- **Status**: To Do
- **Success criteria**: A written scoring rubric exists in `business/`.

### TASK-006 — Build customer discovery interview script
- **Description**: Create an interview/outreach script tailored to surface the signals needed for vertical scoring.
- **Priority**: P1
- **Category**: Validation
- **Estimated effort**: S
- **Dependencies**: TASK-005
- **Status**: To Do
- **Success criteria**: Reusable script saved in `business/`.

### TASK-007 — Finalize MVP architecture
- **Description**: Decide the high-level architecture for the Assisted-Mode MVP: how WhatsApp messages flow to the AI engine, knowledge-base retrieval, Google Calendar booking/rescheduling, escalation, and conversation storage. Capture as architecture decisions and a diagram in `documentation/`.
- **Priority**: P1
- **Category**: Architecture
- **Estimated effort**: M
- **Dependencies**: TASK-008, TASK-009, TASK-010 (key technical choices feed the architecture)
- **Status**: To Do
- **Success criteria**: Architecture documented in `documentation/`, with decisions logged in `DECISIONS.md`; no open "how does X connect to Y" questions for MVP scope.

### TASK-008 — Decide WhatsApp integration path
- **Description**: Choose between the official WhatsApp Business API (direct) and a BSP/provider. Research cost, approval process, and constraints. (Open question from DEC-005.)
- **Priority**: P1
- **Category**: Research
- **Estimated effort**: M
- **Dependencies**: None
- **Status**: To Do
- **Success criteria**: A path is chosen and logged in `DECISIONS.md` with reasoning and trade-offs.

### TASK-009 — Decide AI model/provider for the conversation engine
- **Description**: Evaluate model/provider options against current pricing, context limits, capability, and latency. Per CLAUDE.md AI Engineering Principles, verify current specs rather than assuming.
- **Priority**: P1
- **Category**: Research
- **Estimated effort**: M
- **Dependencies**: None
- **Status**: To Do
- **Success criteria**: A model/provider chosen for the MVP and logged in `DECISIONS.md`.

### TASK-010 — Decide core stack and hosting
- **Description**: Choose backend language/framework, database, and hosting/infrastructure provider for the MVP, favoring boring and reliable per the technology philosophy.
- **Priority**: P1
- **Category**: Architecture
- **Estimated effort**: M
- **Dependencies**: None
- **Status**: To Do
- **Success criteria**: Stack and hosting chosen and logged in `DECISIONS.md`; reflected in `PROJECT_CONTEXT.md`.

### TASK-011 — Set up development environment
- **Description**: Establish local dev setup, project tooling/linting/formatting, and base CI once the stack is chosen. Preparation only — no feature code.
- **Priority**: P1
- **Category**: Operations
- **Estimated effort**: M
- **Dependencies**: TASK-010
- **Status**: To Do
- **Success criteria**: A new contributor can clone, install, and run lint/test scaffolding with documented steps.

---

## High Priority

> Cross-cutting urgent items that don't belong to a single sprint slice.

_Empty — no open high-priority items. The WhatsApp access-token replacement is complete; see Completed (TASK-C007)._

---

## Onboarding

> Self-service onboarding, per `ONBOARDING_IMPLEMENTATION_PLAN.md`. Milestone A is done; B–F are not started.

### ONBOARD-A — Business provisioning ✅ Done (2026-07-05)

- **Description**: Signup creates a real tenant. Adds `POST/GET /api/v1/onboarding/*`, a minimal `/onboarding` form (business name, industry, business email, country, timezone), a dashboard redirect gate for users with no business yet, and a placeholder "getting started" checklist on the dashboard.
- **Priority**: P1
- **Category**: Technical
- **Status**: Done — see `PROGRESS.md` Session 21.
- **Success criteria**: ✅ A Clerk sign-up with no matching `User` row is redirected to `/onboarding`; submitting the form creates a `Business` + owner `User` and lands on `/dashboard` showing the checklist. 63 backend tests / 14 frontend tests passing.

### ONBOARD-B — Knowledge ingestion pipeline (website/PDF/manual → drafts)

- **Priority**: P2
- **Category**: Technical
- **Status**: Partially built, unreviewed — see PROGRESS.md Session 22 (2026-07-06). `POST /api/v1/kb/website` ships a direct single-URL fetch→clean→chunk→index endpoint (`app/ai/web_import.py`), but indexes straight to live `kb_entries` with **no** `kb_entry_drafts` staging/approval step, conflicting with this task's own design in `ONBOARDING_ARCHITECTURE.md`. **Open decision for the founder**: accept direct-to-live as the permanent design, or add the review step on top. PDF ingestion, manual-drafts, dedup, and confidence-flagging are still not built either way.
- **Dependencies**: ONBOARD-A

### ONBOARD-C — Knowledge review UI + test-drive playground

- **Priority**: P2
- **Category**: Technical
- **Status**: To Do
- **Dependencies**: ONBOARD-B

### ONBOARD-D — WhatsApp connection (guided-manual, v1)

- **Priority**: P2
- **Category**: Technical
- **Status**: To Do
- **Dependencies**: ONBOARD-A; should not ship before `SEC-1`/`SEC-2` (see `IMPLEMENTATION_PLAN.md` Milestone 0) are done.

### ONBOARD-E — WhatsApp Embedded Signup (v2)

- **Priority**: P2
- **Category**: Business (external dependency) / Technical
- **Status**: To Do
- **Dependencies**: Meta Tech Provider / Embedded Signup approval — an external, non-engineering approval process. Should be kicked off in parallel now; it is the longest lead-time item in the onboarding plan.

### ONBOARD-F — Go-live, resumability, and polish

- **Priority**: P2
- **Category**: Technical
- **Status**: To Do
- **Dependencies**: ONBOARD-A through ONBOARD-D

---

## Infrastructure

> Production-readiness follow-ups, deferred until after MVP/pilot validation (not blocking current WhatsApp loop work, which is live and verified against Meta's Cloud API sandbox/test setup).

### INFRA-001 — Replace ngrok with a permanent HTTPS deployment

- **Description**: Move off the ngrok dev tunnel to a permanent hosted deployment (Railway, Fly.io, Render, or a VPS) with a stable public HTTPS endpoint for the WhatsApp webhook.
- **Priority**: P2
- **Category**: Operations
- **Status**: To Do

### INFRA-002 — Move secrets to a production secrets manager

- **Description**: Replace local `.env`-file secrets (WhatsApp token, Groq key, database URL, Clerk keys) with a managed secrets store appropriate to the chosen hosting platform, for production deployment.
- **Priority**: P2
- **Category**: Operations
- **Status**: To Do

### INFRA-003 — Add webhook health monitoring and alerting

- **Description**: Monitor the WhatsApp webhook endpoint's availability and error rate in production, with alerting on failures (e.g. signature-validation failures, send failures, downtime).
- **Priority**: P2
- **Category**: Operations
- **Status**: To Do

### INFRA-004 — Configure automatic backups for production data

- **Description**: Set up scheduled, automated backups for the production Postgres database (conversations, messages, KB entries, business/customer records).
- **Priority**: P2
- **Category**: Operations
- **Status**: To Do

### INFRA-005 — Add production logging and error monitoring

- **Description**: Add structured application logging and error monitoring/tracing (e.g. Sentry or equivalent) for production, replacing ad-hoc debug logging added during development.
- **Priority**: P2
- **Category**: Operations
- **Status**: To Do

### INFRA-006 — Verify webhook recovery after deployment

- **Description**: The current WhatsApp loop depends on a local development machine and ngrok (see PROGRESS.md Session 19 — 2026-07-04). Once deployed to a permanent HTTPS endpoint (INFRA-001), the full webhook path must be re-verified end-to-end before onboarding real businesses — the deployment target is a different environment than the one the live loop was proven against.
- **Priority**: P0
- **Category**: Operations
- **Estimated effort**: S
- **Dependencies**: INFRA-001 (permanent HTTPS deployment)
- **Status**: To Do
- **Success criteria**:
  - Deploy to a permanent HTTPS endpoint.
  - Update Meta webhook callback URL.
  - Verify webhook GET verification succeeds.
  - Verify real inbound messages arrive.
  - Verify outbound replies succeed.
  - Remove ngrok from the production path.
- **Reason**: The current deployment depends on a local development machine and ngrok. A production deployment should be verified end-to-end before onboarding real businesses.

### INFRA-007 — Add rate limiting to public/webhook endpoints

- **Description**: Found during Sprint 34's production-readiness security review (2026-07-10) — `POST /webhooks/whatsapp` and the public `GET /calendar/oauth/callback` have no request-rate limiting of any kind (confirmed: no `slowapi` or equivalent dependency, no limiter middleware anywhere in `app/`). Signature/HMAC verification on the webhook prevents forged payloads, but not a high-volume request flood. Not fixed this sprint — adding a limiter is a new dependency and needs a design decision (per-IP? per-business? which endpoints?), out of scope for a "no major new features, reuse existing architecture" sprint.
- **Priority**: P2
- **Category**: Operations
- **Estimated effort**: S
- **Dependencies**: None
- **Status**: To Do
- **Success criteria**: A rate limit is enforced on `POST /webhooks/whatsapp` and the OAuth callback, with a decision recorded in `DECISIONS.md` for the library/strategy chosen.

---

## Next Sprint

> Begins only after a vertical is selected (TASK-004) and architecture/stack are finalized. High-priority work immediately following the current sprint. Implementation tasks will be added here once validation gates pass — intentionally not pre-populated to avoid speculative MVP scope.

_No tasks yet. To be populated after the current sprint's validation and architecture gates are met._

---

## Product Backlog

> Validated work to be completed later. Items enter only once validated; none yet.

_Empty — nothing has cleared validation yet._

---

## Research

### TASK-008 — Decide WhatsApp integration path
> Listed in Current Sprint (active). Cross-listed here as an open investigation.

### TASK-009 — Decide AI model/provider
> Listed in Current Sprint (active). Cross-listed here as an open investigation.

### RES-001 — Legal/compliance requirements
- **Description**: Research WhatsApp Business Platform policy constraints and data-privacy obligations relevant to storing customer conversations, for the likely target market(s).
- **Priority**: P1
- **Category**: Research
- **Estimated effort**: M
- **Dependencies**: Partially depends on TASK-004 (target market influences applicable law)
- **Status**: Open
- **Success criteria**: Key compliance constraints documented in `documentation/`; any that affect architecture flagged into `DECISIONS.md`.

### RES-002 — Pricing model
- **Description**: Investigate viable pricing models for the chosen vertical (per-seat, per-conversation, flat subscription, etc.).
- **Priority**: P2
- **Category**: Research
- **Estimated effort**: M
- **Dependencies**: TASK-003, TASK-004
- **Status**: Open
- **Success criteria**: A proposed pricing model documented in `business/` with supporting rationale.

---

## Technical Debt

> Known improvements intentionally postponed.

Current technical debt is limited to production-infrastructure hardening — see the **Infrastructure** section above (ngrok replacement, secrets manager, webhook health monitoring, automated backups, production logging/error monitoring). The WhatsApp access token has been replaced with a permanent, non-expiring System User token (see Completed, TASK-C007) and is no longer a source of debt. As of 2026-07-04: the WhatsApp end-to-end pipeline (Milestone 4) is complete and live-verified, and all temporary `[WA-DEBUG]` instrumentation added during that debugging session has been removed.

**Sprint 35 audit findings (2026-07-10) — Medium/Low, not fixed this sprint:**

- **Analytics' "Pending approvals" tile has no error state.** `usePending()` on `/analytics` has no `isError` handling — a failed fetch silently shows `0` instead of a retryable error, the same bug class fixed on `/dashboard` and `/knowledge-base` this sprint. Lower priority than those two: `/analytics` is still a mostly-placeholder page (3 of 4 tiles already show "Coming soon"), so the stakes of a silent failure here are much lower than on the pages a beta owner actually depends on daily.
- **Appointment booking doesn't prevent picking a start time in the past.** Neither the "New appointment" nor "Reschedule" forms validate that `starts_at` is in the future before submitting — the backend would presumably still book it (no evidence either way it's rejected server-side). Cosmetic/edge-case: an owner mis-clicking a past date gets a weird historical appointment row, not a security or data-integrity issue.
- **Dashboard's "AI activity" tile unconditionally shows "Live."** Pre-existing (noted in PROGRESS.md Session 34) — it doesn't reflect whether Groq is actually reachable, since detecting that needs a new backend health signal. Not re-flagged as new; restated here only because Sprint 35's audit reconfirmed it's still the case.
- **Settings' WhatsApp configuration remains disabled placeholders.** Pre-existing, unchanged — no backend endpoint exists for self-serve WhatsApp connection (`ONBOARD-D`/`ONBOARD-E`).

---

## Blocked

> ⚠️ Items waiting on an external dependency or an upstream decision.

- **TASK-007 (Finalize MVP architecture)** — partially blocked until TASK-008, TASK-009, and TASK-010 are decided. Can begin high-level shaping in parallel but cannot be finalized.
- **TASK-011 (Dev environment setup)** — blocked on TASK-010 (stack/hosting choice).
- **RES-002 (Pricing model)** — blocked on customer discovery (TASK-003) and vertical selection (TASK-004).

---

## Completed

> Append-only. Never remove or rewrite.

### TASK-C001 — Create `.claude/` project memory scaffolding
- **Description**: Created the `.claude/` directory and the six memory files.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: `.claude/` exists with CLAUDE.md, PROJECT_CONTEXT.md, MEMORY.md, PROGRESS.md, TODOS.md, DECISIONS.md.

### TASK-C002 — Author CLAUDE.md operating manual
- **Description**: Wrote the 17-section operating manual defining role, philosophy, standards, and workflow.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: `CLAUDE.md` populated and approved.

### TASK-C003 — Build repository structure and READMEs
- **Description**: Created 14 top-level folders, each with a README explaining purpose/contents/rationale, plus the root `README.md`.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: Folder structure and READMEs created and approved.

### TASK-C004 — Populate PROJECT_CONTEXT.md
- **Description**: Recorded current project state, MVP scope, target verticals, and explicit unknowns.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: File populated and approved.

### TASK-C005 — Populate MEMORY.md
- **Description**: Established permanent cross-session memory with all required sections.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: File populated and approved.

### TASK-C006 — Populate DECISIONS.md
- **Description**: Logged decisions DEC-001 through DEC-009.
- **Category**: Operations
- **Status**: Done (2026-06-29)
- **Success criteria met**: File populated and approved.

### TASK-C007 — Replace temporary WhatsApp access token with a permanent System User token
- **Description**: Created a Meta System User and generated a permanent WhatsApp access token with the required permissions, replacing the temporary 24-hour dashboard token in `backend/.env`.
- **Category**: Operations
- **Status**: Done (2026-07-04)
- **Success criteria met**: Meta System User created ✅. Permanent token generated ✅. `WHATSAPP_ACCESS_TOKEN` in `backend/.env` replaced (only that line changed) ✅. Verified via Graph API: `GET /me` → `200` (resolves to `stoneveil-backend`) ✅; `GET /debug_token` confirms `"type":"SYSTEM_USER"`, `"expires_at":0` (non-expiring), scopes `whatsapp_business_management` + `whatsapp_business_messaging` ✅.
