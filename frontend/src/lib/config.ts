// Runtime configuration derived from environment variables.

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Auth is "enabled" (real Clerk) when a publishable key is present. When absent
// we fall back to a development mock — but NEVER in production.
export const clerkPublishableKey =
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";

export const authEnabled = clerkPublishableKey.length > 0;

// Clerk's publishable key prefix reliably encodes which kind of instance it
// belongs to (Clerk's own documented convention): pk_test_ for development
// instances (real auth, but with strict usage limits and a "Development
// mode" banner Clerk itself warns about — see the console on app load),
// pk_live_ for production. Sprint 77: this closes an RC-1 finding — a
// production deploy was running on a pk_test_ key with no signal anywhere
// a founder would see it until Clerk's own request cap was eventually hit.
export const clerkKeyLooksLikeTestKey = clerkPublishableKey.startsWith("pk_test_");

export const isProduction = process.env.NODE_ENV === "production";

// Mock auth is only allowed outside production. In production without Clerk,
// the app refuses to render protected content (see AuthLayer) rather than
// bypassing authentication.
export const mockAuthAllowed = authEnabled || !isProduction;

// WhatsApp Embedded Signup (Track B prep, TODOS.md ONBOARD-E). Mirrors
// authEnabled's derivation above: "enabled" means there's actually something
// configured to use, not just a flag flipped on by mistake. Both must be set
// or the entry screen falls back to the existing manual connect flow — see
// (dashboard)/connect-whatsapp/page.tsx. The backend independently gates its
// own routes on ENABLE_EMBEDDED_SIGNUP; this is only the frontend's own copy
// of that decision so the entry screen doesn't have to round-trip an API
// call just to know whether to render itself.
export const embeddedSignupConfigId = process.env.NEXT_PUBLIC_EMBEDDED_SIGNUP_CONFIG_ID ?? "";
export const embeddedSignupEnabled =
  process.env.NEXT_PUBLIC_ENABLE_EMBEDDED_SIGNUP === "true" && embeddedSignupConfigId.length > 0;

// Polling cadence for data that can change from outside the dashboard (a
// WhatsApp webhook firing asynchronously) — pending replies, conversations,
// and message threads all use this so refresh behavior stays consistent.
export const POLL_INTERVAL_MS = 15_000;

// WhatsApp Cloud API's text message body limit — matches the backend's
// PATCH /messages/{id}/draft validation (backend/app/api/dashboard.py).
export const MAX_DRAFT_LENGTH = 4096;
