# Google OAuth Verification — Final Readiness Report

**Date:** 2026-08-18
**Scope:** Technical verification only, performed against the live production site (`https://stoneveil.in`, backend `https://api.stoneveil.in`) and the current codebase. No production accounts were connected, disconnected, or otherwise mutated. No code was changed as part of this report except where explicitly noted (none — this pass was read-only).

---

## Phase 1 — Live Privacy Policy

**Finding: `https://stoneveil.in/privacy` returns HTTP 404 to every unauthenticated visitor. This is not a stale-deployment problem — it's a middleware access-control bug that blocks the entire site, not just this page.**

Verified:

```
GET https://stoneveil.in/                → 200
GET https://stoneveil.in/privacy         → 404
GET https://stoneveil.in/terms           → 404
GET https://stoneveil.in/data-deletion   → 404
GET https://stoneveil.in/contact         → 404
GET https://stoneveil.in/company         → 404
```

The response headers are the diagnostic smoking gun:

```
x-clerk-auth-reason: protect-rewrite, session-token-and-uat-missing
x-matched-path: /404
x-next-error-status: 404
```

I compared this against a request to a URL that **does not exist at all** (`/this-route-does-not-exist-xyz123`) — it returns byte-for-byte identical Clerk headers. That confirms this isn't specific to `/privacy`; **every route except `/`, `/sign-in`, and `/sign-up` is currently unreachable by any signed-out visitor**, including Googlebot and Google's own OAuth reviewer.

**Root cause:** `frontend/src/middleware.ts:10`

```ts
const isPublicRoute = createRouteMatcher(["/", "/sign-in(.*)", "/sign-up(.*)"]);
```

This is a deliberate default-deny design (per the comment above it) — any route not explicitly listed gets `auth.protect()`'d. The `(legal)` route group (`/privacy`, `/terms`, `/data-deletion`, `/contact`, `/company`) was never added to this allowlist, so Clerk rewrites every request to it to `/404` for anyone without a session.

Corroborating evidence this is intended to be public: `robots.txt` explicitly `Allow: /` with no disallow on any legal path, and `sitemap.xml` lists all five legal URLs for indexing — the sitemap/robots config assumes these pages are public, but the middleware never was updated to match.

**What I could not verify:** because the 404 is identical whether or not the underlying route exists, I cannot confirm from outside whether the currently-deployed build even contains the new policy content (the one implemented in `frontend/src/app/(legal)/privacy/page.tsx`) or an older version — the block happens before any page content is ever reached. This can only be confirmed after the middleware fix ships.

**Exact fix required (not applied — flagged per your instruction not to modify production behavior unless told to):**

```ts
const isPublicRoute = createRouteMatcher([
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/privacy",
  "/terms",
  "/data-deletion",
  "/contact",
  "/company",
]);
```

**Deployment step required:** merge that change, then a normal Vercel deploy (push to the branch Vercel is tracking, or `vercel --prod`). No env var or infra change needed — this is a one-line code fix.

This is the single blocking issue in this entire report — see Phase 7.

## Phase 2 — Google OAuth Scope

Confirmed via direct source inspection, unchanged from the prior audit:

```python
# backend/app/calendar/oauth.py:27
SCOPES = ["https://www.googleapis.com/auth/calendar"]
```

Repo-wide search for any other Calendar scope string (`calendar.readonly`, `calendar.events`, `calendar.settings`, or any other `googleapis.com/auth/calendar*` variant) returns **no other matches**. This one constant is imported and reused everywhere the scope is needed (`credentials.py`, `oauth.py`) — there is exactly one scope, requested in exactly one place, and it is `https://www.googleapis.com/auth/calendar`.

No broader scope is requested than what's in code today. (A *narrower*-scope option was already noted as an optional, non-blocking recommendation in the earlier `PRIVACY_POLICY_IMPLEMENTATION_TASKS.md` — restated in Phase 7 as a recommendation, not repeated as new analysis here, and not something to act on unless you ask.)

## Phase 3 — Production Verification

| Check | Result | Evidence |
|---|---|---|
| Backend reachable/healthy | **Healthy** | `GET https://api.stoneveil.in/health` → `200` |
| Hosting substrate | **Self-managed nginx + Docker** (the AWS EC2 target documented in `DEPLOYMENT_AWS.md`), not Railway | Response header `server: nginx/1.31.3` on the health endpoint — Railway's edge does not expose a raw nginx version like this. This resolves the "which hosting target is actually live" open question from the original audit. |
| OAuth connect endpoint | Correctly requires auth | `GET /api/v1/calendar/oauth/connect` (unauthenticated) → `401`, as expected for a route documented as "called from an authenticated dashboard request" |
| OAuth callback endpoint reachable and fails gracefully | **Working as coded** | `GET /api/v1/calendar/oauth/callback?code=test&state=garbage` → `307` redirect to `https://app.stoneveil.in/calendar?calendar=error&message=Invalid+or+expired+connection+request` — no 500, no stack trace, matches the exact error-handling path in `backend/app/api/calendar.py:192-223` |
| `app.stoneveil.in` | Not a separate deployment — it's a Vercel domain alias that 308-redirects every path to `https://stoneveil.in` (same path preserved) | `curl -I https://app.stoneveil.in/privacy` → `308` → `location: https://stoneveil.in/privacy` |
| Redirect URI Google Console should have on file | `https://api.stoneveil.in/api/v1/calendar/oauth/callback` (inferred from the live callback route responding correctly at that exact path) | I do not have Google Cloud Console access — **you need to manually confirm** the Console's "Authorized redirect URI" for this OAuth client is exactly this URL. Flagged in Phase 7 as a Google Console item, not something I can verify end-to-end from here. |
| Full live OAuth consent round-trip | **Not exercised** | Doing so would require signing in with a real Google account through the actual consent screen — out of scope per your instruction not to reconnect/disconnect production accounts. What I verified instead is that every stage of the flow the code is responsible for (auth-gating the connect endpoint, validating state, handling Google's redirect, failing gracefully on bad input) behaves correctly against the live backend. |

## Phase 4 — Limited Use Compliance Audit

Re-checked the current codebase (confirmed via `git status` that nothing outside my own privacy-page edit and the three audit docs has changed since the original audit — this is a re-verification, not a stale carry-forward):

| Claim in the new Privacy Policy | Status |
|---|---|
| Google data never used for advertising | **Accurate** — no ad SDK, no analytics beyond backend-only Sentry (`send_default_pii=False`, no tracing), confirmed again via fresh grep |
| No data sold | **Accurate** — no code path shares/sells data; nothing to contradict this |
| No claims of features that don't exist | **Accurate** — file uploads correctly described as not existing; payments correctly described as not collected (`grep` for Stripe/Razorpay/PayPal/Paddle across both `pyproject.toml` and `package.json`: zero hits, confirmed again) |
| AI providers listed accurately | **Accurate** — `anthropic` and `groq` are the only AI SDKs in `pyproject.toml`; no `openai`/`google-generativeai`/`cohere`/`mistral` anywhere in the repo |
| Authentication providers listed accurately | **Accurate** — Clerk is the only auth provider (`middleware.ts`, `@clerk/nextjs`); confirmed still true |
| Third-party services listed accurately | **Accurate**, and actually improved over the old policy — the new page deliberately says "our hosting and infrastructure providers" instead of naming Railway (which the old policy did, inaccurately, per Phase 3's finding that production actually runs on self-managed nginx/Docker, not Railway) |
| Data retention statements match implementation | **Accurate** — no TTL on live conversation/message/KB data (unchanged), 14-day backup retention matches `backend/scripts/backup_postgres.sh:16` exactly |

**No discrepancies found in Phase 4.**

## Phase 5 — Token Revocation Review

**Does HIRA revoke Google's OAuth grant on disconnect? No — it only deletes the locally stored token.**

```python
# backend/app/calendar/credentials.py:65-72
def disconnect(db: Session, business_id: uuid.UUID) -> bool:
    """Remove a business's stored calendar credentials. Returns False if none existed."""
    existing = get_stored_credential(db, business_id)
    if existing is None:
        return False
    db.delete(existing)
    db.commit()
    return True
```

Called from:

```python
# backend/app/api/calendar.py:240-245
@router.delete("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_calendar(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> None:
    calendar_credentials.disconnect(db, principal.business_id)
```

No reference to `oauth2.googleapis.com/revoke` or `Credentials.revoke()` exists anywhere in the repo.

**Affected files:** `backend/app/calendar/credentials.py` (the `disconnect` function itself), `backend/app/api/calendar.py` (the only call site).

**Exact recommended implementation** (not applied, per your instruction):

1. In `credentials.py`, before deleting the row, decrypt the stored refresh token (the code already does this in `build_google_credentials`) and issue `POST https://oauth2.googleapis.com/revoke?token={refresh_token}` using `httpx` (already a project dependency — no new dependency needed).
2. Treat a failed revoke call as non-fatal but logged — don't block the user's local disconnect if Google's revoke endpoint is briefly unavailable, matching the existing "log the underlying error, never surface it raw" pattern used in the callback handler (`api/calendar.py:216-219`).
3. Suggested shape:
   ```python
   def disconnect(db: Session, business_id: uuid.UUID) -> bool:
       existing = get_stored_credential(db, business_id)
       if existing is None:
           return False
       _revoke_at_google(decrypt_token(existing.refresh_token_encrypted))  # new helper, logs+swallows failure
       db.delete(existing)
       db.commit()
       return True
   ```
4. This closes the exact gap the current Privacy Policy discloses honestly ("disconnecting does not, on its own, revoke HIRA's access grant on Google's side") — implementing it would let that sentence be dropped or strengthened, but isn't required for the current disclosure to be truthful.

## Phase 6 — Legal Consistency Review

Read all four legal pages in full (`privacy`, `terms`, `data-deletion`, `company`) plus `contact` and the shared footer/header nav.

**Structural strength:** `ENTITY_NAME`, `PRODUCT_NAME`, `SUPPORT_EMAIL`, `SITE_URL`, and `GOVERNING_LAW` are all imported from a single shared file (`frontend/src/lib/legal.ts`) by every legal page. This makes company name, contact email, and product name **consistent by construction** — there is no drift to find here, and no discrepancy exists.

**Broken links:** none. Every internal link in the footer, header, and cross-page references (`/privacy`, `/terms`, `/data-deletion`, `/contact`, `/company`) resolves to a route that exists in the codebase.

**References to Railway or old infrastructure:** none, in any current legal page. (The old Privacy Policy did name Railway explicitly — that's gone now, replaced with generic language, which per Phase 3's finding is actually more accurate.)

**Missing Google disclosures:** none found in the new Privacy Policy content itself — all required elements (Google User Data, Google Calendar Integration, Limited Use statement, retention, disconnect behavior, security, third-party services) are present as written. (Whether that content is actually what's *served* in production is the open question from Phase 1.)

**One real discrepancy found:**

- **Terms of Service** (`terms/page.tsx:29-32`) and **Company** (`company/page.tsx:21-25`) both explicitly and prominently disclose: *"Stoneveil is not yet a registered company, LLP, or other formal legal entity."* Terms repeats this again in its Governing Law section.
- The **Privacy Policy** and **Data Deletion** pages say nothing about this — they refer to Stoneveil as a normal named entity ("we," "us") with no caveat.
- This isn't a factual error in the Privacy Policy (it doesn't claim incorporation), but it *is* an inconsistency: a reader who reads Terms and Company would learn something material that Privacy is silent on, for the same entity, on the same site. Worth a conscious decision on whether Privacy should carry the same disclosure, not something I'm changing without your say-so (this is exactly the kind of legal/business call the operating rules say to bring to you rather than resolve myself).

## Phase 7 — Final Readiness Report

### Blocking Issues

1. **`/privacy` (and every other legal page) returns 404 to unauthenticated visitors in production**, due to `frontend/src/middleware.ts`'s route matcher not including the `(legal)` route group. This is not specific to the new policy — it would have blocked the *old* policy too. Google's reviewer cannot read the Privacy Policy at all right now. **This must be fixed and redeployed before resubmitting.** Exact fix is in Phase 1 above; it's a one-line change to `middleware.ts` plus a redeploy — I have not applied it, since none of the seven phases instructed me to.

### Needs Deployment

- The middleware fix above (Phase 1), once you approve it.
- Once middleware is fixed, **re-verify that the live page actually renders the new content** (Google User Data, Google Calendar Integration, Limited Use statement, etc.) — this could not be confirmed in this pass because the 404 blocks any content check regardless of what's actually deployed underneath.

### Needs Google Console Change (verification, not necessarily a change)

- Confirm the OAuth client's **Authorized redirect URI** in Google Cloud Console is exactly `https://api.stoneveil.in/api/v1/calendar/oauth/callback` — I inferred this is the correct value from how the live callback route behaves, but I have no Console access to confirm it's what's actually registered.
- Confirm the **Privacy Policy URL** entered in the OAuth consent screen is `https://stoneveil.in/privacy` and that the scope listed there matches `https://www.googleapis.com/auth/calendar` exactly (Phase 2).

### Recommended Improvements (non-blocking)

- Implement Google token revocation on disconnect (Phase 5) — strengthens an already-honest disclosure but isn't required for it to be truthful.
- Consider narrowing the Calendar OAuth scope if `calendar.events` proves sufficient for the freebusy + booking-write usage (carried forward from `PRIVACY_POLICY_IMPLEMENTATION_TASKS.md`, not re-analyzed here) — optional, not a blocker.
- Resolve the Terms/Company vs. Privacy/Data-Deletion incorporation-disclosure inconsistency (Phase 6) — a business/legal decision, not an engineering one.
- Decide whether to complete Stoneveil's incorporation before resubmitting, or consciously proceed without it (carried forward from the original audit — still unresolved, still your call).

### Blocking Issues Summary

**HIRA is not yet technically ready for Google OAuth verification resubmission — one blocker exists: the Privacy Policy (and every other legal page) is unreachable by unauthenticated visitors in production due to a middleware configuration gap, unrelated to the policy content itself.** Everything else checked in this report — the OAuth scope, the callback flow, the backend's health, the policy's factual accuracy against the implementation, and cross-page legal consistency — came back clean. Fix the one middleware line, redeploy, re-verify the live page renders the new content, and confirm the two Google Console values above — at that point there are no known remaining blockers.
