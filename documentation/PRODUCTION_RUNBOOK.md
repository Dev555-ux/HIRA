# HIRA Production Operations Runbook

Status: written 2026-09-12, from documented architecture ([DEPLOYMENT_AWS.md](DEPLOYMENT_AWS.md),
`backend/docker-compose.prod.yml`, `backend/app/core/config.py`) and external
black-box verification (DNS/HTTP/TLS against `stoneveil.in` / `api.stoneveil.in`).
**Commands in this document have not been executed against the live instance**
(no SSH/SSM access was available when this was written) — treat "expected
output" as what the architecture defines/implies, not a live-captured transcript.
Verify the first real run of each section and correct this doc if reality
differs (see [DEPLOYMENT_AWS.md](DEPLOYMENT_AWS.md) for the deploy history this
runbook assumes).

**Related documentation**: [DEPLOYMENT_AWS.md](DEPLOYMENT_AWS.md) (how this
deployment was set up) · [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)
(pre-launch readiness audit) · [PRODUCTION_HEALTH_CHECKLIST.md](PRODUCTION_HEALTH_CHECKLIST.md)
(the 5-minute post-deploy version of this document).

**Scope**: one Ubuntu EC2 instance running `docker-compose.prod.yml`
(`postgres`, `api`, `worker`, `nginx`, + on-demand `certbot`), fronting
`api.stoneveil.in`, paired with a Vercel-hosted Next.js frontend at
`stoneveil.in` (out of scope for most of this doc — Vercel manages its own
TLS/hosting; see the one Frontend-specific note in Deployment Verification).

**Conventions used below**: run everything from `~/hira/backend` on the
instance unless noted. `$POSTGRES_USER`/`$POSTGRES_DB` come from `.env`
(`set -a; source .env; set +a` once per session). Every command here is
read-only except the Restore Verification section, which creates and drops
its own temporary database and never touches `hira` itself.

---

## Table of contents

1. [SSL Verification](#1-ssl-verification)
2. [SSL Renewal Verification](#2-ssl-renewal-verification)
3. [PostgreSQL Backup Verification](#3-postgresql-backup-verification)
4. [Restore Verification](#4-restore-verification)
5. [Worker Health](#5-worker-health)
6. [Docker Health](#6-docker-health)
7. [Nginx Health](#7-nginx-health)
8. [Disk Usage](#8-disk-usage)
9. [Memory Usage](#9-memory-usage)
10. [CPU Usage](#10-cpu-usage)
11. [Log Inspection](#11-log-inspection)
12. [Application Health](#12-application-health)
13. [WhatsApp Webhook Health](#13-whatsapp-webhook-health)
14. [Clerk Health](#14-clerk-health)
15. [Deployment Verification](#15-deployment-verification)
16. [Rollback Procedure](#16-rollback-procedure)

---

## 1. SSL Verification

**Purpose**: confirm the certificate currently being served is valid, matches
the domain, and isn't near expiry — this is the fastest external signal that
TLS is healthy, checkable with zero instance access.

**Exact commands**:
```bash
# From ANY machine, not just the instance:
echo | openssl s_client -servername api.stoneveil.in -connect api.stoneveil.in:443 2>/dev/null \
  | openssl x509 -noout -dates -issuer -subject

curl -sSI https://api.stoneveil.in/health
```

**Expected successful output**:
```
notBefore=<date roughly 90 days before notAfter>
notAfter=<date at least 10-14 days in the future>
issuer=C=US, O=Let's Encrypt, CN=<R or E series intermediate>
subject=CN=api.stoneveil.in

HTTP/2 200
...
```

**Warning signs**:
- `notAfter` less than 14 days out — renewal should already have fired (see §2) and hasn't yet been confirmed.
- `issuer` shows a self-signed/`CN=localhost` subject — this is the *dummy* bootstrap cert from `DEPLOYMENT_AWS.md` §5, meaning the real Certbot issuance (§7) never completed or a fresh instance was rebuilt without re-running it.
- Browser/`curl` TLS warning without `-k` — cert doesn't match `api.stoneveil.in` or chain is broken.

**Failure conditions**:
- `notAfter` in the past — outage in progress, every client rejects the connection.
- `curl` fails to connect on 443 at all — nginx down or cert file missing/corrupt (nginx's 443 server block won't start without files at the referenced path).

**Recovery steps**:
1. If the cert is the dummy self-signed one: re-run `DEPLOYMENT_AWS.md` §7 (`certbot certonly --webroot ...` then `nginx -s reload`).
2. If expired outright: run `docker compose -f docker-compose.prod.yml run --rm certbot renew --webroot -w /var/www/certbot --force-renewal` then `docker compose -f docker-compose.prod.yml exec nginx nginx -s reload`. This is a **graceful reload**, not a restart — no dropped connections.
3. If nginx won't start at all: check `docker compose -f docker-compose.prod.yml logs nginx` for the exact missing-file error before touching certs further.

---

## 2. SSL Renewal Verification

**Purpose**: confirm the *automatic* renewal path (not just the current
cert) actually works — a cert that's valid today but has no working renewal
job will silently expire in ~90 days with no warning.

**Exact commands**:
```bash
cd ~/hira/backend

# Confirm certbot is present and runnable
docker compose -f docker-compose.prod.yml run --rm --entrypoint sh certbot -c "certbot --version"

# Confirm the renewal cron line exists (per DEPLOYMENT_AWS.md §9)
crontab -l | grep -i certbot
sudo crontab -l -u root 2>&1 | grep -i certbot   # in case it was installed under root instead

# Confirm certbot's own renewal config is present for this domain
docker compose -f docker-compose.prod.yml run --rm --entrypoint sh certbot -c \
  "cat /etc/letsencrypt/renewal/api.stoneveil.in.conf"

# The actual test that matters: does a renewal attempt succeed end-to-end?
docker compose -f docker-compose.prod.yml run --rm certbot renew --dry-run

# Evidence the cron has actually fired before (not just that the line exists)
sudo grep -i certbot /var/log/syslog 2>&1 | tail -20
```

**Expected successful output**:
- `certbot --version` → `certbot 2.x.x` or similar, no error.
- `crontab -l` → a line matching:
  ```
  0 */12 * * * cd /home/ubuntu/hira/backend && docker compose -f docker-compose.prod.yml run --rm certbot renew --webroot -w /var/www/certbot --quiet && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
  ```
- `renewal/api.stoneveil.in.conf` → shows `webroot_path = /var/www/certbot,` and `authenticator = webroot`.
- `renew --dry-run` → ends with:
  ```
  Congratulations, all simulated renewals succeeded:
    /etc/letsencrypt/live/api.stoneveil.in/fullchain.pem (success)
  ```
- syslog → periodic `CRON` entries invoking the renewal command, roughly every 12 hours, most of them no-ops (Certbot itself skips renewal unless within its renewal window, typically the last 30 days before expiry).

**Warning signs**:
- Cron line exists but syslog shows **no** corresponding `CRON` invocations — the cron *daemon* isn't picking it up (check `systemctl status cron`).
- `renewal/*.conf` missing or references a different webroot/authenticator than the compose file's volumes — a config drift that will make a real renewal fail even though `--dry-run` might still pass against stale state.
- Dry-run succeeds but the real cert (§1) is within 14 days of expiry anyway — the cron *works* but isn't *scheduled to have fired yet*; check the last actual renewal timestamp inside `/etc/letsencrypt/renewal/`'s file mtime.

**Failure conditions**:
- No cron line found anywhere (user or root) — renewal has never been automated; the current cert will expire with zero warning.
- `renew --dry-run` fails — read the error carefully; the most common cause is the webroot challenge failing because `/var/www/certbot` isn't actually reachable at `http://api.stoneveil.in/.well-known/acme-challenge/...` (firewall, DNS, or nginx routing regression).

**Recovery steps**:
1. Missing cron line → add it exactly as shown above via `crontab -e`.
2. Cron installed but not firing → `sudo systemctl status cron` / `sudo systemctl enable --now cron`.
3. Dry-run failing on the HTTP-01 challenge → confirm `curl http://api.stoneveil.in/.well-known/acme-challenge/test` reaches nginx (not blocked at the security-group level — port 80 must stay open, not just 443) and that `certbot_www` volume is correctly mounted read-write for `certbot`, read-only for `nginx`.
4. After any fix, re-run `renew --dry-run` until it reports success before considering this closed.

---

## 3. PostgreSQL Backup Verification

**Purpose**: confirm nightly backups are actually being produced, not just
that the script exists — a script that's never been wired into cron is
indistinguishable from "we have backups" until the day you need one.

**Exact commands**:
```bash
cd ~/hira/backend
set -a; source .env; set +a

# Confirm the cron line exists
crontab -l | grep -i backup

# Confirm the script itself
ls -la scripts/backup_postgres.sh

# List actual backup files, newest first
ls -lat /var/backups/hira-postgres/

# Confirm retention is trimming old files (should be <= 14 files/days' worth per DEPLOYMENT_AWS.md)
ls /var/backups/hira-postgres/ | wc -l

# Check the backup log for the most recent run
tail -n 60 /var/log/hira-backup.log
```

**Expected successful output**:
- `crontab -l` → `0 3 * * * cd /home/ubuntu/hira/backend && ./scripts/backup_postgres.sh >> /var/log/hira-backup.log 2>&1`
- `ls -lat` → a file named like `hira-2026-09-12T03-00-00.sql.gz` (or similar timestamp format the script uses) dated **last night**, non-zero size (expect low tens of MB at current beta scale, growing over time — a sudden 0-byte file is the clearest failure signal).
- File count ≤ retention window (14, per the script's own gzip+retention design) — an ever-growing count means retention pruning isn't running.
- Backup log → `pg_dump` completing with no `error` lines, most recent entry timestamped within the last 24 hours.

**Warning signs**:
- Newest backup file is more than ~26 hours old — one run was silently skipped.
- Backup file size is drastically smaller than the previous night's (e.g. 40MB → 40KB) — possible partial/failed dump that still exited 0.
- Backup log shows `pg_dump: error:` anywhere, even if a file was still produced — a truncated or corrupt dump can still leave a non-empty `.gz` on disk.

**Failure conditions**:
- No files in `/var/backups/hira-postgres/` at all — backups have never run.
- Cron line missing — same root cause, the script was written but never scheduled.
- Every recent backup log entry shows connection errors — `DATABASE_URL`/credentials the script uses may have drifted from what `api`/`worker` use.

**Recovery steps**:
1. Missing cron line → add it via `crontab -e` exactly as documented.
2. Run the script manually once to confirm it works standalone: `./scripts/backup_postgres.sh` (writes to the same `$BACKUP_DIR`, safe to run anytime — it only reads from Postgres).
3. If `pg_dump` errors on connection, confirm the script's DB connection matches `.env`'s `POSTGRES_USER`/`POSTGRES_DB`/`DATABASE_URL` — re-check after any credential rotation.
4. Once a manual run succeeds, let the next scheduled 03:00 run confirm the cron path independently before closing this out.

---

## 4. Restore Verification

**Purpose**: a backup file proves nothing by itself — the only real proof a
backup is usable is restoring it and checking the data. This must happen
against a **throwaway database**, never the live `hira` database.

**Exact commands**:
```bash
cd ~/hira/backend
set -a; source .env; set +a

LATEST_BACKUP=$(ls -t /var/backups/hira-postgres/*.sql.gz | head -1)
echo "Using: $LATEST_BACKUP"

# 1. Create a temporary database — isolated from `hira`
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE hira_restore_test;"

# 2. Restore into it
gunzip -c "$LATEST_BACKUP" | docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d hira_restore_test

# 3. Confirm schema loaded
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d hira_restore_test -c "\dt"

# 4. Row counts per table, without needing to hardcode table names
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d hira_restore_test -tAc \
  "SELECT tablename FROM pg_tables WHERE schemaname='public'" | while read -r t; do
    c=$(docker compose -f docker-compose.prod.yml exec -T postgres psql -U "$POSTGRES_USER" -d hira_restore_test -tAc "SELECT count(*) FROM \"$t\"")
    echo "$t: $c"
done

# 5. ALWAYS clean up — drop the temp database
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE hira_restore_test;"

# 6. Confirm cleanup (should print nothing)
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d postgres -c "\l" | grep hira_restore_test
```

**Expected successful output**:
- Step 1: `CREATE DATABASE`
- Step 2: a long stream of `CREATE TABLE`/`ALTER TABLE`/`COPY N` lines, no `ERROR`.
- Step 3: `\dt` lists every application table (`businesses`, `customers`, `conversations`, `messages`, `leads`, `appointments`, `kb_entries`, `job_outbox`, etc.).
- Step 4: every table shows a row count ≥ 0; the core tables (`businesses`, `customers`, `conversations`, `messages`) show counts consistent with real usage (non-zero, roughly matching what `/health/whatsapp`'s traffic history implies).
- Step 5/6: `DROP DATABASE`, then no output — the temp database is gone.

**Warning signs**:
- Step 2 shows scattered `ERROR: relation already exists` — usually harmless if restoring into a genuinely empty fresh database (shouldn't happen here since `hira_restore_test` is freshly created), but investigate if seen.
- Row counts are all `0` — the dump may have captured schema only, not data (check the backup script's `pg_dump` flags for `--schema-only` accidentally set).
- `pg_dump`'s captured row counts are drastically lower than expected for a mature deployment — possible partial/truncated backup.

**Failure conditions**:
- Step 2 fails outright (`ERROR` that aborts the restore) — the backup file itself may be corrupt; try the second-most-recent backup to isolate whether it's this one file or systemic.
- `\dt` shows no tables at all — restore silently no-op'd, often from piping into the wrong database name.

**Recovery steps**:
1. If one backup file is bad, test the previous night's — if that restores cleanly, the problem is a one-off, not systemic; still investigate why.
2. If **no** recent backup restores cleanly, treat this as a P0: this deployment currently has no verified disaster-recovery path. Fix the backup script/cron first (§3), then re-run this section end to end.
3. **Never skip step 5.** An orphaned `hira_restore_test` database left behind just wastes disk — drop it before ending the session even if an earlier step failed.

---

## 5. Worker Health

**Purpose**: the outbox worker has no HTTP port and no healthcheck the
orchestrator enforces — its health is only visible through logs and the
downstream symptom (drafts stop appearing in the Inbox). This section makes
that observable directly instead of waiting for a business owner to notice.

**Exact commands**:
```bash
cd ~/hira/backend

docker compose -f docker-compose.prod.yml ps worker

# Startup confirmation
docker compose -f docker-compose.prod.yml logs worker | grep "Outbox worker starting"

# Recent activity — should show a steady trickle if there's real traffic
docker compose -f docker-compose.prod.yml logs --tail=200 worker | grep -iE "job claimed|job completed|retry scheduled|dead-lettered|zombie recovered"

# Any errors/crashes
docker compose -f docker-compose.prod.yml logs --tail=500 worker | grep -iE "error|exception|traceback"
```

**Expected successful output**:
- `ps worker` → `Up <duration>` (no explicit health column since the worker declares no healthcheck — "Up" with no restart-loop is the signal).
- `Outbox worker starting worker_id=...` present once per container lifetime (once per deploy/restart, not repeating in a loop).
- `job claimed` / `job completed` lines present and increasing over time if there's real WhatsApp traffic; absent entirely is *expected* during genuinely quiet periods, not itself a failure.
- No `error`/`exception`/`traceback` lines, or only isolated ones followed by a successful retry.

**Warning signs**:
- Repeated `Outbox worker starting` lines close together — the container is crash-looping (Docker's `restart: always` keeps bringing it back, masking the underlying crash).
- `retry scheduled` lines for the same job repeating many times — a systematically failing handler (bad LLM key, DB permission issue) rather than a transient blip.
- `dead-lettered` entries accumulating — jobs are exhausting retries; check `GET /api/v1/founder_ops/jobs` for the actual failure reason.

**Failure conditions**:
- `ps worker` shows the container missing entirely, or repeatedly `Restarting`.
- No `job claimed` lines ever, despite confirmed real inbound WhatsApp traffic (`/health/whatsapp`'s `last_inbound_at` is recent) — jobs are enqueuing but nothing is consuming them; check `USE_TRANSACTIONAL_OUTBOX=true` is actually set on **both** `api` and `worker`.

**Recovery steps**:
1. Crash-looping → `docker compose -f docker-compose.prod.yml logs worker --tail=100` for the actual exception right before the last "Outbox worker starting" — fix the root cause (usually a bad env var or a DB connectivity issue), then `docker compose -f docker-compose.prod.yml restart worker`.
2. Jobs enqueuing but not processing → confirm `USE_TRANSACTIONAL_OUTBOX=true` in `.env` on both services; if it was flipped to `false` as an emergency kill-switch (`DEPLOYMENT_AWS.md`'s rollback section) and forgotten, that's expected — flip back once ready.
3. Systematic dead-lettering → check Founder Ops (`/api/v1/founder_ops/jobs`) for the specific error, fix (commonly an expired/rotated LLM API key), then jobs already dead-lettered can be manually retried from that same endpoint.

---

## 6. Docker Health

**Purpose**: the single fastest "is everything up" check across all four
services at once.

**Exact commands**:
```bash
cd ~/hira/backend
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml top
docker system df
```

**Expected successful output**:
```
NAME       IMAGE                  STATUS                 PORTS
postgres   pgvector/pgvector:pg16 Up X (healthy)
api        hira-backend:latest    Up X (healthy)
worker     hira-backend:latest    Up X
nginx      nginx:alpine           Up X (healthy)
```
(`certbot` does **not** appear — it's `profiles: ["tools"]`, correctly absent from the default `up -d` set; seeing it running would itself be unusual, not a good sign, since it should only ever run on-demand.)

**Warning signs**:
- Any service `Up` for only a few minutes when the instance itself has been up much longer — indicates recent restarts, check `docker compose logs <service>` around that time.
- `docker system df` showing reclaimable space growing unboundedly (old images/build cache from repeated `--build` deploys never pruned).

**Failure conditions**:
- Any of `postgres`/`api`/`nginx` showing `(unhealthy)` — their healthchecks are failing even though the process is technically running.
- Any service showing `Restarting` — actively crash-looping right now.
- A service missing from the list entirely.

**Recovery steps**:
1. `(unhealthy)` on `postgres` → `docker compose -f docker-compose.prod.yml logs postgres`; usually disk-full or a corrupted data volume.
2. `(unhealthy)` on `api` → `docker compose -f docker-compose.prod.yml logs api`; check for the SEC-1 boot-guard `ValueError` naming a specific bad env var, or a DB connectivity failure blocking `alembic upgrade head`.
3. `(unhealthy)` on `nginx` → confirm the cert files it references still exist (`docker compose exec nginx ls /etc/letsencrypt/live/api.stoneveil.in/`) — a wiped `certbot_certs` volume without re-bootstrapping (§1's dummy-cert step) is the classic cause.
4. Reclaimable space growing → `docker image prune -f` (safe: only removes untagged/dangling images, never a running container's image).

---

## 7. Nginx Health

**Purpose**: nginx is the only service exposed to the internet — everything
else being healthy is moot if nginx itself can't route to it.

**Exact commands**:
```bash
cd ~/hira/backend

docker compose -f docker-compose.prod.yml ps nginx

# The healthcheck's own endpoint
curl -sS http://127.0.0.1/nginx-health

# Confirm it actually proxies through to the API (not just serving its own static health route)
curl -sS https://api.stoneveil.in/health

docker compose -f docker-compose.prod.yml logs --tail=50 nginx
```

**Expected successful output**:
- `ps nginx` → `Up (healthy)`.
- `nginx-health` → `200 OK`, minimal body (this route is nginx answering directly, not proxied — see `nginx.conf`).
- `https://api.stoneveil.in/health` → `{"status":"ok"}`, proving the full path (client → nginx → `api` container) works, not just that nginx itself is alive.
- Logs show normal access-log lines, no repeated `upstream timed out`/`connect() failed` errors.

**Warning signs**:
- `nginx-health` succeeds but `https://api.stoneveil.in/health` fails or times out — nginx is up but can't reach `api`; check whether `api` was just redeployed (`docker compose up -d --build api`) — `nginx.conf`'s dynamic-resolver fix should pick up the new container IP within ~10s, but a persistent failure past that window means something else is wrong.
- Logs show `upstream sent too big header` or similar — usually unrelated to health, but worth investigating if it correlates with real user-facing errors.

**Failure conditions**:
- 502/504 on `https://api.stoneveil.in/health` — `api` container is down, crash-looping, or nginx's resolver genuinely can't reach it.
- nginx container itself not running — total outage for the backend API (frontend on Vercel is unaffected but every API call from it will fail).

**Recovery steps**:
1. 502 right after an `api` redeploy that persists past 10-15 seconds → `docker compose -f docker-compose.prod.yml restart nginx` as a last resort (the dynamic resolver should make this unnecessary, per `DEPLOYMENT_AWS.md`'s own documented fix — a persistent 502 means investigate before assuming a restart is the real fix).
2. nginx container down entirely → `docker compose -f docker-compose.prod.yml up -d nginx`; check logs immediately after for why it exited.
3. Cert-related startup failure → see §1's recovery steps.

---

## 8. Disk Usage

**Purpose**: Postgres data, Docker images/logs, and backup files all
accumulate on one instance with no auto-scaling — disk exhaustion is the
single most common "boring" cause of a self-hosted single-instance outage.

**Exact commands**:
```bash
df -h /
docker system df -v
du -sh /var/lib/docker/volumes/*/_data 2>/dev/null
du -sh /var/backups/hira-postgres/
sudo du -sh /var/log/*.log 2>/dev/null
```

**Expected successful output**: root filesystem comfortably under ~70% used;
no single directory an unexplained majority of disk; backup directory
bounded by the retention policy (§3).

**Warning signs**: root filesystem above 80% used; Docker's reclaimable
image/build-cache space (`docker system df`'s RECLAIMABLE column) growing
release over release with no pruning.

**Failure conditions**: root filesystem above ~90-95% — Postgres writes and
new backups can start failing outright; a full disk on the volume backing
`postgres_data` can corrupt in-flight writes.

**Recovery steps**:
1. `docker image prune -f` (safe — dangling images only) and, if truly needed, `docker builder prune -f` (clears build cache; only cost is slower next build).
2. Check `/var/backups/hira-postgres/` isn't retaining more than the script's own 14-day policy intends — if the retention logic itself is broken, fix the script rather than manually deleting backups under pressure.
3. If Postgres's own volume is the growth driver, that's a real data-growth signal, not a cleanup problem — plan a disk resize (EBS volume expand + filesystem grow, no downtime with `resize2fs`/`xfs_growfs` on most setups) rather than deleting anything from a live database volume.

---

## 9. Memory Usage

**Purpose**: `DEPLOYMENT_AWS.md` explicitly flags `t3.small` (2GB) as "tight"
running Postgres + API + worker + a baked-in ~130MB embedding model — this
is the most likely resource to become the actual bottleneck first.

**Exact commands**:
```bash
free -h
docker stats --no-stream
```

**Expected successful output**: `free -h`'s "available" column comfortably
above zero; no single container in `docker stats` pinned near its cgroup
limit (if limits are set) or consuming a runaway, ever-growing amount over
time (a slow leak shows as steadily climbing MEM USAGE% across repeated
samples, not a snapshot symptom).

**Warning signs**: "available" memory trending down over successive days
without a matching traffic increase (possible slow leak); swap usage
non-zero (swap isn't configured by default in the runbook — its presence at
all is worth investigating, not just its size).

**Failure conditions**: OOM killer entries in `dmesg`/`journalctl` — the
kernel killed a container outright; `free -h` showing near-zero available
with visible thrashing.

**Recovery steps**:
1. Confirm which container OOM'd: `sudo dmesg | grep -i "out of memory"` names the killed process.
2. Immediate relief: `docker compose -f docker-compose.prod.yml restart <service>`.
3. If recurring: move to `t3.medium` (`DEPLOYMENT_AWS.md`'s own stated next step) — a resize requires stopping the instance, changing instance type in the EC2 console, and starting it again (the Elastic IP persists across this, per the runbook's own reasoning for allocating one).

---

## 10. CPU Usage

**Purpose**: lower-priority than memory for this workload (I/O-bound: DB
round trips, LLM API calls), but worth a quick check, especially during
embedding/RAG-heavy knowledge-base imports.

**Exact commands**:
```bash
uptime
docker stats --no-stream
top -bn1 | head -20
```

**Expected successful output**: load average roughly proportional to
vCPU count (2 on `t3.small`) under normal traffic; no single container
pinned at 100% CPU continuously.

**Warning signs**: sustained load average above vCPU count for extended
periods (not just a brief KB-import spike) — a genuine capacity signal, not
a one-off.

**Failure conditions**: load average persistently multiples of vCPU count
with visibly degraded response times on `/health` itself.

**Recovery steps**:
1. Identify the container: `docker stats --no-stream` sorted by CPU%.
2. If it's `worker` during a known KB import, this is expected and self-resolving — no action.
3. If sustained and unexplained, same remediation path as Memory Usage above (resize the instance) — CPU credits also matter on `t3` burstable instances: check `CPUCreditBalance` in CloudWatch if credit exhaustion is suspected (burstable instances throttle hard once credits run out, a very different symptom from a genuinely busy CPU).

---

## 11. Log Inspection

**Purpose**: a single place to know where every log actually lives before
you're mid-incident trying to remember.

**Exact commands**:
```bash
# Application containers — structured stdout, rotated by Docker (max 10MB x 3 files per service)
docker compose -f docker-compose.prod.yml logs --tail=100 api
docker compose -f docker-compose.prod.yml logs --tail=100 worker
docker compose -f docker-compose.prod.yml logs --tail=100 nginx
docker compose -f docker-compose.prod.yml logs --tail=100 postgres

# Cron-driven scripts, logged to plain files outside Docker
tail -n 100 /var/log/hira-backup.log

# System-level (cron firing, package/systemd events, OOM kills)
sudo tail -n 100 /var/log/syslog

# Sentry (if SENTRY_DSN is set) — not a local log, check the dashboard directly:
# https://sentry.io/organizations/<org>/issues/?project=<project>
```

**Expected successful output**: each command returns recent, readable log
lines with no gaps; `docker compose logs` never errors with "no such
service."

**Warning signs**: a service's logs stop abruptly with no corresponding
"container exited" — usually means the logging driver itself has an issue,
not the app; check `docker inspect <container> --format '{{.State}}'`.

**Failure conditions**: `docker compose logs` reports the container doesn't
exist — see Docker Health (§6) first, this is downstream of that.

**Recovery steps**: none specific to logging itself — this section is
diagnostic input for every other section above, not a thing to "fix" on its
own. If logs are rotating too fast to be useful during an incident,
temporarily raise `max-file` in `docker-compose.prod.yml` for the affected
service and `docker compose up -d <service>` to apply (no data loss, just
config reload).

---

## 12. Application Health

**Purpose**: confirm the backend's own fail-fast production guard
(`_reject_insecure_production_secrets` in `app/core/config.py`) is passing —
this single check, if the API is up at all, already proves a long list of
security-critical env vars are correctly set (see below).

**Exact commands**:
```bash
curl -sS https://api.stoneveil.in/health
curl -sS https://api.stoneveil.in/health/whatsapp
curl -sS https://api.stoneveil.in/health/instagram   # currently 404 — see note below

docker compose -f docker-compose.prod.yml logs api | grep -i "clerk" | grep -i "warn"
```

**Expected successful output**:
- `/health` → `{"status":"ok"}`.
- `/health/whatsapp` → `{"status":"ok","last_inbound_at":"<recent ISO timestamp>"}` (or `"stale"` with a timestamp older than `WEBHOOK_STALE_THRESHOLD_MINUTES` — not itself a failure if traffic has genuinely been quiet, see §13).
- `/health/instagram` → **currently returns `404 Not Found`.** This is expected today: the Instagram integration (tagged `v0.65.7-instagram-production`) has not been merged into `main`, so this route doesn't exist in the currently deployed build. Treat a 404 here as normal until that merge happens — re-verify this section's expectation once it does.
- No Clerk dev-instance warning in `api` logs (`_warn_if_clerk_looks_like_a_dev_instance`) — its *absence* is the healthy state.

**What a healthy `/health` already proves, with no further checking needed**: `ENVIRONMENT=production` is set; `CLERK_JWKS_URL`/`CLERK_ISSUER`/`CALENDAR_ENCRYPTION_KEY` are all non-empty; `LLM_PROVIDER` isn't `mock`; `ALLOW_MOCK_AUTH` isn't `true`; none of `WHATSAPP_VERIFY_TOKEN`/`WHATSAPP_APP_SECRET`/`WHATSAPP_ACCESS_TOKEN` are at their guessable dev defaults. The backend would have refused to boot otherwise (`ValueError` at startup, container crash-loops in `docker compose ps`) — so a healthy container is itself the proof, not something to separately re-derive.

**Warning signs**:
- A Clerk dev-instance warning present in the logs — `CLERK_JWKS_URL` is set (so the boot guard passes) but points at a `*.clerk.accounts.dev` domain rather than a real production instance. This is an operational fix (correct the env var), never a code change.
- `/health/whatsapp` "stale" for longer than expected given known real business usage.

**Failure conditions**:
- `/health` unreachable or non-200 — see Docker/Nginx Health (§6/§7) first; this is downstream of those.
- `/health` returns a body other than `{"status":"ok"}` — code regression, check `app/main.py`'s health route directly.

**Recovery steps**:
1. Clerk dev-instance warning → fix `CLERK_JWKS_URL`/`CLERK_ISSUER` in `.env` to the real production instance's values, `docker compose -f docker-compose.prod.yml up -d api` to pick up the change (no image rebuild needed for an env-only change, but a container recreate is still required).
2. Any boot-guard `ValueError` seen in `api` logs on a fresh deploy → the error message names the exact variable; fix it in `.env` and redeploy.

---

## 13. WhatsApp Webhook Health

**Purpose**: `/health/whatsapp` exists specifically because "the API is up"
doesn't prove real customer messages are actually arriving.

**Exact commands**:
```bash
curl -sS https://api.stoneveil.in/health/whatsapp
```

**Expected successful output**:
```json
{"status":"ok","last_inbound_at":"<timestamp within WEBHOOK_STALE_THRESHOLD_MINUTES>"}
```
or, during a genuinely quiet period:
```json
{"status":"stale","last_inbound_at":"<timestamp older than the threshold>"}
```
Both are "the check is working correctly" — `"stale"` describes real quiet
traffic, not a broken check. Distinguish this from a failure by checking
whether quiet traffic is expected right now (time of day, known low-volume
period) versus unexpected silence during a period real messages should be
arriving.

**Warning signs**: `"stale"` during a period when messages are known to be
expected (e.g. right after asking a real test contact to send one and
nothing shows up within a few minutes).

**Failure conditions**: the endpoint itself errors (500) rather than
returning a stale/ok status — a bug in the health check's own DB query, not
a traffic problem.

**Recovery steps**:
1. `"stale"` unexpectedly → send a real test WhatsApp message to the
   connected business number, then re-check within a minute. If it still
   doesn't register: verify Meta's webhook subscription is still active in
   the Meta App dashboard (Meta can silently disable a webhook after
   repeated delivery failures), and check `api` logs for signature-
   verification failures (`app/channels/whatsapp/parsing.py`) around the
   time the test message was sent.
2. If Meta shows the webhook as failing deliveries: confirm `api.stoneveil.in`
   is reachable from the public internet on 443 (not just from this
   instance) and that the cert is valid (§1) — Meta will not retry
   indefinitely against a broken endpoint.

---

## 14. Clerk Health

**Purpose**: confirm dashboard authentication is actually using the
production Clerk instance, not a development one that silently still works
today but hits Clerk's dev-tier rate limits under real load.

**Exact commands**:
```bash
# From any machine — confirms the custom Clerk domain is live
curl -sSI https://clerk.stoneveil.in | head -5

# From the browser console while on the real dashboard (not from the instance):
#   check for any "pk_test_ in production" warning logged by
#   frontend/src/components/providers.tsx

docker compose -f docker-compose.prod.yml logs api | grep -i "clerk"
```

**Expected successful output**:
- `clerk.stoneveil.in` → `200`, confirming the custom Clerk domain (a production-instance-only feature) is live and correctly pointed.
- No `pk_test_` warning in the browser console.
- No dev-instance warning in `api` logs (same check as §12).

**Warning signs**: `clerk.stoneveil.in` unreachable while `stoneveil.in`
itself is fine — DNS/CNAME drift specifically on the Clerk subdomain, or an
expired/misconfigured Clerk custom-domain setup on Clerk's own dashboard
side (not something this instance controls).

**Failure conditions**: sign-in on the real dashboard fails outright, or
succeeds but every subsequent authenticated API call 401s — token
verification mismatch between what Vercel's Clerk publishable key issues and
what the backend's `CLERK_JWKS_URL`/`CLERK_ISSUER` expect (usually: one side
points at a different Clerk instance than the other).

**Recovery steps**:
1. `clerk.stoneveil.in` unreachable → check Clerk's own dashboard (Domains
   section) for the custom domain's status; this is entirely Clerk-side,
   nothing to fix in this repo or on the EC2 instance.
2. Sign-in works but API calls 401 → confirm the frontend's
   `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (Vercel) and the backend's
   `CLERK_JWKS_URL`/`CLERK_ISSUER` (EC2 `.env`) are from the **same** Clerk
   application/instance — a mismatch here is the single most common cause
   of "login works, everything after it doesn't."

---

## 15. Deployment Verification

**Purpose**: confirm a just-completed deploy actually took effect and didn't
silently fail partway through.

**Exact commands**:
```bash
cd ~/hira

# Confirm the running code matches what you intended to deploy
git log -1 --oneline
git status --short

cd backend
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=50 api | grep -i "alembic"

curl -sS https://api.stoneveil.in/health
```

**Expected successful output**:
- `git log -1` matches the commit you intended to deploy; `git status --short` is empty (no stray local changes on the instance itself — the instance should only ever run what's in the remote repo).
- `api` logs show `alembic upgrade head` completing with no error, immediately followed by uvicorn's normal startup lines.
- `docker compose ps` shows all services `(healthy)` within `start_period` (30s for `api`).
- `/health` → `{"status":"ok"}`.

**Warning signs**: `git status --short` shows uncommitted changes on the
instance — someone edited a file directly on the box instead of through a
normal commit+deploy, meaning the next `git pull` could silently discard it
or conflict.

**Failure conditions**: `api` container fails to reach `(healthy)` within
`start_period`, or exits and restart-loops — almost always either a migration
failure or the SEC-1 boot guard rejecting something newly introduced.

**Recovery steps**:
1. Check `docker compose -f docker-compose.prod.yml logs api` for the exact
   error immediately — migration errors and boot-guard `ValueError`s are
   both self-describing.
2. If it's a bad migration: see Rollback Procedure (§16) — do **not** just
   redeploy the previous image without first considering whether the
   database itself needs downgrading.
3. If it's a bad env var newly required by the deploy: fix `.env`, then
   `docker compose -f docker-compose.prod.yml up -d api worker` (no rebuild
   needed for an env-only fix).
4. Frontend (Vercel): confirm the new deploy actually promoted to
   Production in the Vercel dashboard (a build can succeed but not auto-
   promote depending on project settings) and that its build log shows no
   errors.

---

## 16. Rollback Procedure

**Purpose**: the one fact that shapes this entire section, from
`DEPLOYMENT_AWS.md`: `alembic upgrade head` runs on **every** `api`
container start, including a rollback. An older image has no knowledge of a
migration applied after it was built — if the database has moved past what
an older image recognizes, that image's `alembic upgrade head` can't
resolve the revision and the container won't boot. **Rollback here is not
"just redeploy the previous image."**

**Decision tree**:

1. **Prefer forward-fix over rollback whenever possible.** Push a new commit
   that fixes the problem and deploy that. This sidesteps the
   migration-mismatch risk entirely and is almost always faster than
   coordinating an image+database rollback.
   ```bash
   cd ~/hira && git pull
   cd backend && docker compose -f docker-compose.prod.yml up -d --build api worker
   ```

2. **A plain image rollback is safe only if the bad deploy shipped no new
   file under `backend/alembic/versions/`** — a pure config/env-var mistake
   or an app-logic bug with no schema change. In that case:
   ```bash
   git checkout <previous-good-commit>   # or: git revert <bad-commit>
   docker compose -f docker-compose.prod.yml up -d --build api worker
   ```

3. **If the bad deploy included a migration**, downgrade the database
   *before* rolling back the image:
   ```bash
   # Identify the previous head (the bad migration's own down_revision, or
   # from `alembic history` locally)
   docker compose -f docker-compose.prod.yml exec api alembic downgrade <previous-revision>
   # Only then roll back the image
   git checkout <previous-good-commit>
   docker compose -f docker-compose.prod.yml up -d --build api worker
   ```
   Skipping the downgrade is exactly the failure mode this whole section
   exists to prevent: the older image boots, tries `alembic upgrade head`,
   can't recognize the newer revision already stamped in the database, and
   the container never starts.

**Outbox kill-switch (fastest mitigation, no redeploy at all)**: if AI
replies are misbehaving but the API itself is healthy, set
`USE_TRANSACTIONAL_OUTBOX=false` in `.env` and
`docker compose -f docker-compose.prod.yml up -d api worker` — reverts to
in-process reply generation instantly, no code rollback needed. Already-
`pending` jobs are harmlessly drained by the worker; flip back to `true`
once the underlying issue is fixed.

**Frontend rollback (Vercel)**: always safe, no schema coupling — Vercel
dashboard → Deployments → select the previous good deployment → "Promote to
Production." Instant. The frontend degrades gracefully against a
slightly-behind or slightly-ahead API version (review metadata is optional
in its data model), so a brief frontend/backend version skew during a
rollback is expected to be harmless, not itself a thing to rush.

**After any rollback — do not skip**:
1. Re-run the Deployment Verification checklist (§15) against the
   rolled-back state.
2. Re-run the full smoke-test path from `DEPLOYMENT_AWS.md`'s verification
   checklist before considering the incident closed.
3. Once the real forward fix ships, the next normal deploy's
   `alembic upgrade head` brings the database back to the latest schema
   automatically — no special handling needed on the way back up.

---

## Appendix: quick command index

| Need to check... | Section |
|---|---|
| Is the cert about to expire? | §1 |
| Will the cert auto-renew? | §2 |
| Do backups actually exist? | §3 |
| Can we actually restore one? | §4 |
| Is the AI reply pipeline alive? | §5 |
| Is everything up, in one glance? | §6 |
| Can traffic actually reach the API? | §7 |
| Are we about to run out of disk? | §8 / §9 / §10 |
| Where do I even look for logs? | §11 |
| Is production correctly configured? | §12 |
| Is WhatsApp actually receiving messages? | §13 |
| Is auth pointed at the right Clerk instance? | §14 |
| Did the last deploy actually work? | §15 |
| Something's broken, how do I get back? | §16 |
