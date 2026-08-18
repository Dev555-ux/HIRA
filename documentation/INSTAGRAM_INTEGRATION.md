# Instagram Integration

Status: **Accepted** (2026-08-19, Sprint 65 PR 7). Covers OAuth (PR 2), webhooks (PR 3), Unified Inbox (PR 4), messaging (PR 5), media (PR 6), and this PR's production hardening.

This is the operational reference for HIRA's Instagram Business Messaging integration — setup, environment variables, webhook/App Review requirements, and the observability this hardening pass added. For the channel-agnostic architecture underneath it (five-layer pipeline, `ChannelProvider` contract, capability system), read `documentation/architecture/messaging-platform.md` first; this document assumes that context and only covers what's Instagram-specific. For the shape of the code itself, see `app/instagram/` (OAuth, credentials) and `app/channels/instagram/` (the `ChannelProvider` implementation).

---

## 1. How this differs from WhatsApp

The single most important operational difference: **Instagram connects every business through one HIRA-owned Meta App**, not a bring-your-own-app model like WhatsApp's self-serve flow (`documentation/WHATSAPP_INTEGRATION.md`). Concretely:

- `INSTAGRAM_APP_ID`/`INSTAGRAM_APP_SECRET`/`INSTAGRAM_VERIFY_TOKEN` are deployment-wide settings (one value for the whole HIRA platform), not something each business enters into a connect wizard.
- Every Instagram webhook delivery to HIRA's one callback URL is signed with that same shared app secret, regardless of which business it's for — the webhook route verifies the signature *before* looking up which business it belongs to (the reverse order from WhatsApp's per-business-secret flow). See `app/webhooks/instagram.py`'s module docstring.
- A business connects via Facebook Login for Business OAuth (`app/instagram/oauth.py`) against HIRA's shared App, authorizing HIRA to manage messaging for their own connected Instagram professional account.

## 2. Meta App setup (one-time, platform-level)

1. Create a Meta App at [developers.facebook.com](https://developers.facebook.com) (or reuse the existing App if WhatsApp already has one — Instagram messaging needs its own product/permission grant on top of an existing App).
2. Add the **Instagram** product ("Instagram API with Facebook Login for Business" — not the standalone "Instagram API with Instagram Login," a different auth model this codebase doesn't implement).
3. Note the **App ID** and **App Secret** (App → Settings → Basic) → `INSTAGRAM_APP_ID` / `INSTAGRAM_APP_SECRET`.
4. Configure OAuth: App → Facebook Login for Business → Settings → **Valid OAuth Redirect URIs** — add the exact deployed callback URL (`https://<api-domain>/api/v1/instagram/oauth/callback`) → `INSTAGRAM_OAUTH_REDIRECT_URI` must match this exactly.
5. Request/verify these permissions are available to the App (see `app/instagram/oauth.py::SCOPES`): `instagram_basic`, `instagram_manage_messages`, `pages_show_list`, `pages_read_engagement`, `pages_manage_metadata`.
6. Configure the webhook (App → Webhooks → Instagram → Subscribe):
   - Callback URL: `https://<api-domain>/webhooks/instagram`
   - Verify token: the same string as `INSTAGRAM_VERIFY_TOKEN`
   - Subscribe to the **messages** field.

### App Review

In Meta's **Development Mode**, the App works immediately against Pages/Instagram accounts owned by people with a role on the App (founder's own test accounts) — enough to build and validate everything in this document. Reaching real third-party businesses requires Meta **App Review** granting **Advanced Access** to `instagram_manage_messages`/`pages_messaging`-adjacent permissions. This is a Meta approval process (screenshots, a use-case description, a demo video showing the actual message flow) — a business/compliance step, not a code change; no code in this repo needs to change once Advanced Access is granted (per `app/instagram/oauth.py`'s own module docstring). Track this as a launch blocker independent of this PR's engineering scope.

## 3. Environment variables

| Variable | Meaning | Where to get it |
|---|---|---|
| `INSTAGRAM_VERIFY_TOKEN` | Arbitrary string; must match Meta's webhook config. Guarded in production (Sprint 65 PR 7): the backend refuses to boot with `ENVIRONMENT=production` if this is still the dev default. | You choose it |
| `INSTAGRAM_APP_ID` | OAuth client id | Meta App → Settings → Basic |
| `INSTAGRAM_APP_SECRET` | Verifies `X-Hub-Signature-256` on every inbound webhook; also the OAuth client secret | Meta App → Settings → Basic → App Secret |
| `INSTAGRAM_OAUTH_REDIRECT_URI` | Must exactly match a URI registered on the Meta App | You set it, matching Meta's config |
| `INSTAGRAM_GRAPH_VERSION` | Graph API version (default `v21.0`) | default |

All four are empty/default-safe outside production — a deployment can run WhatsApp-only with Instagram entirely unconfigured; `app/instagram/oauth.py::_require_configured()` raises a clear `InstagramNotConfiguredError` (mapped to `503`) the moment a connect is attempted without them, rather than failing silently. See `backend/.env.example` and `documentation/DEPLOYMENT.md`'s Appendix for the full annotated list.

**Not required in production the way `WHATSAPP_APP_SECRET` is**: `INSTAGRAM_APP_ID`/`INSTAGRAM_APP_SECRET`/`INSTAGRAM_OAUTH_REDIRECT_URI` default to empty rather than a guessable placeholder — same convention as `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` (an optional integration that fails clearly at first use, not at boot). `INSTAGRAM_VERIFY_TOKEN` is the exception: it defaults to a *guessable* value (`dev-verify-token`), so it follows `WHATSAPP_VERIFY_TOKEN`'s treatment instead — guarded by `_reject_insecure_production_secrets` (`app/core/config.py`). This distinction was a real gap until this PR: the webhook route has been live in production since Sprint 65 PR 3, but the production boot guard for its verify token was never added until now — see this doc's "Fixed this PR" section below.

## 4. Connect flow (dashboard)

A business connects via **Settings → Instagram** (or wherever the frontend surfaces it): `GET /api/v1/instagram/oauth/connect` builds a signed, single-use OAuth state and redirects to Meta's consent screen. Meta redirects back to `GET /api/v1/instagram/oauth/callback` (no Clerk session possible there — the signed `state` param authenticates the request instead). If exactly one eligible Page/Instagram account is found, it's connected immediately; if more than one, the frontend is handed an opaque `selection_token` and calls `GET /connect/choices` + `POST /connect/finalize` to let the business pick.

**Reconnect** reuses the exact same `store_credentials()` path as a first connect (create-or-replace, not a separate code path) — see `app/instagram/credentials.py`. **Disconnect** (`DELETE /disconnect`) removes only the stored credential row; it never touches `Message`/`Customer`/`Conversation` data.

## 5. Capabilities

Text (Sprint 65 PR 5) and media — image/video/audio/document (Sprint 65 PR 6). The authoritative, currently-accurate list is `InstagramProvider.capabilities()` (`app/channels/instagram/provider.py`) and `documentation/architecture/messaging-platform.md` §7 — do not trust this document if it and the code ever disagree; the code is the source of truth for what's actually implemented.

## 6. Logging conventions (Sprint 65 PR 7)

Every Instagram-domain log line (OAuth connect/callback/reconnect/disconnect, webhook verification/signature-failure/parsing-failure, send success/failure/retry) is structured (`logger.info`/`.warning` with named fields, never an f-string interpolating raw external content) and **never includes**: access tokens, refresh tokens, authorization codes, Graph API response bodies, or customer message text/media content. Business ids, Page ids, and Instagram Business Account ids are logged freely — they're not secrets and are essential for debugging "which business/account had a problem."

Fixed this PR (previously violated the rule above): `app/instagram/oauth.py::_fetch_access_token()`/`discover_connectable_pages()` built `InstagramAuthError` messages containing `resp.text` — Meta's raw error response body — which then flowed into `logger.warning()` calls in `app/api/instagram.py`. Both now build a structured `status=... code=... subcode=...` summary instead (`_meta_error_summary()`), matching the convention `app/instagram/credentials.py::check_connection_health` and `app/channels/instagram/send.py::_failed_receipt` already used. **The identical pattern still exists in `app/whatsapp/credentials.py::verify_whatsapp_credentials()`** (`f"Meta rejected these credentials: {resp.status_code} {resp.text}"`) — out of scope for this Instagram-only hardening pass, flagged here for a follow-up.

Where logging previously didn't exist at all: `app/webhooks/instagram.py` had zero log lines before this PR (every rejection was a bare `403` with nothing in the log stream to diagnose it from) — now logs signature-verification failures (distinguishing "app secret not configured" from "bad signature," without revealing which to the caller), unrecognized routing/malformed payloads, unknown-account deliveries, and successful processing counts. `disconnect_instagram()`/`start_oauth_connect()` had no logging either — both now log a structured line. **The identical webhook-logging gap exists in `app/webhooks/whatsapp.py`** — also out of scope here, also flagged for follow-up.

## 7. Metrics

**No metrics framework (Prometheus/StatsD/Datadog/etc.) exists in this codebase today** — the only operational-signal mechanism is Sentry (`app/core/monitoring.py`: `capture_exception` for unhandled exceptions, `capture_message` for a specific alert-worthy condition, first used by `GET /health/whatsapp`'s staleness check). Per this PR's own scope ("do not invent a new monitoring system"), no metrics framework was added. If/when one is adopted, these are the counters to instrument, and exactly where:

| Metric | Where to add it |
|---|---|
| Webhook requests (total) | `app/webhooks/instagram.py::receive()` — increment on entry |
| Webhook failures (by reason: bad signature / unknown account / malformed payload) | Same function, at each of the three `logger.warning()` call sites added this PR — increment alongside each log line |
| OAuth success / failure | `app/api/instagram.py::oauth_callback()` — success at the `logger.info("Instagram connected...")` call sites (both the single-choice and `finalize_connection` paths); failure at each `InstagramAuthError`/`InstagramOAuthStateError` branch |
| Send success / retry / failure | `app/services/channel_manager.py::send()` — success at `receipt.status == "sent"`, retry at the new `logger.info("Retrying...")` call site (this PR), failure at the final `return receipt`/`return DeliveryReceipt(status="failed", ...)` paths. Channel-agnostic by design — instrumenting here covers Instagram *and* WhatsApp with one counter, tagged by `message.channel`. |
| Delivery success / failure | Same `ChannelManager.send()` return paths — `DeliveryReceipt.status` is the signal |

None of these require touching `MessagingService`, `ChannelProvider`, or any DTO — every one of them is observable from a log call site that already exists after this PR's logging additions.

## 8. Health checks

`GET /health/instagram` (Sprint 65 PR 7) — configuration/wiring liveness, not a traffic check (there's no Instagram equivalent of "last inbound message age" the way `GET /health/whatsapp` has yet — see `app/main.py::health_instagram()`'s docstring for why that's a deliberately different kind of check, not an oversight). Verifies the provider is registered and loads, credential encryption is available, and OAuth/webhook signing config is present — **never calls Meta**, so it stays fast and can't itself flap. Returns `200`/`"ok"` even with Instagram entirely unconfigured (a legitimate WhatsApp-only deployment); only `503` if the provider genuinely isn't registered (a code bug, not a config choice).

```bash
curl https://<api-domain>/health/instagram
# {"status": "ok", "checks": {"registry_contains_instagram": true, "provider_loads": true,
#   "credential_encryption_available": true, "oauth_configured": true, "webhook_signing_configured": true}}
```

## 9. Failure modes and how they're handled

| Failure | Handling |
|---|---|
| Revoked credentials / expired token | `check_connection_health()` (`app/instagram/credentials.py`) classifies Meta's OAuthException codes into `needs_reconnect`/`permission_revoked`/`invalid_credentials`; surfaced via `GET /status`, polled by the dashboard. |
| Meta network outage | Every live Graph API call (`oauth.py`, `credentials.py`, `send.py`) catches `httpx.TransportError`/`RequestError` and returns/raises a classified failure — `check_connection_health()` treats it as "can't confirm, keep last-known status" (not "broken"); `send()` marks it `retryable=True` (`ChannelManager` retries, see messaging-platform.md §5). |
| Missing configuration | `_require_configured()` (oauth.py) raises `InstagramNotConfiguredError` → `503` at the API layer; never a bare 500 or silent no-op. |
| Malformed webhook | `parse_webhook()`/`extract_routing_key()` raise `WebhookVerificationFailedError` → `403`, logged (this PR), never crashes the process. |
| Duplicate webhook delivery | `MessagingService.record_inbound()` dedupes by `external_message_id` — a re-delivery is a silent no-op, not a duplicate `Message` row. |
| Duplicate/reused OAuth callback | `InstagramOAuthAttempt.consumed_at` enforces single-use; a replayed `state` raises `InstagramOAuthStateError("already used")`. |
| **Reconnect race** (two concurrent connect/reconnect requests for the same business — double-click, two tabs) | **Fixed this PR.** `store_credentials()`'s `IntegrityError` handling previously attributed *any* unique-constraint violation to "this Instagram account is already connected to a different business" — including the case where the actual conflict was the business's own `business_id` unique constraint racing with itself. Now re-queries by `business_id` on conflict: if a row for *this* business exists, it retries as the update the losing request meant to make (both concurrent requests converge on one final state); only a genuinely different business's conflicting `instagram_business_account_id` raises the duplicate-connection error. See `app/instagram/credentials.py::store_credentials()` and `tests/test_instagram_credentials.py::test_store_credentials_reconnect_race_converges_instead_of_a_false_duplicate_error`. |
| Retry exhaustion | `ChannelManager.send()` returns the last failed `DeliveryReceipt` after `DEFAULT_MAX_ATTEMPTS` (3) — `MessagingService` marks the `Message` `failed` with `ai_meta["failure_reason"]`, never leaves it stuck `sending` (see messaging-platform.md §4.2/§4.3). |

## 10. Manual test with curl

Webhook verification (GET handshake):
```bash
curl "http://localhost:8000/webhooks/instagram?hub.mode=subscribe&hub.verify_token=$INSTAGRAM_VERIFY_TOKEN&hub.challenge=12345"
# → 12345
```

Simulate an inbound text message (signature must match the raw body, and a business must already be connected with a matching `instagram_business_account_id`):
```bash
BODY='{"object":"instagram","entry":[{"id":"<IG_BUSINESS_ACCOUNT_ID>","messaging":[{"sender":{"id":"IGSID_TEST"},"recipient":{"id":"<IG_BUSINESS_ACCOUNT_ID>"},"message":{"mid":"mid.test1","text":"Are you open on Sunday?"}}]}]}'
SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$INSTAGRAM_APP_SECRET" | sed 's/^.* //')"
curl -X POST http://localhost:8000/webhooks/instagram \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIG" \
  --data "$BODY"
# → {"status":"received"}
```

Live validation beyond this (real Meta App, real OAuth round-trip, real message send/receive) requires real Meta Developer credentials — see `documentation/testing/instagram-e2e.md` for the full manual walkthrough, and `documentation/deployment/instagram-production-checklist.md` for what to verify before calling a deployment production-ready. Neither of those documents' steps have been executed against live Meta credentials as part of this PR — see this PR's own Production Readiness Report for exactly what could and couldn't be verified without them.
