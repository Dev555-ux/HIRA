# Implementation Recommendations — Privacy Policy Follow-Ups

Deliverable 3 of 3. These are gaps where the new Privacy Policy (`PRIVACY_POLICY_NEW.md`) states
something true about *today's* behavior, but where the underlying behavior itself is worth improving —
either because Google's reviewers will likely expect it, or because it's a real product/legal gap
independent of Google. Nothing here was invented; each ties back to a finding in `PRIVACY_POLICY_AUDIT.md`.

Ranked roughly by how directly each affects the OAuth re-submission.

## Directly relevant to Google OAuth re-verification

1. **Add token revocation on Calendar disconnect.**
   Currently `DELETE /api/v1/calendar/disconnect` (`backend/app/calendar/credentials.py:66-73`) deletes
   the local `CalendarCredential` row but never calls Google's revoke endpoint. The new policy discloses
   this honestly rather than overclaiming — but Google's reviewers specifically look for apps to revoke
   grants on disconnect, and it's a small change: call `google.oauth2.credentials.Credentials.revoke()`
   (or POST to `https://oauth2.googleapis.com/revoke` with the refresh token) before deleting the row.
   Do this before resubmitting if possible — it upgrades the policy from an honest gap to a stronger claim.

2. **Consider narrowing the Calendar OAuth scope.**
   HIRA currently requests `https://www.googleapis.com/auth/calendar` (full access) but only uses
   freebusy queries and event create/update/delete. `https://www.googleapis.com/auth/calendar.events`
   (event-only read/write) may cover the actual usage and is a narrower, less sensitive scope in
   Google's own classification — narrower scopes generally face a lighter verification bar. This needs
   a code change (`backend/app/calendar/oauth.py:27`) and testing that freebusy queries still work under
   the narrower scope before switching; flagging as a recommendation, not a guaranteed drop-in.

3. **Verify the OAuth consent screen's listed scopes match what the policy now discloses.**
   Not a code task — a Google Cloud Console configuration check. The scope named in the new policy
   (§5) must match exactly what's configured in the OAuth consent screen submission.

## Real gaps independent of Google

4. **No account/business-level deletion endpoint exists.**
   `PRIVACY_POLICY_AUDIT.md` §11 confirms every deletion today is manual, handled by the team via email
   per `/data-deletion`. The new policy states this accurately and doesn't promise a self-service
   button. If self-serve deletion becomes a product priority, that's a real backend feature (cascading
   delete on `Business`, revoking all connected third-party tokens first) — not a documentation fix.

5. **Backups are local-only and unencrypted by the backup script.**
   `backend/scripts/backup_postgres.sh` writes gzip dumps to local disk on the host with no offsite
   copy and no encryption applied by the script itself. This is an infra resilience/security gap, not
   something the privacy policy needs to disclose in detail — but worth fixing independent of this audit
   (offsite copy for disaster recovery, encryption at rest for the dump files).

6. **No secrets manager.**
   Already flagged in the project's own `PRODUCTION_CHECKLIST.md:12`. Out of scope for the privacy
   policy itself, noted here only because it surfaced during the audit.

## Legal/business decisions — not engineering tasks

7. **Stoneveil is not yet incorporated.**
   `frontend/src/lib/legal.ts:5-8` — a founder-dated TODO already documents this. The new policy uses
   the existing `ENTITY_NAME`/`GOVERNING_LAW` constants for consistency with the rest of the site, but
   publishing a privacy policy (especially one submitted as part of a Google OAuth review) that names a
   legal entity ahead of incorporation is a real exposure, not a formatting detail. This needs a founder
   decision: either complete incorporation before resubmitting to Google, or consciously accept the risk
   and document why. Not something to resolve by editing code.

8. **No cookie-consent mechanism exists.**
   Not required today (HIRA sets exactly one essential, non-advertising cookie), but if HIRA knowingly
   serves EU/UK users, GDPR/ePrivacy expectations around consent banners may apply even for
   "essential-only" cookie setups in some interpretations. Recommend a decision on whether HIRA is
   targeting EU/UK users at all before investing engineering time here.

9. **Confirm production `LLM_PROVIDER` and hosting target.**
   Both are deploy-time configuration, not visible in code (`PRIVACY_POLICY_AUDIT.md` Unresolved
   Questions #2–3). The new policy is written to be accurate regardless of which is live, but internal
   documentation (`DEPLOYMENT.md`) should be updated to state the actual current state rather than
   leaving it ambiguous ("not yet executed") once resolved.

## Not gaps — confirmed already correct, no action needed

- File uploads: correctly not claimed anywhere in the new policy; feature doesn't exist.
- Payments: correctly not claimed; no payment processing exists in code.
- Analytics/tracking: correctly limited to backend-only, PII-scrubbed Sentry; no consent-triggering
  analytics tooling exists to disclose.
- Embeddings: correctly described as fully local; no third-party embeddings API is called.
