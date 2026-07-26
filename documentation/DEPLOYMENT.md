# Deployment Runbook

Status: written Sprint 69, **not yet executed**. `PRODUCTION_CHECKLIST.md`'s top blocking item ("Permanent HTTPS deployment... explicitly a founder decision") is what this document exists to close — but closing it means actually running these steps against real accounts, which only the founder can do (new billable infrastructure, real secrets). Nothing in this file has been run against a real Railway/Vercel project as of this writing; do not update `MEMORY.md`'s "Current Deployment" section to say otherwise until you've actually done it.

This is a runbook, not a design doc — see `TECH_STACK.md` (DEC-011) for why Railway/Vercel were chosen, `ARCHITECTURE.md` for the system itself, and `PRODUCTION_CHECKLIST.md` for the full list of what "production-ready" means beyond deployment alone.

---

## What already exists, ready to use

- `backend/Dockerfile` — builds and runs the backend (Python 3.12-slim, bakes in the local embedding model, runs `alembic upgrade head` then `uvicorn` on every start, reads `$PORT` dynamically). No changes needed.
- `backend/railway.json` — build/healthcheck/restart config, already points at `/health`. No changes needed.
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

`DATABASE_URL` is injected automatically by the Postgres plugin — do not set it manually unless you're pointing at a different database.

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
