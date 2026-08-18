# Privacy Policy Compliance Audit — HIRA / Stoneveil

**Date:** 2026-08-18
**Trigger:** Google rejected the OAuth verification submission, stating the Privacy Policy does not sufficiently disclose how Google user data is collected, used, protected, retained, and handled.
**Method:** Full codebase audit (backend `app/`, frontend `src/`, migrations, deployment docs). Every claim below is cited to a file and line. Anything not verifiable from code is marked **Needs Owner Confirmation** rather than assumed.

This document is Deliverable 1 of 3. See also `PRIVACY_POLICY_NEW.md` (Deliverable 2) and `PRIVACY_POLICY_IMPLEMENTATION_TASKS.md` (Deliverable 3).

---

## 1. Authentication

- **Sole provider: Clerk.** Backend verifies Clerk-issued RS256 JWTs against Clerk's JWKS endpoint (`backend/app/auth/clerk.py:41-62`), resolving to a local `User` row scoped to a `business_id` (`backend/app/auth/dependencies.py:1-39`). Frontend uses `@clerk/nextjs` (`frontend/package.json`), wired via `frontend/src/middleware.ts` and `frontend/src/components/providers.tsx`.
- No email/password, Auth0, or NextAuth in the codebase.
- **Google is not used for login/identity** — only for Calendar data access (§2), a separate OAuth grant.
- A dev-only `MOCK_TOKEN` bypass exists (`backend/app/auth/dependencies.py:31-48`). **Needs Owner Confirmation**: verify this path cannot be reached in production. Not a privacy-policy disclosure item, but worth closing before wider launch.

## 2. Google OAuth / Calendar — the section Google flagged

| Item | Finding | Evidence |
|---|---|---|
| Scope requested | `https://www.googleapis.com/auth/calendar` — the **full** read/write calendar scope, not a narrower one | `backend/app/calendar/oauth.py:27` |
| Actual usage | (a) `freebusy().query()` to check availability — busy/free time only, no event titles/descriptions/attendees read; (b) `events().insert/patch/delete()` to create, reschedule, and cancel appointments **that HIRA itself books**. Nothing in the codebase reads a user's pre-existing calendar events. | `backend/app/calendar/providers/google.py:84-151` |
| OAuth flow | `google-auth-oauthlib` `Flow`, `access_type=offline`, `prompt=consent` (forces refresh token). CSRF protection: HMAC-SHA256-signed `state` param carrying `business_id` + timestamp, constant-time verified, 600s expiry. Callback is a public route (`GET /api/v1/calendar/oauth/callback`) that relies entirely on this signed state. | `backend/app/calendar/oauth.py:75-116`, `backend/app/api/calendar.py:192-223` |
| Refresh tokens | Obtained once at connect (`exchange_code_for_refresh_token()`); access-token renewal thereafter is handled implicitly by `googleapiclient`, not custom code | `backend/app/calendar/oauth.py:119-138`, `backend/app/calendar/credentials.py:6-9` |
| Storage / encryption | Refresh token stored **Fernet-encrypted** (AES128-CBC+HMAC) in a single `CalendarCredential` row per business, one shared key (`CALENDAR_ENCRYPTION_KEY`) for all tenants | `backend/app/calendar/security.py:1-32`, `backend/app/models.py:313-324` |
| Disconnect | `DELETE /api/v1/calendar/disconnect` **hard-deletes** the `CalendarCredential` row from the DB | `backend/app/api/calendar.py:240-244`, `backend/app/calendar/credentials.py:66-73` |
| **Gap: no revocation call** | No call to Google's revoke endpoint (`oauth2.googleapis.com/revoke` or `Credentials.revoke()`) exists anywhere in the codebase. Disconnecting deletes HIRA's copy of the token but does **not** revoke the grant at Google. The grant remains listed under the user's Google Account third-party access until they revoke it themselves or it naturally expires. | Repo-wide grep, no matches |

**Why this matters for the rejection:** the current live policy says only "calendar event data via Google Calendar, limited to calendar access" — it never names the scope, never explains the freebusy-vs-write distinction, never states retention or deletion behavior for Google data specifically, and has no Limited Use statement at all. That is almost certainly the specific gap Google's reviewer is pointing at.

## 3. AI Providers

| Provider | Model | Trigger | Data sent | Evidence |
|---|---|---|---|---|
| Anthropic (Claude) | `claude-sonnet-4-6` (configurable) | Customer-facing reply generation, when `LLM_PROVIDER=claude` | System prompt: business name, customer `display_name`, lead stage/source/value/follow-up, upcoming appointment times, retrieved knowledge-base chunks, rolling conversation summary, plus the last 20 raw messages verbatim | `backend/app/ai/llm/claude.py:38-73`, `backend/app/ai/prompts.py:248-260`, `backend/app/ai/context.py:65-103` |
| Groq | `llama-3.3-70b-versatile` (configurable) | Same reply path, when `LLM_PROVIDER=groq` | Same payload shape | `backend/app/ai/llm/groq.py:78-112` |
| Anthropic (Claude) | same client | Background conversation summarization ("memory" compaction) | Raw older-window transcript text, verbatim | `backend/app/ai/memory.py:35-98` |

- **No `openai`, `google.generativeai`, `cohere`, or `mistralai` imports anywhere** — only Anthropic and Groq are integrated.
- Provider selection is a deploy-time env var (`LLM_PROVIDER`); code default is `"mock"`. **Needs Owner Confirmation**: which provider is actually live in production. The policy should state "Anthropic and/or Groq, never both for the same message" rather than naming one definitively — this matches how the existing policy already phrases it.
- **Embeddings run entirely locally** via `fastembed` (`BAAI/bge-small-en-v1.5`) — no external API call, no network egress for this step. Stored in Postgres/pgvector. (`backend/app/ai/knowledge_base.py:20-21,54,59,101-103,178`)
- **Memory**: `Conversation.summary` is an LLM-generated rolling summary, persisted to Postgres, re-injected into future prompts for that conversation. This is the only cross-turn memory mechanism — no separate long-term fact store. (`backend/app/ai/memory.py:1-14,56-107`)
- No zero-retention / no-training API flag is set in either provider integration in code. Whether Anthropic/Groq train on this traffic is governed by their own commercial API terms, not anything HIRA configures. **Needs Owner Confirmation**: check current Anthropic and Groq API/DPA terms before asserting "not used for training" as a HIRA-side guarantee — the existing policy's phrasing ("does not operate its own foundation model and does not use business data to train one") is accurate as a statement about HIRA, and is preserved as such in the new draft.

## 4. User Data — full data model

| Data type | Table | Contents | Evidence |
|---|---|---|---|
| Business/tenant profile | `businesses` | name, industry, timezone, contact email, country, WhatsApp IDs, working hours | `backend/app/models.py:31-78` |
| Staff account | `users` | Clerk user ID, email, role, business_id | `backend/app/models.py:81-91` |
| Customer/CRM record | `customers` | WhatsApp phone, display name, email, free-text notes, company | `backend/app/models.py:94-117` |
| Conversation | `conversations` | status, rolling AI-generated summary | `backend/app/models.py:120-142` |
| Message | `messages` | full message body text, direction, WhatsApp message ID, AI metadata (JSONB) | `backend/app/models.py:145-185` |
| Knowledge base | `kb_entries` | title, content text, 384-dim embedding vector, status | `backend/app/models.py:188-210` |
| Appointment | `appointments` | customer_id, Google event ID, start/end, status | `backend/app/models.py:213-232` |
| Escalation | `escalations` | reason, status, assigned/resolved staff | `backend/app/models.py:235-260` |
| Lead | `leads` | pipeline stage, source, estimated value, free-text notes, follow-up date | `backend/app/models.py:263-287` |
| Lead activity log | `lead_events` | append-only timeline of lead changes | `backend/app/models.py:290-310` |
| Google Calendar credential | `calendar_credentials` | encrypted refresh token, calendar ID, scopes | `backend/app/models.py:313-324` |
| WhatsApp credential | `whatsapp_credentials` | encrypted access token, app secret | `backend/app/models.py:327-345` |
| Instagram credential | `instagram_credentials` | encrypted page access token, IG account ID/username | `backend/app/models.py:348-377` |
| AI execution trace | `execution_traces` | per-turn AI plan, proposed tool calls, result message IDs | `backend/app/models.py:410-479` |
| Background job payloads | `job_outbox` | task-specific JSONB payload (may include message-send data) | `backend/app/jobs/models.py:24-87` |

All business-scoped tables carry `business_id` for tenant isolation.

## 5. File Uploads — feature does not exist

Grepped the full repo for `boto3`, S3 clients, `UploadFile`, `multipart/form-data`, presigned URLs — **zero matches**. **HIRA has no document/file upload capability today.** Knowledge-base content enters only two ways:
- Manual text entry by the business owner (`kb_entries.content`)
- Public website URL import, parsed with BeautifulSoup (`backend/app/ai/web_import.py:21,68,73`)

The existing privacy policy already reflects this correctly ("FAQs, pricing, hours... a business enters or imports from its own website"). **The new policy must not claim a general file-upload feature.**

## 6. Analytics & Telemetry

| Service | Found? | Notes |
|---|---|---|
| Sentry | Yes (backend only) | Error monitoring only — `traces_sample_rate=0.0` (no APM/tracing), `send_default_pii=False`, explicit header-scrubber strips `authorization`/`cookie`/signature headers before events leave the process, only a `business_id` tag attached. DSN empty by default (no-op unless set). `backend/app/core/monitoring.py:25-61`, `backend/app/core/config.py:195` |
| Google Analytics, Vercel Analytics, PostHog, Plausible, Microsoft Clarity, Mixpanel, Amplitude, Segment, Hotjar | **Not found** | Zero hits across backend and frontend |
| Frontend Sentry | Not found | No `@sentry/nextjs` dependency |
| Tracking pixels (Meta Pixel, LinkedIn Insight, etc.) | Not found | — |

## 7. Payments

**No payment processing is live in code.** Zero hits for Stripe/Razorpay/PayPal/Paddle/LemonSqueezy anywhere. The frontend's own Terms page states this directly: *"HIRA does not currently charge for access"* (`frontend/src/app/(legal)/terms/page.tsx:98-105`). No payment information is collected today.

## 8. Infrastructure

| Category | Finding | Evidence |
|---|---|---|
| Backend compute | Documented as Railway, but `documentation/DEPLOYMENT.md:10` states production deployment steps were "not yet executed" as of the last doc update. A parallel AWS EC2 self-managed Docker Compose target exists (`backend/docker-compose.prod.yml`, `documentation/DEPLOYMENT_AWS.md`). **Needs Owner Confirmation**: which is actually live at publish time — the policy should describe hosting generically enough not to overclaim. |
| Database | Postgres + pgvector, self-hosted in Docker — not RDS |
| Frontend hosting | Vercel (`hira-tau.vercel.app` in CORS allowlist, `backend/app/main.py:186`) |
| AWS managed services (S3/SES/SNS/Lambda) | **None** — no `boto3` dependency anywhere |
| Email provider | **None found** — no Resend/SendGrid/Postmark/SES/SMTP anywhere in code or `.env.example`. HIRA currently sends no transactional email (welcome, password reset, notification) via any provider. |
| Backups | Nightly `pg_dump`, gzip, cron on the host, **14-day retention** (`RETENTION_DAYS=14`, env-overridable), stored **locally only** at `/var/backups/hira-postgres` — no offsite/S3 copy, not encrypted by the script itself | `backend/scripts/backup_postgres.sh:16,32`, `documentation/DEPLOYMENT_AWS.md:247-255` |
| Secrets management | Plain `.env` file / Railway Variables tab — no secrets manager. Already flagged as a gap in the project's own `PRODUCTION_CHECKLIST.md:12`. |

## 9. Third-Party Services (master list, code-verified)

Anthropic · Groq · Google (Calendar OAuth) · Meta WhatsApp Cloud API · Meta Instagram Graph API · Clerk · Sentry · Vercel · Railway/AWS EC2 (hosting).

**Not integrated**: any payment processor, any email-sending service, any AWS managed data service.

## 10. Cookies

Only cookie in use: **Clerk's own session cookie(s)**, set entirely by the Clerk SDK/middleware — no app code sets cookies. Zero hits for `set_cookie`/`response.cookies` in the backend, zero hits for `document.cookie` or `cookies()` in the frontend. No CSRF cookie, no preference cookie (theme uses `localStorage`, not a cookie), **no cookie-consent mechanism exists anywhere in the repo**. Exact Clerk cookie names/TTLs are SDK-internal — **Needs Owner Confirmation** via Clerk's own documentation if the policy needs to name them individually (not required for Google's review; flagged for GDPR completeness).

## 11. Account Deletion

**No self-service account or business-level deletion endpoint exists anywhere in the API.** This is already correctly reflected on the site's own `/data-deletion` page ("There is no self-service 'delete my account' button in the product today — every deletion request is handled directly by our team"). Per-resource hard deletes do exist and cascade via DB-level `ON DELETE CASCADE`:

| Resource | Endpoint | Behavior |
|---|---|---|
| Customer | `DELETE /customers/{id}` | Hard delete; cascades to conversations/messages/leads/appointments |
| Lead | `DELETE /leads/{id}` | Hard delete; cascades to lead events |
| Knowledge base entry | `DELETE /knowledge_base/{id}` | Hard delete, including embedding |
| Google Calendar | `DELETE /calendar/disconnect` | Hard-deletes local credential row; **no Google-side revocation** (see §2) |
| Instagram | `DELETE /instagram/disconnect` | Same pattern — local delete only, no revocation |
| WhatsApp | `POST /whatsapp/disconnect` | Deletes credential, nulls business-level mirror fields |

If a `Business` row were ever deleted, cascades would remove everything belonging to it automatically — but **no code path triggers that today**; it would have to be done manually by the team, matching what `/data-deletion` already describes.

## 12. Data Retention

| Data type | Retention enforced by code? | Finding |
|---|---|---|
| Conversations / messages | No | Kept indefinitely, no TTL/cron |
| `job_outbox` (AI job payloads) | No | Kept indefinitely, no cleanup job |
| Knowledge base entries | No | Deleted only on explicit user action |
| Google/Instagram/WhatsApp tokens | No | Deleted only on manual disconnect |
| DB backups | **Yes — 14 days** | `RETENTION_DAYS=14`, pruned via `find -mtime +14 -delete` |

No retention period is enforced anywhere for live conversation/message data — it is retained indefinitely by default while a business account is active. The existing policy already frames this honestly ("We keep data for as long as a business's account is active") — the new draft keeps that framing rather than inventing a fixed retention number that isn't in the code.

---

## Phase 2 — Gap Analysis vs. Google / GDPR Requirements

| Requirement | Current policy | Gap |
|---|---|---|
| Google API Services User Data Policy / Limited Use statement | **Absent entirely** | **Critical — add verbatim statement** |
| Explicit Calendar scope disclosure | Says only "limited to calendar access" | Must name the literal scope and explain freebusy-vs-write usage |
| Google data retention/deletion specifics | Generic account-level retention only | Must state Calendar-specific retention and disconnect behavior, including the no-revocation gap |
| "Never sold / never used for ads" tied specifically to Google data | Exists only as a general statement | Must be explicit under the Google section per Google's requirement |
| Dedicated "Google User Data" / "Google Calendar Integration" headings | Buried in "AI Processing" and "Third-Party Services" | Must be its own discoverable section |
| Uploaded Documents section | Not present | Should exist and state the feature doesn't exist yet, per the mission's required 21-section structure |
| International transfers | Not present | Should disclose that providers (Anthropic, Groq, Google, Clerk, Vercel) may process data outside India, including in the US |
| Children's privacy | Not present | Standard disclosure needed |
| Entity/jurisdiction certainty | Uses placeholder entity facts | See "Unresolved Questions" below — this is the most consequential open item |

## Unresolved Questions / Needs Owner Confirmation

1. **Stoneveil is not yet incorporated.** `frontend/src/lib/legal.ts:5-8` carries a founder-dated TODO (2026-08-12): `ENTITY_NAME`, `GOVERNING_LAW`, and the missing Grievance Officer name are explicitly marked as placeholders pending incorporation, to be resolved "before any wider commercial launch." The new policy uses the current constants (`Stoneveil`, Republic of India, `support@stoneveil.in`) to stay consistent with every other page on the site — but this is a **real legal exposure**, not a documentation nit: a privacy policy naming an entity that doesn't yet legally exist is itself a disclosure problem. Flag to the founder directly; see Deliverable 3.
2. Which LLM provider (`claude` vs `groq`) is actually set via `LLM_PROVIDER` in production — a deploy-time env var, not visible in code.
3. Which hosting target is actually live (Railway vs. the AWS EC2 migration) — `DEPLOYMENT.md` suggests neither was confirmed executed as of the last update.
4. Whether HIRA currently or imminently serves EU/UK data subjects — determines whether GDPR transfer mechanisms (SCCs) need explicit mention, and whether a cookie-consent banner becomes legally required (none exists today).
5. Exact Clerk session cookie names/TTLs — SDK-internal, not derivable from this repo.
6. Whether tool-call arguments passed to the LLM (e.g. booking tool calls) carry structured PII beyond what's in the system prompt — not exhaustively traced in this audit.

## Verified Facts vs. Assumptions Avoided

Every table above cites file:line. Nothing in Deliverable 2 states a retention period, deletion behavior, or third-party integration that isn't backed by one of these citations. Where the codebase is silent (fixed retention periods, Google token revocation, backup encryption), the new policy says so honestly rather than asserting best-practice behavior HIRA doesn't yet implement — consistent with the instruction not to invent answers.
