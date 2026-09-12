# HIRA Production Health Checklist

**Run this after every deployment. Target: under 5 minutes.**
Full detail/recovery steps for any ❌ live in [PRODUCTION_RUNBOOK.md](PRODUCTION_RUNBOOK.md).

**Related documentation**: [DEPLOYMENT_AWS.md](DEPLOYMENT_AWS.md) (how this
deployment was set up) · [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)
(pre-launch readiness audit).

Run everything below from `~/hira/backend` on the EC2 instance unless marked **(external)**.

```bash
cd ~/hira/backend && set -a && source .env && set +a
```

| # | Check | Command | Pass looks like |
|---|---|---|---|
| 1 | Deployed commit is correct | `cd ~/hira && git log -1 --oneline && git status --short && cd backend` | Expected commit; empty status |
| 2 | All containers up | `docker compose -f docker-compose.prod.yml ps` | `postgres`, `api`, `nginx` → `(healthy)`; `worker` → `Up`; no `Restarting` |
| 3 | Migrations applied cleanly | `docker compose -f docker-compose.prod.yml logs --tail=30 api \| grep -i alembic` | Upgrade completes, no error, immediately followed by uvicorn startup |
| 4 | API reachable through nginx | `curl -sS https://api.stoneveil.in/health` | `{"status":"ok"}` |
| 5 | Frontend live **(external)** | `curl -sSI https://stoneveil.in` | `HTTP/2 200`, `server: Vercel` |
| 6 | WhatsApp webhook alive | `curl -sS https://api.stoneveil.in/health/whatsapp` | `"ok"` (or `"stale"` only if traffic is genuinely quiet right now) |
| 7 | No Clerk dev-instance warning | `docker compose -f docker-compose.prod.yml logs api \| grep -i clerk \| grep -i warn` | No output |
| 8 | Clerk production domain live **(external)** | `curl -sSI https://clerk.stoneveil.in \| head -1` | `HTTP/2 200` |
| 9 | Worker actually processing | `docker compose -f docker-compose.prod.yml logs --tail=100 worker \| grep -iE "job claimed\|job completed\|error\|exception"` | Activity present (or quiet if no recent traffic), no errors |
| 10 | Cert not near expiry | `echo \| openssl s_client -servername api.stoneveil.in -connect api.stoneveil.in:443 2>/dev/null \| openssl x509 -noout -dates` | `notAfter` ≥ 14 days out |
| 11 | Disk has headroom | `df -h /` | Root filesystem < 80% used |
| 12 | Memory has headroom | `free -h` | "available" comfortably above zero |

## Result

- **All 12 pass** → 🟢 Deploy verified healthy.
- **Any of #2, #3, #4, #6 fail** → 🔴 Stop. Do not consider the deploy successful. Go to `PRODUCTION_RUNBOOK.md` §6/§15/§16 (Docker Health / Deployment Verification / Rollback).
- **Only #7, #9, #10, #11, #12 flag a warning (not a hard fail)** → 🟡 Deploy is live and serving traffic; schedule a fix, don't roll back for these alone.
- **#5 or #8 fail while everything else passes** → 🟡 backend/EC2 side is fine; the issue is Vercel- or Clerk-dashboard-side, not this instance.

## If anything is 🔴

1. Do not attempt a fix improvised on the spot — go to the matching numbered
   section in `PRODUCTION_RUNBOOK.md`.
2. If the deploy itself is the cause and a quick forward-fix isn't obviously
   available, go straight to `PRODUCTION_RUNBOOK.md` §16 (Rollback
   Procedure) rather than debugging live under pressure.
3. Re-run this entire checklist after any fix or rollback before calling the
   incident closed.
