# AWS EC2 Deployment Runbook (Docker)

Replaces Railway as the backend's hosting target. The Vercel frontend is
unaffected — see `documentation/DEPLOYMENT.md` §8 for that half, which still
applies unchanged. This doc covers only the backend: FastAPI API, the outbox
worker, and Postgres, all on one Docker-Compose-managed Ubuntu EC2 instance
behind Nginx.

Why containerized Postgres instead of RDS, and why one instance instead of
managed PaaS: this matches the codebase's existing "single instance, no
infra ahead of real need" reasoning (`ONBOARDING_ARCHITECTURE.md`) at the
current beta scale — a founder decision made explicitly for this migration,
not a default. Revisit (RDS, multiple instances, a load balancer) once real
traffic/uptime requirements justify the added cost and complexity.

## Related Operational Documentation

- [PRODUCTION_RUNBOOK.md](PRODUCTION_RUNBOOK.md) — command-by-command
  verification and recovery steps for every part of this deployment (SSL,
  backups, worker/Docker/nginx health, rollback, and more).
- [PRODUCTION_HEALTH_CHECKLIST.md](PRODUCTION_HEALTH_CHECKLIST.md) — the
  5-minute checklist to run after every deployment.

---

## Architecture at a glance

```
   Customer WhatsApp ──▶ Meta Cloud API ──POST /webhooks/whatsapp──┐
                                                                    ▼
  ┌───────────────────── EC2 instance (Ubuntu, Docker Compose) ─────────────┐
  │                                                                          │
  │   ┌────────┐   443/80    ┌──────────────────┐  enqueue job   ┌────────┐ │
  │   │ Nginx   │───────────▶│  api              │───────────────▶│Postgres│ │
  │   │ TLS     │◀───────────│  uvicorn          │◀── reads/writes─│+pgvector│ │
  │   │ term.   │            │  --proxy-headers  │                │job_outbox│ │
  │   └────────┘            │  GET /health       │                └───┬────┘ │
  │        ▲                └──────────────────┘                     │      │
  │        │ only 80/443 published to the host                FOR UPDATE    │
  │        │                                                  SKIP LOCKED    │
  │                          ┌──────────────────┐                    │      │
  │                          │  worker           │◀───────────────────┘      │
  │                          │  run_worker.py    │                           │
  │                          │  (no HTTP port)   │                           │
  │                          └──────────────────┘                           │
  └──────────────────────────────────────────────────────────────────────────┘
               │ NEXT_PUBLIC_API_BASE_URL (HTTPS)
        ┌──────┴──────────────┐
        │  VERCEL — Next.js    │  founder dashboard (unchanged)
        └─────────────────────┘
```

All four services (`postgres`, `api`, `worker`, `nginx`) are defined in
`backend/docker-compose.prod.yml` and build from the **same**
`backend/Dockerfile` as before (untouched — its migrations-on-boot,
baked-in-embedding-model, and dynamic-port design all still apply as-is).
Only `api` and `worker` differ, by `command:`, exactly like the two Railway
services used to differ by start command.

| Service | Image/build | Published ports | Healthcheck |
|---|---|---|---|
| `nginx` | `nginx:alpine` | 80, 443 (public) | — |
| `api` | `backend/Dockerfile` | none (internal only) | `/health` |
| `worker` | `backend/Dockerfile` (same image, different command) | none | log-based only |
| `postgres` | `pgvector/pgvector:pg16` | none (internal only) | `pg_isready` |

---

## What changed vs. Railway

- **Removed**: `backend/railway.json`, `backend/railway.worker.json` (Railway
  build/deploy config — no AWS equivalent needed, Docker Compose replaces
  their job).
- **Added**: `backend/docker-compose.prod.yml`, `backend/nginx/nginx.conf`,
  `backend/.env.production.example`, `backend/scripts/backup_postgres.sh`,
  this doc.
- **Unchanged**: `backend/Dockerfile`, all of `app/`, `alembic/`,
  `scripts/run_worker.py`, `pyproject.toml`, the CI workflow. The
  application code has zero AWS-specific branches — it reads `DATABASE_URL`
  and friends from the environment exactly as it did on Railway.
- **`RAILWAY_PUBLIC_DOMAIN`**: kept as-is (no rename) — it's just an env var
  the WhatsApp connect wizard reads for display (`app/api/whatsapp.py`).
  Railway auto-injected it; on EC2 you set it by hand in `.env` to your
  domain. Leaving it blank still works (falls back to the request's own
  host).
- **New**: uvicorn now runs with `--proxy-headers
  --forwarded-allow-ips='*'` (set in `docker-compose.prod.yml`'s `api`
  command) because Nginx is a new hop in front of it that didn't exist on
  Railway's edge. Without this, `request.client.host` — and therefore the
  IP-scoped rate limit on business creation (`app/core/rate_limit.py`) —
  would see Nginx's container IP for every request. Safe here because
  uvicorn's port is never published to the host; Nginx is the only thing
  that can reach it.

---

## Environment variables

Full annotated list: `backend/.env.production.example` — copy it to
`backend/.env` on the instance and fill in real values (same `.gitignore`
protection as `.env.example`: never commit the filled-in `.env`).

Three variables are new/different from the Railway setup:

| Variable | Purpose |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Configure the containerized Postgres. `DATABASE_URL` must be built from these same values, pointing at `postgres:5432` (the Compose service name) — Railway used to inject `DATABASE_URL` automatically; now you construct it yourself once. |
| `API_DOMAIN` | Read only by the `nginx` service — the domain Certbot issues the cert for and Nginx serves. |

Every other variable (`WHATSAPP_*`, `LLM_PROVIDER`, `CLERK_*`,
`CALENDAR_ENCRYPTION_KEY`, `FRONTEND_URL`, `SENTRY_DSN`,
`USE_TRANSACTIONAL_OUTBOX`, etc.) is unchanged from
`documentation/DEPLOYMENT.md`'s Appendix — same names, same production
requirements, same `_reject_insecure_production_secrets` boot guard in
`app/core/config.py`. Set them once in `backend/.env`; both `api` and
`worker` read the same file (`env_file: .env` in the compose file), so there
is no risk of the two services drifting out of sync the way two separate
Railway services' Variables tabs could.

**`CLERK_JWKS_URL` / `CLERK_ISSUER` — must come from a Clerk *production*
instance, not the default Development one.** Clerk creates every
application in Development mode first; its keys/URLs are real and
functional, so nothing fails at signup or at the boot guard above if you
copy them by mistake (this has happened in production before — see
`documentation/DEPLOYMENT.md`'s Appendix). Development instances are served
from a shared `*.clerk.accounts.dev` domain and have strict request-rate
limits not meant for real traffic; a production instance needs its own
custom domain (Clerk dashboard → your app → Production). The backend logs a
warning at startup (`app/main.py::_warn_if_clerk_looks_like_a_dev_instance`)
if `CLERK_JWKS_URL` still looks like a `*.clerk.accounts.dev` domain with
`ENVIRONMENT=production` — check `docker compose logs api` after first
deploy and treat that warning as a real, actionable misconfiguration, not
noise. **This is an operational fix (point `CLERK_JWKS_URL`/`CLERK_ISSUER`
at your production Clerk instance), not a code change** — the warning
itself is the backend correctly doing its job; do not silence or remove it.

---

## Fresh Ubuntu EC2 instance: full deploy

### 1. Launch the instance

- Ubuntu 24.04 LTS, **t3.small** to start (2 vCPU / 2 GB — tight running
  Postgres + API + worker + the baked-in ~130 MB embedding model; watch
  memory on first real traffic and move to **t3.medium** if you see
  pressure).
- Allocate an **Elastic IP** and associate it with the instance, so the IP
  survives a stop/start (a plain public IP does not).
- Security group: inbound **22** (SSH, restrict to your IP, not
  `0.0.0.0/0`), **80** and **443** (public, `0.0.0.0/0`). No other inbound
  ports — Postgres and the API's port 8000 are never published to the host,
  so they're unreachable from outside even without a rule blocking them
  explicitly.

### 2. DNS

Point `API_DOMAIN`'s A record at the Elastic IP now — Certbot's HTTP-01
challenge (step 6) needs it resolving correctly before it can issue a
certificate.

### 3. Install Docker

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER   # log out/in for this to take effect
```

Docker's own daemon is enabled to start on boot by the package install
(`systemctl is-enabled docker` should already show `enabled`) — combined
with every service's `restart: always` in `docker-compose.prod.yml`, this is
what makes all four containers come back up automatically after an instance
reboot, with no separate systemd unit needed.

### 4. Get the code and configure

```bash
git clone <your-repo-url> hira
cd hira/backend
cp .env.production.example .env
chmod 600 .env
nano .env   # fill in every value — see the Environment variables section above
```

### 5. Bring up Postgres, then bootstrap TLS with a dummy cert

Nginx's 443 server block fails to start at all if the cert files it
references don't exist — a fresh `certbot_certs` volume has nothing in it
yet. Standard fix (the well-known nginx+certbot bootstrap pattern): write a
throwaway self-signed cert to the real path first so Nginx can start, then
replace it with a real one via Certbot's HTTP-01 **webroot** challenge
against that now-running Nginx. Both steps use the `certbot` service
(`docker-compose.prod.yml`, `profiles: ["tools"]`, so it never runs as a
long-lived container) — everything goes through the same named Docker
volumes Nginx already mounts, no reaching into Docker's internal host
filesystem paths.

```bash
docker compose -f docker-compose.prod.yml up -d postgres
docker compose -f docker-compose.prod.yml ps   # wait for postgres to show "healthy"

# 1. Dummy cert so nginx's 443 server block has something to load.
export API_DOMAIN=<your-api-domain>   # matches API_DOMAIN in .env
docker compose -f docker-compose.prod.yml run --rm --entrypoint sh certbot -c "
  mkdir -p /etc/letsencrypt/live/$API_DOMAIN &&
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout /etc/letsencrypt/live/$API_DOMAIN/privkey.pem \
    -out /etc/letsencrypt/live/$API_DOMAIN/fullchain.pem \
    -subj '/CN=localhost'
"
```

### 6. Bring up everything

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

Watch `docker compose -f docker-compose.prod.yml logs -f api` for:
- `alembic upgrade head` completing (same on-every-boot migration as Railway).
- The embedding model already present (no download — baked into the image).

Nginx should now be up and serving the dummy cert (browsers will warn — expected, not fixed until the next step).

### 7. Get the real certificate

```bash
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d $API_DOMAIN --non-interactive --agree-tos -m <your-email> \
  --force-renewal

docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

`nginx -s reload` is a graceful config/cert reload (no dropped connections,
no restart) — the same command the renewal cron below uses.

### 8. Verify

```bash
curl https://$API_DOMAIN/health
# {"status": "ok"}   — now over a real, browser-trusted cert
curl https://$API_DOMAIN/health/whatsapp
# {"status": "no_traffic_yet"}
docker compose -f docker-compose.prod.yml logs worker | grep "Outbox worker starting"
```

### 9. Backups and cert renewal (cron)

```bash
crontab -e
```

```cron
# Nightly Postgres backup, 14-day retention (backend/scripts/backup_postgres.sh)
0 3 * * * cd /home/ubuntu/hira/backend && ./scripts/backup_postgres.sh >> /var/log/hira-backup.log 2>&1

# Certbot renewal check twice daily (standard practice — Certbot itself
# no-ops unless the cert is actually near expiry). webroot method means
# nginx never needs to stop; `nginx -s reload` picks up a renewed cert with
# no dropped connections.
0 */12 * * * cd /home/ubuntu/hira/backend && docker compose -f docker-compose.prod.yml run --rm certbot renew --webroot -w /var/www/certbot --quiet && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

### 10. Point the frontend at the new API

Same circular-dependency two-step as `documentation/DEPLOYMENT.md` §8: set
`FRONTEND_URL` in `backend/.env` to the real Vercel URL (redeploy), and set
Vercel's `NEXT_PUBLIC_API_BASE_URL` to `https://<API_DOMAIN>` (redeploy the
frontend). `app/main.py`'s CORS allow-list already includes
`settings.frontend_url`, so no code change is needed on either side.

### 11. Redeploying after a code change

```bash
cd hira && git pull
cd backend && docker compose -f docker-compose.prod.yml up -d --build api worker
```

(`postgres` and `nginx` are untouched by an app code change — only rebuild
them if their own config changed.)

**Why this used to 502 after every redeploy.** `docker compose up -d --build
api` recreates the `api` container, which gets a new internal IP on the
Compose network — the old container is gone, DNS-wise. `nginx.conf`'s
`proxy_pass http://api:8000` used a bare hostname, and Nginx only resolves a
bare hostname in `proxy_pass` once, when a worker process starts, then
caches that IP in memory for the rest of that worker's life. A live Nginx
worker never re-resolves `api`, so after the container above swaps under it,
Nginx keeps proxying to the dead IP of the container that no longer exists —
every request 502s until something forces Nginx to re-resolve (previously:
a manual `docker compose restart nginx`). `backend/nginx/nginx.conf` fixes
this by routing through Docker's embedded DNS resolver (`127.0.0.11`) with a
variable in `proxy_pass` (`set $upstream_api api:8000; proxy_pass
http://$upstream_api;`), which defers resolution to request time instead of
config-load time — a `resolver ... valid=10s` directive means a recreated
`api` container is picked up automatically within 10 seconds, with no
manual Nginx restart, and without touching any application code.

---

## Verification checklist (before calling the migration done)

- `docker compose -f docker-compose.prod.yml up -d` brings up all 4
  containers (`postgres`, `api`, `worker`, `nginx` — `certbot` is
  `profiles: ["tools"]` and correctly does **not** start), all healthy, on a
  fresh instance. `docker compose ps` shows `(healthy)` for `postgres`,
  `api`, and `nginx`.
- `curl https://<API_DOMAIN>/health` and `/health/whatsapp` both return 200
  over real HTTPS (valid cert, no browser warning).
- `alembic upgrade head` ran cleanly in the `api` container's logs.
- Worker log shows `Outbox worker starting worker_id=…`.
- `docker compose -f docker-compose.prod.yml stop api` then `start api` →
  confirm `worker` and `postgres` are entirely unaffected (proves the worker
  doesn't depend on the API process, matching the Railway setup where they
  were already independent services).
- Send a real WhatsApp message to the connected test number → confirm
  receipt (`/health/whatsapp`'s `last_inbound_at`) and a generated reply.
- From a fresh IP with no prior requests, hit the business-creation endpoint
  more than `RATE_LIMIT_BUSINESS_CREATION` times and confirm a 429 —
  proves `X-Forwarded-For` is wired correctly, not just that Nginx runs (a
  misconfigured proxy would make every client share Nginx's own IP and
  either always or never rate-limit, not per-real-client).
- Dashboard frontend (Vercel) signs in and loads data against the new API
  URL with no CORS errors in the browser console.
- `sudo reboot` the instance → confirm all 4 containers come back up on
  their own with no manual `docker compose up`.
- Force a renewal dry-run: `docker compose -f docker-compose.prod.yml run
  --rm certbot renew --dry-run` succeeds with no manual steps.
- Run a full backup + restore against a scratch database (see **Restoring a
  backup** below) and confirm the row counts match.
- Trigger a real error and confirm it appears in Sentry (if `SENTRY_DSN` is
  set).

---

## Restoring a Postgres backup

`backend/scripts/backup_postgres.sh` writes a plain-SQL `pg_dump`, gzipped,
to `$BACKUP_DIR` (default `/var/backups/hira-postgres`). To restore:

```bash
cd hira/backend
set -a; source .env; set +a   # exports POSTGRES_USER/POSTGRES_DB for the commands below

gunzip -c /var/backups/hira-postgres/hira-<timestamp>.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

This replays the dump's `CREATE`/`INSERT` statements into whatever database
is already there — safe for restoring into a **fresh** container (empty
database, right after `docker compose up -d postgres` on a new volume) but
will error on `CREATE TABLE`/duplicate-key conflicts if run against a
database that already has this schema populated. To restore over an
existing database instead (disaster recovery on the same instance), drop and
recreate the database first:

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE \"$POSTGRES_DB\"; CREATE DATABASE \"$POSTGRES_DB\";"
gunzip -c /var/backups/hira-postgres/hira-<timestamp>.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Then restart `api`/`worker` (`docker compose -f docker-compose.prod.yml
restart api worker`) so any in-memory state (e.g. SQLAlchemy connection
pool) picks up cleanly against the restored data.

---

## Rollback

The Railway deployment is not touched by this migration — it keeps running
throughout the cutover. Rolling back is:

1. Point DNS / `NEXT_PUBLIC_API_BASE_URL` back at the Railway domain.
2. Redeploy the Vercel frontend with that env var.
3. Leave the EC2 instance running (or stop it) until the AWS-side issue is
   diagnosed — no rush, since traffic is back on Railway.

**Do not run both deployments as the source of truth simultaneously** —
they'd have two diverging Postgres databases with no sync between them. Cut
over once (§10 above), verify, and only decommission Railway after the AWS
deployment has been stable under real traffic for a period you're
comfortable with.

If a bad deploy on **AWS itself** needs undoing (not a full rollback to
Railway): the same forward-fix-first logic from `documentation/DEPLOYMENT.md`
§10 applies — `alembic upgrade head` runs on every `api` container start, so
an image/commit rollback that leaves the database ahead of what the older
code expects has the same migration-mismatch risk described there. Prefer
`git revert` + redeploy (§11 above) over trying to run an older container
against a newer schema. If the bad deploy shipped a migration, restore the
pre-migration backup (**Restoring a Postgres backup** above) rather than
attempting an `alembic downgrade` against a container image that may no
longer have the matching migration file.
