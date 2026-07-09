# Production Readiness Checklist

Status: Living checklist, first written **2026-07-10 (Sprint 34)**. Reflects an audit of the codebase as it exists today, not a plan — items marked **Done** were verified by reading the actual code/tests, not assumed. See `.claude/DECISIONS.md` and `ARCHITECTURE.md` for the reasoning behind anything referenced here.

This is a checklist, not a design doc — it exists to answer "can we put a real beta business on this today, and if not, what's blocking it." For narrative architecture detail, see `ARCHITECTURE.md`; for the raw backlog, see `.claude/TODOS.md`'s Infrastructure section (INFRA-001 through INFRA-007).

---

## Blocking — must resolve before onboarding a real beta business

- [ ] **Permanent HTTPS deployment.** The backend and frontend both currently run on a laptop + ngrok tunnel (`INFRA-001`). No hosting decision has been made yet — this is explicitly a founder decision (a paid service / infrastructure choice), not something this sprint could resolve unilaterally.
- [ ] **Production secrets manager.** All secrets (`WHATSAPP_ACCESS_TOKEN`, `GROQ_API_KEY`/`ANTHROPIC_API_KEY`, `DATABASE_URL`, `CALENDAR_ENCRYPTION_KEY`, Clerk keys) live in a local, git-ignored `.env` file today (`INFRA-002`). Fine for one founder's laptop; not fine for a real deployment.
- [ ] **`FRONTEND_URL` set to the real domain** once deployed. Confirmed this sprint: the backend's CORS policy (`app/main.py`) and the Google OAuth callback redirect (`app/api/calendar.py`) both derive from `settings.frontend_url`, which defaults to `http://localhost:3000`. Leaving it unset in production means the deployed dashboard is silently CORS-blocked from calling its own API. (Fixed this sprint: CORS previously had *no* path from this setting into `allow_origins` at all — see below.)
- [ ] **Re-verify the WhatsApp webhook end-to-end against the deployed URL** (`INFRA-006`) — the current live-verified round-trip (`PROGRESS.md`, 2026-07-04) was proven against ngrok, a different network path than a real deployment.

## Fixed this sprint (Sprint 34)

- [x] **CORS didn't actually include the configured frontend URL.** `app/main.py` hardcoded `allow_origins` to three localhost dev ports; `settings.frontend_url` existed (added Sprint 29 for the OAuth callback) but nothing wired it into CORS, despite a code comment claiming they were kept in sync. Fixed: `frontend_url` is now included in `allow_origins`. Regression tests in `tests/test_main.py`.
- [x] **`.env.example` was missing four documented settings** (`FRONTEND_URL`, `LLM_MAX_TOKENS`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`) that `app/core/config.py` already defines with defaults — added for completeness so a new deploy doesn't have to read source to discover them.
- [x] **A demo workspace now exists** (`backend/scripts/seed_demo_workspace.py`) — a fully-populated, idempotent demo `Business` with no WhatsApp/Calendar connection required: knowledge base (reuses the existing dental-clinic fact set from `app/onboarding/knowledge.py`), 5 customers with leads spanning every pipeline stage (new → contacted → qualified → won → lost), a pending AI reply (populates `/pending`), and an upcoming appointment. Lets the founder demo the full dashboard experience to a beta prospect without needing that prospect's real WhatsApp number or Google Calendar first. Run: `.venv/bin/python scripts/seed_demo_workspace.py` (idempotent — safe to re-run).

## Security review findings (Sprint 34 audit — no code change needed)

Reviewed and confirmed already safe by design:

- **Mock auth cannot activate in production.** `get_token_verifier()` (`app/auth/dependencies.py`) only falls back to the fixed dev token when *both* `CLERK_JWKS_URL` is unset *and* `ALLOW_MOCK_AUTH` is true. A real deployment sets `CLERK_JWKS_URL` (the whole point of going live), so this is a genuine interlock, not just a default — even a stray `ALLOW_MOCK_AUTH=true` left in a production `.env` wouldn't bypass real auth.
- **Tenant isolation.** Every business-owned table is scoped via `get_scoped()`/`tenant_query()` (see `ARCHITECTURE.md` §"Tenant isolation") — this has been exercised by cross-tenant-access tests (→ `404`, not `403`, so existence isn't leaked) across every sprint since DEC-013's founding schema. No gap found.
- **Webhook signature verification.** `POST /webhooks/whatsapp` verifies Meta's HMAC-SHA256 signature and does a timing-safe comparison for `WHATSAPP_VERIFY_TOKEN`. No forged-payload risk found.
- **No secret leakage in logs.** Grepped every `logger.info`/`logger.debug`/`print` call in `app/` for anything token/key/secret/credential-adjacent — none found.
- **No stack-trace leakage.** FastAPI's `debug` flag defaults to `False` (never explicitly enabled) — an unhandled exception returns a generic `500`, not a Python traceback, by default.
- **N+1 query risk checked** in the two highest-traffic list endpoints (`GET /customers`, `GET /conversations`) — both already batch-load related data (`_conversation_stats`/`_leads_by_customer` as grouped queries, a single `JOIN` for conversations) rather than per-row queries. No fix needed.

Known gaps, not fixed this sprint (each requires a new dependency or a hosting/paid-service decision, out of scope for "no major new features, reuse existing architecture"):

- **No rate limiting** on `POST /webhooks/whatsapp` or the public OAuth callback — tracked as `INFRA-007` (new, added this sprint).
- **No production secrets manager, monitoring, or automated backups** — `INFRA-002`/`INFRA-003`/`INFRA-004`/`INFRA-005`, all pre-existing, all blocked on a hosting decision.

## Reliability review findings (Sprint 34 audit — no code change needed)

- **DB connections**: `pool_pre_ping=True` already set (`app/db/session.py`) — avoids stale-connection errors after idle periods. Pool size/overflow left at SQLAlchemy defaults; no evidence of a real problem at current scale, so not tuned (avoiding a speculative change).
- **External API retries**: Groq calls retry up to 3× (linear backoff) on connection errors/timeouts/429/5xx (`app/ai/llm/groq.py`); WhatsApp sends retry up to 3× on 5xx/network errors (`app/services/messaging.py`). Both pre-existing, confirmed still correct.
- **`/health`** is a pure liveness check (no DB ping) — this is intentional, not a gap: conflating liveness and readiness checks can cause bad restart-loop behavior under some hosting platforms. Left unchanged.
- **Generation-failure handling**: a failed `generate_and_store_reply()` still produces customer silence with no automatic escalation (a pre-existing, already-documented gap — see `ARCHITECTURE.md` §7's "Fallback behaviour"). Not a new finding; not addressed this sprint (would be a feature, not a fix).

## End-to-end owner journey (audited, not rebuilt)

Walked the full first-time-owner path end-to-end against the code (not just individually-tested pages): sign up (`/onboarding`) → land on `/dashboard` with the `OnboardingChecklist` → import knowledge (`/knowledge-base`) → test the AI (`/playground`) → review/approve AI replies (`/pending`) → browse customers/leads (`/customers`, `/leads`) → configure Calendar/Appointments → Settings. No broken links or dead-end states found beyond what Sprint 33 already fixed (Settings' dead Business Information card, Calendar's missing error states). The one real gap this journey still has — connecting a business's own WhatsApp number — has no self-serve path yet (`ONBOARD-D`/`ONBOARD-E` in `TODOS.md`) and is honestly labeled "Coming soon" in the checklist rather than a broken control.

## Not evaluated this sprint

Explicitly out of scope, each requiring a founder decision this sprint's "no major new features" constraint doesn't cover:

- Choice of hosting provider (`INFRA-001`).
- Choice of secrets manager (`INFRA-002`).
- Choice of monitoring/error-tracking tool (`INFRA-005`) — would be a new paid integration.
- Rate-limiting library/strategy (`INFRA-007`, newly tracked this sprint).
