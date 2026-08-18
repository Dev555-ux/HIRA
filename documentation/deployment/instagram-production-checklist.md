# Instagram Production Checklist

Status: written Sprint 65 PR 7 (production hardening/release readiness). This is a checklist to execute before/during a real deployment that enables Instagram, not a design doc — see `documentation/INSTAGRAM_INTEGRATION.md` for the "why"/"how" behind each item, `documentation/architecture/messaging-platform.md` for the underlying architecture, and `documentation/DEPLOYMENT.md`/`documentation/DEPLOYMENT_AWS.md` for the platform-wide deploy runbook this supplements (not replaces).

**Nothing in this checklist has been executed against real Meta credentials as part of this PR** — no Meta Developer App, no live OAuth, no live webhook delivery was available in this environment. Every box below is what to verify, not a claim that it passed. See the Production Readiness Report for the explicit list of what could/couldn't be verified here.

---

## Meta

- [ ] **Meta App configured** — the App has the Instagram product added ("Instagram API with Facebook Login for Business"). See `INSTAGRAM_INTEGRATION.md` §2.
- [ ] **Redirect URI** registered on the App exactly matches the deployed `INSTAGRAM_OAUTH_REDIRECT_URI` (e.g. `https://<api-domain>/api/v1/instagram/oauth/callback`) — a mismatch fails OAuth with an opaque Meta error, not a HIRA-side one.
- [ ] **Webhook URL** configured: `https://<api-domain>/webhooks/instagram`, subscribed to the **messages** field.
- [ ] **Verify token** entered in Meta's webhook config matches the deployed `INSTAGRAM_VERIFY_TOKEN` exactly (case-sensitive, no trailing whitespace).
- [ ] **Permissions** available to the App: `instagram_basic`, `instagram_manage_messages`, `pages_show_list`, `pages_read_engagement`, `pages_manage_metadata` (`app/instagram/oauth.py::SCOPES`).
- [ ] **App Review** status confirmed and understood: Development Mode is enough to validate this checklist against the founder's own test accounts; reaching real third-party businesses requires Advanced Access via App Review (a Meta approval process, not a code change — see `INSTAGRAM_INTEGRATION.md` §2's App Review section). Confirm which mode this deployment is actually running in before promising real-business availability.
- [ ] **Live mode**: the App is switched from Development to Live (Meta App dashboard toggle) if serving real businesses — confirm this explicitly; a Development-mode App silently limits who can authenticate.

## HIRA

- [ ] **Environment variables** set on every service that needs them (API + Worker, per `documentation/DEPLOYMENT.md`'s Appendix): `INSTAGRAM_VERIFY_TOKEN` (not the `dev-verify-token` default — the backend now refuses to boot in production if it is, Sprint 65 PR 7), `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`, `INSTAGRAM_OAUTH_REDIRECT_URI`, `INSTAGRAM_GRAPH_VERSION`.
- [ ] **Database migration** applied: `alembic upgrade head` includes `633a0b1814ca` (Sprint 65 PR 6, `messages.media`) and every earlier Instagram-related migration (`InstagramCredential`, `InstagramOAuthAttempt`, `Conversation.channel`) — confirm via `alembic current` against the production database, not assumed from the deploy log alone.
- [ ] **Health check**: `GET /health/instagram` returns `200` with every check `true` (`registry_contains_instagram`, `provider_loads`, `credential_encryption_available`, `oauth_configured`, `webhook_signing_configured`) — a `false` on any of the last three means a config variable above is missing, not a code problem.
- [ ] **Smoke test** (see `documentation/testing/instagram-e2e.md` for the full walkthrough): connect one real test business end-to-end (OAuth → webhook verification handshake → send/receive one real text message → send/receive one real image) against the deployed environment, not just against local dev.
- [ ] **Rollback plan understood before enabling**: Instagram has no separate kill-switch env var the way `USE_TRANSACTIONAL_OUTBOX` does for the outbox — disabling it means either (a) unsubscribing the webhook in the Meta App dashboard (stops inbound delivery immediately, no redeploy), or (b) a code rollback if the problem is in the provider/messaging pipeline itself. If the bad deploy included the `633a0b1814ca` migration, follow `documentation/DEPLOYMENT.md` §10's migration-mismatch rollback procedure (downgrade the DB before rolling back the image) — do not attempt a plain image rollback past a migration boundary.

## Operations

- [ ] **Monitoring**: `SENTRY_DSN` is set (shared across every channel — no Instagram-specific Sentry project needed). Confirm a deliberately-triggered error (e.g. a temporarily wrong `INSTAGRAM_APP_SECRET`) actually shows up in Sentry before relying on it in production.
- [ ] **Logs**: confirm, against real deployed logs (not just this PR's test suite), that a signature-verification failure, an unknown-account webhook delivery, and a successful connect/disconnect each produce the expected structured log line — see `INSTAGRAM_INTEGRATION.md` §6 for exactly what each should look like and what must never appear in it (tokens, secrets, Graph API response bodies, customer message content).
- [ ] **Alerts**: no dedicated Instagram alert exists yet (unlike `GET /health/whatsapp`'s Sentry `capture_message` on staleness) — there is no Instagram traffic-staleness signal to alert on today (see `INSTAGRAM_INTEGRATION.md` §8/§9's metrics table for where one would be added if built). Until then, treat a `503` from `GET /health/instagram` and any Sentry error tagged with an Instagram-domain exception (`InstagramAuthError`, `InstagramNotConfiguredError`, `InstagramOAuthStateError`, `InstagramDuplicateConnectionError`) as page-worthy.

---

## Sign-off

This checklist is complete when every box above is checked by someone who actually executed the step against the real deployment (not inferred from code review) and the Production Readiness Report's "Known Limitations" section has been read and accepted by whoever is approving the release.
