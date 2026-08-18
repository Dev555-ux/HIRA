# Instagram End-to-End Manual Validation Guide

Status: written Sprint 65 PR 7. Step-by-step instructions for another engineer (or the same one, later) to manually validate the full Instagram integration against real Meta infrastructure. **No step in this document has been executed as part of this PR** — this environment has no Meta Developer credentials configured (`INSTAGRAM_APP_ID`/`INSTAGRAM_APP_SECRET` are empty, `INSTAGRAM_VERIFY_TOKEN` is at its local dev default). This is a checklist to run, not a report of what already passed — do not check a box, or claim in a PR/release note that this ran, without actually doing it.

**Prerequisites** before starting:
- A Meta Developer account with an App configured per `documentation/INSTAGRAM_INTEGRATION.md` §2 (App ID/Secret, OAuth redirect URI, webhook URL + verify token, required permissions).
- A test Facebook Page with a connected Instagram professional (Business or Creator) account, owned by (or granted a role to) the Meta Developer account above (Development Mode requirement).
- A second Instagram account (personal or another professional account) to act as "the customer" sending DMs to the test Page's Instagram account.
- HIRA running somewhere Meta's servers can reach over HTTPS (a deployed environment, or local dev tunneled via `ngrok http 8000` or similar) — Meta's webhook delivery and OAuth redirect are both real HTTP calls from Meta's infrastructure, not something a local-only server can receive.
- A HIRA business account (dashboard login) to connect Instagram to.

---

## Step 1 — OAuth

1. Log into the HIRA dashboard as the test business.
2. Navigate to the Instagram connect entry point (Settings → Instagram, or wherever the frontend surfaces `GET /api/v1/instagram/oauth/connect`).
3. Click "Connect Instagram." Confirm the browser redirects to Meta's consent screen (`facebook.com/.../dialog/oauth`), listing the permissions from `INSTAGRAM_INTEGRATION.md` §2 step 5.
4. Approve. Confirm the browser lands back on `GET /api/v1/instagram/oauth/callback` and then redirects to the frontend with `?instagram=connected` (single eligible Page) or `?instagram=choose&selection_token=...` (multiple eligible Pages — pick one, confirm the choice flow completes and also lands on `?instagram=connected`).
5. **Verify in the backend logs**: a structured `"Instagram connected for business <id> (page_id=..., ig_account_id=...)"` line — confirm no access token appears anywhere in that log line or the surrounding request log.

**Expected failure modes to also exercise, not just the happy path:**
- Deny consent on Meta's screen → confirm the frontend shows a clear error, not a blank page or a stack trace.
- Reload/revisit the OAuth callback URL with the same `state` param a second time (browser back-button) → confirm it's rejected ("already used"), not silently reprocessed.

## Step 2 — Connect account

1. Confirm `GET /api/v1/instagram/status` (or the dashboard's own status display) shows `connected: true` with the correct `instagram_username`.
2. Confirm `GET /health/instagram` shows every check `true`.

## Step 3 — Receive DM

1. From the second (customer) Instagram account, send a plain text DM to the connected professional account: "Are you open today?"
2. Confirm Meta delivers a webhook to `POST /webhooks/instagram` — check the backend logs for the `"Instagram webhook delivered N message(s), M new, for business <id>"` line (Sprint 65 PR 7 logging).
3. Query `GET /api/v1/conversations` (or the dashboard Inbox) and confirm a new conversation with `channel: "instagram"` appears, with the message body matching what was sent.

## Step 4 — Inbox

1. Open the conversation in the dashboard Inbox.
2. Confirm the inbound message renders correctly (text bubble, correct timestamp, correct customer identity — Instagram-scoped id, since no display name is available from the webhook alone; see `INSTAGRAM_INTEGRATION.md`/`app/channels/instagram/parsing.py`'s own docs on this limitation).
3. Confirm the Instagram channel badge is visible on the conversation.

## Step 5 — AI reply

1. If the business is in Assisted Mode: confirm an AI-drafted reply appears as `pending_approval` in the Inbox/`/pending`, then click Approve.
2. If the business is in Autonomous Mode: confirm a reply is sent automatically with no approval step.
3. On the customer's Instagram account, confirm the reply actually arrives as a real Instagram DM.
4. Check the backend logs for the send outcome (`ChannelManager`'s retry/success logging, Sprint 65 PR 7) and confirm no access token or raw Graph API response body appears.

## Step 6 — Media reply

1. Attach a real, publicly-reachable image URL to a draft via `PATCH /api/v1/messages/{id}/draft` (`{"body": "...", "media": [{"kind": "image", "url": "<https-url>"}]}` — see `INSTAGRAM_INTEGRATION.md` §5 and `documentation/architecture/messaging-platform.md` §7 for exactly what media types are supported; there is no upload UI yet, only this API, per Sprint 65 PR 6's scoping decision).
2. Approve it and confirm the image actually arrives in the customer's Instagram DM thread, not just a "sent" status in HIRA.
3. Separately, have the customer send an image *to* the business account and confirm it persists correctly (`Message.media` populated, correct `type`) and renders in the Inbox (`MessageBubble`'s image rendering, `frontend/src/app/(dashboard)/inbox/page.tsx`).
4. Try a video and an audio message in at least one direction each, to exercise more than just the image path — the payload shape differs per media kind (`app/channels/instagram/send.py`).

## Step 7 — Disconnect

1. `DELETE /api/v1/instagram/disconnect` (or the dashboard's disconnect control).
2. Confirm `GET /api/v1/instagram/status` now reports `connected: false`.
3. Confirm existing `Message`/`Customer`/`Conversation` rows for that business are untouched (disconnect must never delete customer data — `app/instagram/credentials.py::disconnect()`'s own contract).
4. Send another DM from the customer's Instagram account → confirm the webhook now returns `403` (no connected credential to route to) and nothing new is persisted.

## Step 8 — Reconnect

1. Repeat Step 1 for the same business.
2. Confirm the connection succeeds and behaves identically to a first connect (same `store_credentials()` path, per `INSTAGRAM_INTEGRATION.md` §4).
3. Confirm the conversation history from before disconnect is still intact and the business can send/receive messages again immediately.

**Reconnect race (Sprint 65 PR 7 fix)** — deliberately exercise the fixed bug, not just the happy path: open two browser tabs, start the connect flow in both, and complete both roughly simultaneously (or use two rapid API calls with valid, unexpired states). Confirm neither request surfaces "this account is already connected to a different business" — both should converge on one final connected state. See `tests/test_instagram_credentials.py::test_store_credentials_reconnect_race_converges_instead_of_a_false_duplicate_error` for the automated version of this; this step is the live-Meta equivalent.

## Step 9 — Retry verification

1. Temporarily misconfigure `INSTAGRAM_APP_SECRET` to a wrong value (staging/test environment only — never do this against a production Meta App secret a real business depends on) and send a DM from the customer account.
2. Confirm the webhook returns `403`, logs a signature-verification-failure line (not a bare crash), and nothing is persisted.
3. Restore the correct secret and confirm normal delivery resumes without a restart.
4. To exercise outbound retry: temporarily point `INSTAGRAM_GRAPH_VERSION` at a version that returns a 5xx (or, more reliably, use a test double / staging Meta endpoint if available) and confirm `ChannelManager`'s retry logging (`"Retrying instagram send (attempt N/3): ..."`, Sprint 65 PR 7) appears in the logs, with the eventual outcome (success or final failure) correctly reflected in the `Message`'s status.

---

## Recording results

When this guide is actually executed, record: date, environment (which deployment), Meta App used (Development or Live mode), which steps passed/failed, and any deviation from the expected behavior above — in a PR description, an incident doc, or wherever this team tracks validation runs. Do not silently mark this file "done" without that record existing somewhere.
