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
