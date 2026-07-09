// Runtime configuration derived from environment variables.

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Auth is "enabled" (real Clerk) when a publishable key is present. When absent
// we fall back to a development mock — but NEVER in production.
export const clerkPublishableKey =
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";

export const authEnabled = clerkPublishableKey.length > 0;

export const isProduction = process.env.NODE_ENV === "production";

// Mock auth is only allowed outside production. In production without Clerk,
// the app refuses to render protected content (see AuthLayer) rather than
// bypassing authentication.
export const mockAuthAllowed = authEnabled || !isProduction;

// Polling cadence for data that can change from outside the dashboard (a
// WhatsApp webhook firing asynchronously) — pending replies, conversations,
// and message threads all use this so refresh behavior stays consistent.
export const POLL_INTERVAL_MS = 15_000;

// WhatsApp Cloud API's text message body limit — matches the backend's
// PATCH /messages/{id}/draft validation (backend/app/api/dashboard.py).
export const MAX_DRAFT_LENGTH = 4096;
