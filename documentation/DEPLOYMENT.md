# Deployment Runbook

Status: written Sprint 69, **not yet executed**. `PRODUCTION_CHECKLIST.md`'s top blocking item ("Permanent HTTPS deployment... explicitly a founder decision") is what this document exists to close — but closing it means actually running these steps against real accounts, which only the founder can do (new billable infrastructure, real secrets). Nothing in this file has been run against a real Railway/Vercel project as of this writing; do not update `MEMORY.md`'s "Current Deployment" section to say otherwise until you've actually done it.

This is a runbook, not a design doc — see `TECH_STACK.md` (DEC-011) for why Railway/Vercel were chosen, `ARCHITECTURE.md` for the system itself, and `PRODUCTION_CHECKLIST.md` for the full list of what "production-ready" means beyond deployment alone.

---

## Architecture at a glance

Four deployed components: three Railway services in one project (Backend API,
Worker, PostgreSQL) and the Vercel frontend.

```
   Customer WhatsApp ──▶ Meta Cloud API ──POST /webhooks/whatsapp──┐
                                                                   ▼
  ┌───────────────────────── RAILWAY PROJECT "hira" ────────────────────────┐
  │                                                                          │
  │   ┌─────────────────┐   enqueue job (same     ┌──────────────────────┐  │
  │   │  Backend API     │   DB txn as the         │  PostgreSQL          │  │
  │   │  service         │   inbound message)      │  + pgvector plugin   │  │
  │   │  uvicorn         │────────────────────────▶│  messages, job_outbox│  │
  │   │  Dockerfile CMD  │◀───── reads/writes ─────│  kb_entries, ...     │  │
  │   │  GET /health     │                         └──────────┬───────────┘  │
  │   └────────┬─────────┘                                    │              │
  │            │ serves /api/*                     FOR UPDATE SKIP LOCKED     │
  │            │                                              ▼              │
  │            │                                   ┌──────────────────────┐  │
  │            │                                   │  Worker service       │  │
  │            │                                   │  run_worker.py        │  │
  │            │                                   │  (no HTTP port)       │  │
  │            │                                   │  claim → generate AI  │  │
  │            │                                   │  reply → store        │  │
  │            │                                   └──────────────────────┘  │
  └────────────┼─────────────────────────────────────────────────────────────┘
               │ NEXT_PUBLIC_API_BASE_URL (HTTPS)
        ┌──────┴──────────────┐
        │  VERCEL — Next.js    │  founder dashboard: Inbox / review workflow
        └─────────────────────┘
```

**Railway service architecture** — all three share the same project, the same
`DATABASE_URL` (injected by the Postgres plugin), and the same secrets. API and
Worker build from the **same** `backend/Dockerfile`; they differ only in start
command and config file:

| Service | Root dir | Config file | Start command | HTTP port | Healthcheck |
|---|---|---|---|---|---|
| **Backend API** | `backend/` | `railway.json` | Dockerfile `CMD` (`alembic upgrade head && uvicorn`) | `$PORT` | `/health` |
| **Worker** | `backend/` | `railway.worker.json` | `python scripts/run_worker.py` | none | none (log-based) |
| **PostgreSQL** | — (Railway plugin) | — | — | internal | Railway-managed |

**Deployment sequence (do these in order — details in the numbered sections below):**
1. Create the Railway project (§1)
2. Add the PostgreSQL plugin + enable `vector` extension (§1)
3. Deploy the Backend API service, set env vars (§2)
4. Migrations run automatically on API container start — confirm in logs (§3)
5. Deploy the Worker service (`railway.worker.json`) (§2b)
6. Verify the worker connected — its logs show `Outbox worker starting…` (§2b, §3)
7. Deploy the Frontend to Vercel, set env vars (§8)
8. Configure domains + CORS (`FRONTEND_URL` back into the API, redeploy) (§8)
9. Set `USE_TRANSACTIONAL_OUTBOX=true` on **both** API and Worker (§2, §2b)
10. Run end-to-end validation (§9)

---

## What already exists, ready to use

- `backend/Dockerfile` — builds and runs the backend (Python 3.12-slim, bakes in the local embedding model, runs `alembic upgrade head` then `uvicorn` on every start, reads `$PORT` dynamically). No changes needed.
- `backend/railway.json` — build/healthcheck/restart config for the **API** service, already points at `/health`. No changes needed.
- `backend/railway.worker.json` — build/restart config for the **Worker** service (v0.10.0): overrides the Dockerfile `CMD` with `startCommand: python scripts/run_worker.py`, no healthcheck (the worker binds no HTTP port), `restartPolicyType: ON_FAILURE`. Point the worker service's config path at this file (§2b).
- `backend/scripts/run_worker.py` — the worker entrypoint; imports `app.ai.tasks` so the `generate_ai_reply` handler is registered before the loop starts.
- `GET /health` — plain liveness check Railway's own healthcheck uses.
- `GET /health/whatsapp` (new, Sprint 69) — reports whether inbound WhatsApp traffic has gone quiet longer than `WEBHOOK_STALE_THRESHOLD_MINUTES` (default 60); meant for an external uptime monitor, not Railway's own healthcheck (see step 6).
- Sentry integration (`app/core/monitoring.py`) — a no-op until `SENTRY_DSN` is set; no code change needed to activate it, just the env var (step 4).
- `app/core/config.py`'s `_reject_insecure_production_secrets` — the backend will **refuse to boot** with `ENVIRONMENT=production` if: the WhatsApp secrets are still their dev defaults, `LLM_PROVIDER` is still `mock`, `ALLOW_MOCK_AUTH=true`, or `CLERK_JWKS_URL`/`CLERK_ISSUER`/`CALENDAR_ENCRYPTION_KEY` are unset (Sprint 69.5 production hardening — see the Sprint 69 Operations Readiness Audit, which found each of these could otherwise boot successfully and then fail silently or confusingly at runtime instead of at startup). This is intentional (SEC-1 / Sprint 69.5) — if the deploy fails at startup with a `ValueError` naming specific variables, that's this guard doing its job; fix the named variable(s) in Railway's Variables tab.

## What you'll need before starting

- A Railway account (you already have one — `railway` CLI is authenticated locally as Devansh Dhaundiyal). **Create a fresh project for HIRA** — the two existing projects ("perfect-renewal", "pretty-wholeness") are unrelated.
- A Vercel account, connected to the `Dev555-ux/HIRA` GitHub repo (Vercel's own "Preview Comments" already appear on PRs, suggesting some GitHub↔Vercel connection exists — confirm in the Vercel dashboard whether a project is already linked before creating a new one).
- Real values for: a Groq or Anthropic API key (`LLM_PROVIDER`), Clerk keys, a WhatsApp test business's Meta credentials (see `WHATSAPP_INTEGRATION.md` — this can be the founder's own existing test setup; self-serve per-business credentials from Sprint 69's other work don't change what the *platform itself* needs to boot), optionally Google Calendar OAuth credentials, and a Sentry DSN (free tier is enough for a beta).
- ~15 minutes for Railway, ~5 for Vercel.

---

## 1. Railway: create the project and database

```
railway login          # already done on this machine
railway init            # in repo root or backend/ — creates a new project, name it "hira" or similar
```

In the Railway dashboard for the new project:
1. **Add a service** → "GitHub Repo" → select `Dev555-ux/HIRA` → set the **root directory to `backend/`** (this repo is a monorepo; Railway needs to know the Dockerfile lives under `backend/`, not the repo root).
2. **Add a Postgres plugin** to the same project (Railway → "New" → "Database" → "PostgreSQL"). Railway automatically injects `DATABASE_URL` into the backend service's environment — you do not need to construct it by hand. Confirm the pgvector extension: Railway's managed Postgres supports the `vector` extension; it may need enabling once via Railway's query console: `CREATE EXTENSION IF NOT EXISTS vector;` (the app's own Alembic migrations also attempt this — check the first deploy's logs).
3. Railway auto-detects `backend/railway.json` and `backend/Dockerfile` once the root directory is set — no extra build configuration needed.
4. **Deploy on push**: Railway's GitHub integration deploys automatically on every push to whichever branch you connect (typically `main`). No custom GitHub Actions deploy workflow is needed — this is the "boring," native path.

## 2. Set backend environment variables

In the Railway service's **Variables** tab, set every one of these (see `backend/.env.example` for the full annotated list — do not copy the dev defaults):

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` (required — this is what activates SEC-1's insecure-default guard) |
| `WHATSAPP_VERIFY_TOKEN` | a real value you choose (not `dev-verify-token`) |
| `WHATSAPP_APP_SECRET` | from your Meta App |
| `WHATSAPP_ACCESS_TOKEN` | your System User token |
| `LLM_PROVIDER` | `groq` or `claude` (not `mock` — the backend now refuses to boot in production with `LLM_PROVIDER=mock`) + the matching `GROQ_API_KEY`/`ANTHROPIC_API_KEY` |
| `CLERK_JWKS_URL`, `CLERK_ISSUER` | from the Clerk dashboard — **required**; the backend refuses to boot in production without both. **Make sure these come from a Clerk *production* instance, not the default Development instance** — Clerk creates every app in Development mode first, and its API keys/URLs are real and functional, so nothing fails at signup or at this guard if you copy them by mistake (found live in production during RC-1). Development instances are served from a shared `*.clerk.accounts.dev` domain and have strict request-rate limits not meant for real traffic; a production instance needs its own domain (Clerk dashboard → your app → toggle "Production" / add a production instance). The backend logs a warning at startup (`app/main.py::_warn_if_clerk_looks_like_a_dev_instance`) if `CLERK_JWKS_URL` still looks like a `*.clerk.accounts.dev` domain with `ENVIRONMENT=production` — check Railway's logs after first deploy. |
| `ALLOW_MOCK_AUTH` | `false` (or leave unset) |
| `CALENDAR_ENCRYPTION_KEY` | **required**, regardless of whether Calendar is used for the pilot business — this key encrypts both Google Calendar OAuth refresh tokens *and*, since Sprint 69, every business's self-serve WhatsApp credentials (`app/whatsapp/security.py` reuses it). Generate once with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. The backend refuses to boot in production without it. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` | only if Calendar is being connected for the pilot business now; can be added later (unlike `CALENDAR_ENCRYPTION_KEY` above, these three are genuinely calendar-only) |
| `FRONTEND_URL` | the real Vercel production URL from step 8 below (circular dependency — deploy the backend first with a placeholder, then update this once Vercel's URL is known, then redeploy) |
| `SENTRY_DSN` | from sentry.io (step 4) |
| `WEBHOOK_STALE_THRESHOLD_MINUTES` | `60` is a reasonable starting point |
| `USE_TRANSACTIONAL_OUTBOX` | `true` to route inbound-message AI-reply generation through the durable outbox (v0.10.0). **Defaults `false`.** Only set `true` **after** the worker service (section 2b) is running — otherwise jobs enqueue and are never processed, so no AI replies are generated. Set the **same value** on the worker service. Rollback is flipping this back to `false` (webhook reverts to in-process generation, no redeploy). |

`DATABASE_URL` is injected automatically by the Postgres plugin — do not set it manually unless you're pointing at a different database.

## 2b. Deploy the outbox worker (REQUIRED for the AI review workflow)

The transactional outbox (v0.8.0+) splits inbound-message AI-reply generation into
a *separate long-lived worker process* (`backend/scripts/run_worker.py`). The
backend `Dockerfile`'s `CMD` runs **only** the API (`uvicorn`) — it does **not**
run the worker. So with `USE_TRANSACTIONAL_OUTBOX=true` and no worker, every
inbound WhatsApp message enqueues a `generate_ai_reply` job that is **never
processed**: no draft is generated and the Inbox review workflow silently breaks.

Deploy the worker as a **second Railway service in the same project**, sharing the
same Postgres and the same secrets as the API:

1. Railway → the HIRA project → **New → GitHub Repo → `Dev555-ux/HIRA`**, root
   directory **`backend/`** (same repo/Dockerfile as the API service).
2. Point this service at the worker config: **Settings → Config-as-code / Railway
   Config File** → `railway.worker.json`. That file sets the start command
   (`python scripts/run_worker.py`, overriding the Dockerfile `CMD` so this
   service runs the worker, not uvicorn) and the restart policy in version
   control. (Equivalent fallback: skip the config file and set a **Custom Start
   Command** of `python scripts/run_worker.py` in **Settings → Deploy** directly.)
3. **Variables:** set the *same* values as the API service — reference the shared
   `DATABASE_URL`, the LLM/WhatsApp/Clerk/`CALENDAR_ENCRYPTION_KEY` secrets, and
   **`USE_TRANSACTIONAL_OUTBOX=true`**. The worker needs the WhatsApp + LLM
   secrets because it is what actually calls the model and (in Autonomous mode)
   sends replies.
4. This service has **no HTTP port and no `/health`** — disable its healthcheck
   (or leave it, Railway tolerates a service that never binds a port). Confirm it
   started from its **logs**: `Outbox worker starting worker_id=…`.
5. Optional tuning (env, both defaults are fine to start):
   `OUTBOX_WORKER_BATCH_SIZE` (5), `OUTBOX_WORKER_POLL_INTERVAL` (0.5s),
   `OUTBOX_ZOMBIE_TIMEOUT_SECONDS` (300).

Scale throughput by adding replicas of this service — `FOR UPDATE SKIP LOCKED`
lets multiple workers share the queue without double-claiming.

### Worker service settings & operations

- **Resources (starting point):** the worker builds from the *same* image as the
  API (the BAAI/bge-small embedding model is baked in — ~130 MB resident — and
  the worker runs RAG retrieval + the LLM call), so size it like the API:
  **~0.5 vCPU, 512 MB–1 GB memory** to start. It is I/O-bound (poll → LLM/DB round
  trips), not CPU-bound; raise memory before CPU if you see pressure. Railway's
  default service resources are usually enough for a pilot; watch the metrics tab
  on first real traffic.
- **Scaling:** stateless and horizontally scalable — add replicas of this one
  service (Railway → service → Settings → Replicas) or duplicate it. `FOR UPDATE
  SKIP LOCKED` guarantees no two workers claim the same job. Each worker's
  `worker_id` (host:pid:uuid) appears in `locked_by`/logs so you can tell them
  apart. Start with **1**; add more only if `pending`/oldest-pending age climbs
  (watch Founder Ops metrics).
- **Restart policy:** `restartPolicyType: ON_FAILURE`, `maxRetries: 10`
  (`railway.worker.json`). A crash restarts the process; a graceful `SIGTERM` on
  redeploy exits cleanly (the worker finishes its in-flight job first — see the
  worker's shutdown handling — so no job is abandoned mid-flight).
- **Logging:** structured stdout, captured natively by Railway's log viewer.
  Key lines to look for: `Outbox worker starting …` (boot), `job claimed`,
  `job completed`, `retry scheduled`, `dead-lettered`, `zombie recovered`. No
  separate log shipping needed at this scale.
- **Failure recovery (two layers):** (1) the **process** — Railway restarts it on
  crash, and on restart the worker's *zombie sweep* returns any job left
  `processing` past `OUTBOX_ZOMBIE_TIMEOUT_SECONDS` (300s) back to `pending` so no
  work is lost; (2) the **job** — transient handler failures get exponential-
  backoff retries up to `max_attempts`, then move to the **dead-letter** state,
  visible/retryable via Founder Ops (`/api/v1/founder_ops/jobs`). So a worker
  crash never drops a message, and a poison job never blocks the queue.
- **Startup ordering:** deploy/verify the API first (it runs the migration that
  creates `job_outbox`). If the worker happens to start before the table exists,
  its first query fails and Railway restarts it until the table is present — the
  restart policy makes the race self-healing, but the deployment sequence avoids
  it by design (migrations at step 4, worker at step 5).

## 3. First deploy and verification

Push to the connected branch (or trigger a manual deploy from the Railway dashboard). Watch the build logs for:
- `alembic upgrade head` running successfully (this happens on every container start, per the Dockerfile's `CMD`).
- The embedding model already baked in (no Hugging Face download at runtime).

Once deployed, verify:
```
curl https://<your-railway-domain>/health
# {"status": "ok"}

curl https://<your-railway-domain>/health/whatsapp
# {"status": "no_traffic_yet"}   — expected before any real message arrives
```

If the service fails to boot, check the logs for a `ValueError` naming a specific insecure/missing variable — that's SEC-1's guard, and the error message says exactly which Railway variable to fix.

## 4. Sentry (centralized logging / error monitoring)

1. Create a free Sentry account/project (Python → FastAPI).
2. Copy the DSN into Railway's `SENTRY_DSN` variable (step 2).
3. No code change needed — `app/core/monitoring.py::init_sentry()` activates automatically once the DSN is present. Structured request logs (`app/core/request_logging.py`) already go to stdout, which Railway captures natively in its own log viewer — no separate log-shipping integration is needed at this scale.

## 5. Automated database backups

Railway's Postgres plugin has built-in scheduled backups — enable it from the plugin's **Settings** tab (retention/frequency depend on your Railway plan). This is a dashboard toggle, not something this codebase configures.

## 6. Webhook health monitoring (external uptime check)

`GET /health/whatsapp` (Sprint 69) reports staleness and raises a Sentry alert on its own, but something needs to actually *poll* it — that's an external monitor, not Railway's own healthcheck (which stays pointed at `/health` only, so a quiet-but-healthy webhook never triggers a restart loop). A free option: [UptimeRobot](https://uptimerobot.com) (or Railway's own "Cron"/monitoring add-ons, if available on your plan) hitting `https://<your-railway-domain>/health/whatsapp` every 15–30 minutes. A `503` response there means real customer messages may be going unanswered — treat it as page-worthy.

## 7. Graceful shutdown

Not yet implemented in code (`DEPLOY-4` in `IMPLEMENTATION_PLAN.md`, Medium priority, deferred) — Railway sends `SIGTERM` on redeploy/restart; uvicorn's default handling drains in-flight requests reasonably well for this app's traffic level. Revisit if in-flight-request loss is ever actually observed.

## 8. Vercel: frontend

1. In the Vercel dashboard, import the `Dev555-ux/HIRA` repo (if not already connected — check first, since CI's "Vercel Preview Comments" check suggests some connection may exist already) as a new project, **root directory `frontend/`**.
2. Set environment variables (Project Settings → Environment Variables), production scope:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | the Railway backend URL from step 3 |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | from Clerk — **must start with `pk_live_`, not `pk_test_`** (see the `CLERK_JWKS_URL` note in step 2; `pk_test_` is Clerk's Development-instance prefix). The frontend logs a console warning at load if a `pk_test_` key reaches a production build (`frontend/src/components/providers.tsx`). |
| `CLERK_SECRET_KEY` | from Clerk — same instance as the publishable key above (`sk_live_`, not `sk_test_`) |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |

3. Deploy. Vercel gives you a production domain (e.g. `hira.vercel.app` or a custom domain if configured) — copy it back into Railway's `FRONTEND_URL` variable (step 2) and redeploy the backend so CORS allows the real frontend origin. Note: `app/main.py`'s CORS config already allow-lists `https://hira-tau.vercel.app` specifically and any `https://hira-*.vercel.app` preview deployment via regex — if your production domain differs, add it explicitly rather than relying on the regex alone.

## 9. End-to-end verification (do this before calling it done)

- `/health` and `/health/whatsapp` both return 200 against the real Railway URL.
- Sign up a real test business through the deployed frontend → Clerk auth round-trips correctly.
- Check Railway's logs and the browser console for the Clerk-development-instance warning (`_warn_if_clerk_looks_like_a_dev_instance` / `providers.tsx`) — if either fires, the Clerk keys above are from the wrong instance even though sign-in still worked.
- Send a real WhatsApp message to the connected test number → confirm it's received (check `/health/whatsapp`'s `last_inbound_at`) and a reply is generated/sent.
- Trigger a real error (e.g. temporarily misconfigure something) and confirm it shows up in Sentry.
- Update `MEMORY.md`'s "Current Deployment" section and `IMPLEMENTATION_PLAN.md`'s Milestone 1 rows to reflect what's actually now live — **only after** this verification, not before.

## 10. Production rollback

The one fact that shapes everything below: `backend/Dockerfile`'s `CMD` runs `alembic upgrade head && uvicorn ...` on **every** container start, including a rollback. An older Docker image's `alembic/versions/` directory has no knowledge of any migration applied after that image was built — if the database has already moved past what the older image recognizes, its `alembic upgrade head` can't resolve the current revision and the container simply won't boot. Rollback here is not "just redeploy the previous image."

**Preferred strategy: forward-fix, not image rollback.** Push a new commit that fixes the problem and let Railway's normal GitHub-integration deploy handle it. This avoids the migration-mismatch risk above entirely and is almost always faster than orchestrating a coordinated image+database rollback. Reach for an image rollback only when a forward fix isn't realistically fast enough (e.g. a startup crash with no quick code fix available).

**When a plain image rollback is safe:** only when the bad deploy added no new file under `backend/alembic/versions/` — a pure config/env-var mistake or an application-logic bug that didn't touch the schema. In that case the database hasn't changed, so redeploying the previous Railway deployment (or reverting the commit and pushing) is safe as-is.

**When an Alembic downgrade is required first:** if the bad deploy included a new migration, downgrade the database *before* rolling back the image:
1. Identify the previous head revision (`alembic history` locally, or the migration file the bad deploy added — its `down_revision` is what you're downgrading to).
2. Run `alembic downgrade <previous-head-revision>` against the production database — from a machine with `DATABASE_URL` pointed at Railway's Postgres (`railway run` or a one-off shell against the service), not by pushing code.
3. Only then redeploy the older image. Its `alembic upgrade head` will now correctly find the database already at the revision it expects and no-op straight into `uvicorn` starting.

Skipping step 2 is exactly the failure mode described above: the older image boots, tries to upgrade, can't recognize the newer revision already stamped in `alembic_version`, and the container never starts.

**Recovery procedure after a failed deployment:**
1. Check Railway's deploy logs first. If it's `_reject_insecure_production_secrets` (SEC-1 / Sprint 69.5) rejecting a missing or insecure variable — a `ValueError` naming the exact variable(s) — fix that variable in the Variables tab and redeploy. No rollback needed; this is the guard working as intended.
2. If it's a genuine code or migration bug, decide forward-fix vs. rollback using the two points above.
3. If rolling back the image and a migration needs undoing, downgrade the database first, confirm `alembic current` (run the same way as step 2 above) matches the older image's expected head, then redeploy the older image.
4. After any rollback, re-run the smoke test checklist from the Sprint 69 Operations Readiness Audit before considering the incident closed.
5. Once the real fix ships forward, the next normal deploy's `alembic upgrade head` brings the database back to the latest schema automatically — no special handling needed on the way back up.

### Rollback by component

- **Outbox rollback (fastest kill-switch, no redeploy):** set
  `USE_TRANSACTIONAL_OUTBOX=false` on the API service. The webhook immediately
  reverts to generating replies in-process (the pre-v0.10.0 path); no new jobs
  are enqueued. Do this first if AI replies are misbehaving but the API itself is
  healthy. Jobs already `pending` will still be drained by the worker (harmless);
  leave the worker running, or scale it to 0. Flip back to `true` to re-enable.
- **Worker failures:** a crashing worker never affects the API or message intake
  — inbound messages are still stored, jobs still enqueue. Symptoms: `pending`
  count / oldest-pending age climb in Founder Ops; drafts stop appearing.
  Actions: check the worker logs; if it's a bad worker deploy, redeploy the
  previous worker deployment (the worker ships no migrations, so an image
  rollback is always safe for it); or set `USE_TRANSACTIONAL_OUTBOX=false` to
  fall back to in-process generation while you fix it. Jobs stuck `processing`
  from a killed worker auto-recover via the zombie sweep.
- **API failures:** use the forward-fix vs. image-rollback logic above (mind the
  migration-mismatch rule). The `/health` healthcheck + `ON_FAILURE` restart
  policy already restart a crashed API container.
- **Migration failures:** covered above — downgrade the DB *before* rolling back
  an image that shipped a migration.
- **Frontend failures:** Vercel keeps every prior deployment — **Instant Rollback**
  from the Vercel dashboard (Deployments → previous → Promote to Production) is
  immediate and safe (no schema coupling). The frontend is backward-compatible
  with older API payloads (review metadata is optional), so a frontend/back-end
  version skew degrades gracefully rather than breaking.

---

## Appendix: complete environment variable reference

Sources of truth: `backend/.env.example`, `backend/app/core/config.py`,
`frontend/.env.example`. "Scope" = which deployed component reads it. **API and
Worker must be given the same values** for every backend variable they share.

### Backend (set on BOTH the API and Worker Railway services)

| Variable | Scope | Required (prod) | Default | Sensitive | Description |
|---|---|---|---|---|---|
| `DATABASE_URL` | API, Worker | **Yes** | — | **Yes** | Postgres connection. Injected automatically by the Railway Postgres plugin; don't set by hand. `postgres://`/`postgresql://` are normalized to `postgresql+psycopg://`. |
| `ENVIRONMENT` | API, Worker | **Yes** | `development` | No | Set to `production` — activates the SEC-1 insecure-default boot guard. |
| `USE_TRANSACTIONAL_OUTBOX` | API, Worker | **Yes** (v0.10.0) | `false` | No | `true` routes AI-reply generation through the outbox+worker. Set on **both**; worker must exist first. Flip to `false` = instant rollback. |
| `WHATSAPP_VERIFY_TOKEN` | API | **Yes** | `dev-verify-token` | **Yes** | Any string you choose; enter the same in Meta's webhook config. |
| `WHATSAPP_APP_SECRET` | API, Worker | **Yes** | `dev-app-secret` | **Yes** | Meta App secret; verifies webhook signatures. |
| `WHATSAPP_ACCESS_TOKEN` | API, Worker | **Yes** | `dev-access-token` | **Yes** | Meta System User token; used to send replies. |
| `WHATSAPP_API_BASE` | API, Worker | No | `https://graph.facebook.com` | No | Rarely changed. |
| `WHATSAPP_GRAPH_VERSION` | API, Worker | No | `v21.0` | No | Meta Graph API version. |
| `LLM_PROVIDER` | API, Worker | **Yes** | `mock` | No | `groq` or `claude` — backend refuses to boot in prod with `mock`. |
| `GROQ_API_KEY` / `ANTHROPIC_API_KEY` | API, Worker | If provider matches | `""` | **Yes** | Key for the chosen provider. |
| `GROQ_MODEL` / `LLM_MODEL` | API, Worker | No | `llama-3.3-70b-versatile` / `claude-sonnet-4-6` | No | Model id per provider. |
| `LLM_MAX_TOKENS` | API, Worker | No | `1024` | No | Max tokens per reply. |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | API, Worker | No | `local_bge` / `BAAI/bge-small-en-v1.5` | No | Local model (baked into the image). Change both together + rebuild. |
| `CLERK_JWKS_URL`, `CLERK_ISSUER` | API | **Yes** | `""` | No | Clerk **production** instance (not `*.clerk.accounts.dev`). Backend won't boot in prod without both. |
| `ALLOW_MOCK_AUTH` | API | No | `false` | No | Must be `false`/unset in prod (guarded). |
| `FOUNDER_CLERK_USER_IDS` | API | If using Founder Ops | `""` | No | Comma-separated Clerk user ids allowed to reach `/api/v1/founder_ops/*`. |
| `CALENDAR_ENCRYPTION_KEY` | API, Worker | **Yes** | `""` | **Yes** | Fernet key encrypting Calendar tokens **and** per-business WhatsApp creds. Generate once; required to boot in prod. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_OAUTH_REDIRECT_URI` | API | Only if Calendar used now | `""` | **Yes** (secret) | Google OAuth; can be added later. |
| `FRONTEND_URL` | API | **Yes** | `http://localhost:3000` | No | Real Vercel URL for CORS (circular: deploy backend, then set once Vercel URL is known, redeploy). |
| `RAILWAY_PUBLIC_DOMAIN` | API | No | `""` | No | Injected by Railway for services with a public domain; used by the WhatsApp connect wizard. |
| `SENTRY_DSN` | API, Worker | No (recommended) | `""` | **Yes** | Enables Sentry; no-op if unset. |
| `WEBHOOK_STALE_THRESHOLD_MINUTES` | API | No | `60` | No | `/health/whatsapp` staleness threshold. |
| `RATE_LIMIT_DEMO_CHAT` / `RATE_LIMIT_KB_UPLOAD` / `RATE_LIMIT_BUSINESS_CREATION` | API | No | `20/minute` / `10/minute` / `5/hour` | No | Per-endpoint rate limits. |
| `OUTBOX_WORKER_POLL_INTERVAL` | Worker | No | `0.5` | No | Seconds to sleep when a poll finds no work. |
| `OUTBOX_WORKER_BATCH_SIZE` | Worker | No | `5` | No | Max jobs claimed per poll. |
| `OUTBOX_ZOMBIE_TIMEOUT_SECONDS` | Worker | No | `300` | No | `processing` longer than this → reclaimed to `pending`. |
| `OUTBOX_BACKOFF_BASE_SECONDS` / `OUTBOX_BACKOFF_MAX_SECONDS` | Worker | No | `2.0` / `3600.0` | No | Exponential retry backoff base/cap. |

### Frontend (Vercel, Production scope)

| Variable | Required (prod) | Default | Sensitive | Description |
|---|---|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | **Yes** | `http://localhost:8000` | No | The Railway backend URL. |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | **Yes** | `""` | No | Clerk publishable key (production instance). |
| `CLERK_SECRET_KEY` | **Yes** | `""` | **Yes** | Clerk secret key (server-side). |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` / `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | No | `/sign-in` / `/sign-up` | No | Point Clerk redirects at our own auth pages. |
