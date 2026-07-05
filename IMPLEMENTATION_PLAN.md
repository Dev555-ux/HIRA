# HIRA — Implementation Plan

Remediation roadmap derived from the senior backend architecture audit (see chat history / `.claude/PROGRESS.md` for the audit itself). This plan does not introduce new findings — it sequences the existing ones into a realistic roadmap.

**Stage definitions used below** (since "blocks X" needs a shared meaning):
- **MVP** — the four milestones in `MILESTONES.md`. **Already complete.** Included as a column for completeness; nothing here blocks it retroactively.
- **Pilot** — one real business, real customers, founder actively monitoring day-to-day. Low volume, single tenant, supervised — mistakes are recoverable by a human watching closely.
- **Production** — general availability: multiple tenants, unattended operation, real trust/SLA expectations.
- **Scale** — traffic/tenant volume high enough that performance, cost, and concurrency start to matter on their own terms.

Each finding keeps its original severity from the audit. Effort uses S (hours–1 day) / M (1–3 days) / L (3–10 days) / XL (multiple weeks).

---

## Milestone 0 — Pre-Pilot Hardening

**Goal**: close the issues that would embarrass or actively hurt a real pilot business, before any real external customer talks to HIRA. Everything here is cheap (S, one M) relative to its impact — this is the highest-ROI block of work in the whole plan.

| ID | Finding | Priority | Effort | Dependencies | Blocks | Order |
|---|---|---|---|---|---|---|
| SEC-1 | Insecure default secrets (`WHATSAPP_APP_SECRET`/`VERIFY_TOKEN`/`ACCESS_TOKEN` fall back to guessable defaults) | Critical | S | None | Pilot, Production | 1 |
| SCALE-1 | Async route blocks on sync DB I/O (quick fix: `receive` → `def`) | Critical | S | None | Production, Scale (not Pilot at low volume, but free to fix now) | 2 |
| REL-3 | Double-send race on `approve_and_send` | Medium | S | None | Production (cheap enough to just fix now) | 3 |
| AI-2 | No relevance threshold on KB retrieval | Medium | S | None | Pilot (reply quality) | 4 |
| AI-3 | Non-text messages silently dropped (empty-body reply) | Medium | S | None | Pilot (real customers will send voice notes/images) | 5 |
| REL-2 | No fallback reply / escalation on AI generation failure | High | M | None | Pilot, Production | 6 |
| API-1 | No reject endpoint (Assisted Mode workflow incomplete) | Medium | S | None | Pilot (core workflow gap) | 7 |
| PERF-1 | `expire_on_commit=True` default (extra round-trip per commit) | Medium | S | None | — (free win, bundle in) | 8 |
| SEC-2 | No CORS configuration | High | S | Needs the real frontend origin decided (can stub with env-driven origin) | Pilot, Production | 9 |

**Milestone 0 total effort**: ~1 (M) + 8 (S) ≈ **1–1.5 weeks** for one engineer.

**Why this grouping**: every item here is S or M effort and either closes a real security hole (SEC-1), prevents a bad first customer impression (AI-2, AI-3, REL-2, API-1), or is free to fix while touching adjacent code (PERF-1, REL-3). None require new infrastructure — they're all code-only changes, consistent with "do not modify source code" for *this* planning document, but flagged as the first implementation pass once work begins.

---

## Milestone 1 — Deployment & Observability

**Goal**: get off the founder's laptop + ngrok and onto infrastructure that can run unattended and be debugged after the fact. This is the precondition for a *credible* pilot (one that doesn't depend on a laptop staying on).

| ID | Finding | Priority | Effort | Dependencies | Blocks | Order |
|---|---|---|---|---|---|---|
| DEPLOY-1 | No production deployment exists (`INFRA-001`) | Critical | M | SEC-1, SEC-2 (don't deploy with insecure defaults or no CORS) | Pilot (recommended), Production (required) | 10 |
| DEPLOY-3 | No automated database backups (`INFRA-004`) | High | S | DEPLOY-1 (needs a managed DB target) | Pilot (recommended), Production (required) | 11 |
| DEPLOY-2 | No centralized logging / error monitoring (`INFRA-005`) | High | M | DEPLOY-1 | Pilot (recommended), Production (required) | 12 |
| DEPLOY-5 | No webhook health monitoring/alerting (`INFRA-003`, `INFRA-006`) | Medium | M | DEPLOY-1, DEPLOY-2 | Production | 13 |
| WA-1 | Unknown-business payloads dropped silently, no alerting | Low | S | DEPLOY-2 (needs somewhere to alert to) | Production | 14 |
| DEPLOY-4 | No graceful shutdown handling | Medium | M | DEPLOY-1 | Production (superseded later by REL-1's durable queue, but cheap interim mitigation) | 15 |

**Milestone 1 total effort**: ~1 M (deploy) + 1 S + 2 M + 1 M + 1 S ≈ **2–3 weeks**.

**Why this grouping**: all of these depend on DEPLOY-1 (there's nowhere to deploy backups/logging/monitoring/health-checks to until the app is hosted somewhere real), so they're sequenced right after it. This milestone is the honest cost of "leaving the laptop" — it's the largest chunk of calendar time in the plan even though no single item is individually huge.

**→ Pilot can realistically begin after Milestone 0 + Milestone 1.**

---

## Milestone 2 — Production Hardening (Multi-Tenant General Availability)

**Goal**: everything needed to responsibly onboard a *second* real business and run unattended with real customer data and money on the line. Not required to run the first pilot; required before general availability.

| ID | Finding | Priority | Effort | Dependencies | Blocks | Order |
|---|---|---|---|---|---|---|
| SCALE-3 | No per-tenant rate limiting (noisy-neighbor risk) | Medium | M | None | Production, Scale | 16 |
| SEC-5 | No rate limiting on the webhook endpoint itself | Medium | M | Can share infra with SCALE-3 | Production | 17 |
| SEC-4 | No data retention/deletion policy for customer PII | Medium | M | Depends on legal research (`RES-001`, already open in `TODOS.md`) | Production | 18 |
| WA-2 | 24-hour service window tracked but never enforced before send | Medium | M | None | Production | 19 |
| REL-4 | Dedup race on concurrent webhook deliveries (uncaught `IntegrityError`) | Low | S | None | Production | 20 |
| MAINT-2 | String-typed status/role/type columns, no CHECK constraints | Low | S | Needs a migration | Production (data-integrity hygiene) | 21 |
| SEC-3 | Prompt injection / no output validation — full guardrail | High | M–L | REL-2 (fallback path) helps here; benefits from DEPLOY-2 (to see injection attempts in logs) | Production (specifically: general Autonomous Mode availability) | 22 |

**Milestone 2 total effort**: ~3 M (rate limiting × 2, window enforcement) + 1 M (retention, pending legal scope) + 1 S + 1 S + 1 M–L (guardrails) ≈ **3–4 weeks**.

**Stopgap for Pilot**: SEC-3 (prompt injection guardrails) is the one Milestone-2 item worth pulling forward conceptually — not by doing the engineering early, but by **restricting the pilot business to Assisted Mode** (human reviews every reply before send) rather than Autonomous Mode. That sidesteps the risk entirely at zero engineering cost until real guardrails are built.

---

## Milestone 3 — Scale Readiness

**Goal**: everything that only matters once real traffic/concurrency arrives. Deliberately deferred — building this before there's a second or third active tenant is premature optimization.

| ID | Finding | Priority | Effort | Dependencies | Blocks | Order |
|---|---|---|---|---|---|---|
| REL-1 / SCALE-2 | Background task loss on restart; AI processing has no durable queue | High | XL | DEPLOY-1 (needs real infra to host a worker) | Scale (not Pilot; recommended before heavy Production load) | 23 |
| PERF-2 | No explicit connection pool sizing | Low | S | Needs a real load estimate first | Scale | 24 |
| SCALE-4 / API-2 | No pagination on `/api/v1/pending` | Low | S | None | Scale | 25 |
| TENANT-1 | No DB-level tenant isolation (Postgres RLS as defense-in-depth) | Medium | L | Real multi-tenant data volume to justify the investment | Scale | 26 |
| SCALE-1 (full) | Full async SQLAlchemy migration (if the Milestone-0 quick fix proves insufficient under load) | Critical→High (downgraded once quick fix ships) | XL | Load testing shows the quick fix (`def` route) is insufficient | Scale | 27 |

**Milestone 3 total effort**: **4–8 weeks**, dominated by the two XL items (durable queue, and — only if needed — full async migration). Recommend load-testing before committing engineering time to either; the Milestone-0 quick fixes may hold up longer than expected at realistic small-business message volumes.

---

## Recommended Implementation Order (flat sequence)

1. `SEC-1` — remove insecure default secrets
2. `SCALE-1` (quick fix) — `receive` route → `def`
3. `REL-3` — atomic status transition on approve
4. `AI-2` — relevance threshold on retrieval
5. `AI-3` — handle non-text messages
6. `REL-2` — fallback reply + escalation on failure
7. `API-1` — reject endpoint
8. `PERF-1` — `expire_on_commit=False`
9. `SEC-2` — CORS middleware
10. `DEPLOY-1` — deploy to permanent hosting
11. `DEPLOY-3` — automated backups
12. `DEPLOY-2` — centralized logging + error monitoring
13. `DEPLOY-5` — webhook health monitoring/alerting
14. `WA-1` — unknown-business alerting
15. `DEPLOY-4` — graceful shutdown

**← Pilot starts here (Assisted Mode only, per the SEC-3 stopgap above) →**

16. `SCALE-3` — per-tenant rate limiting
17. `SEC-5` — webhook rate limiting
18. `SEC-4` — data retention/deletion policy (pending legal scope from `RES-001`)
19. `WA-2` — 24h window enforcement
20. `REL-4` — dedup race handling
21. `MAINT-2` — CHECK constraints
22. `SEC-3` — prompt-injection guardrails (unlocks general Autonomous Mode availability)

**← General Production availability starts here →**

23. `REL-1` / `SCALE-2` — durable task queue
24. `PERF-2` — connection pool sizing (after real load data)
25. `SCALE-4` / `API-2` — pagination
26. `TENANT-1` — Postgres RLS
27. `SCALE-1` (full) — async SQLAlchemy migration, only if load-testing shows it's needed

**No action planned** (informational findings from the audit, not remediation items):
- `MAINT-1` — provider config requires a full restart to change; documented behavior, not a defect.
- `DB-1` — `appointments`/`escalations`/`calendar_credentials` tables exist unused; revisit when actually building Google Calendar / human handoff (see `ARCHITECTURE.md` §15 roadmap), not part of this remediation plan.

---

## Roadmap Summary

| Milestone | Focus | Effort | Unlocks |
|---|---|---|---|
| 0 — Pre-Pilot Hardening | Cheap, high-impact code fixes | ~1–1.5 weeks | Safe to show HIRA to a real business |
| 1 — Deployment & Observability | Get off the laptop | ~2–3 weeks | **Pilot** |
| 2 — Production Hardening | Multi-tenant safety, compliance, quality | ~3–4 weeks | **General Production** |
| 3 — Scale Readiness | Durable queue, async migration, RLS | ~4–8 weeks (mostly deferred, load-test-gated) | **Scale** |

**Total to Pilot**: ~3–4.5 weeks of engineering effort.
**Total to general Production**: ~6–8.5 weeks.
**Scale work**: intentionally not on the critical path — start it only once real usage data justifies the XL items.

This sequencing front-loads the cheapest, highest-severity fixes (Milestone 0 is almost entirely S-effort Critical/High items), defers the two genuinely expensive items (durable queue, async migration) until there's real traffic to justify them, and treats "deploy somewhere real" as its own gating milestone rather than bundling it in with either pre- or post-pilot hardening.
