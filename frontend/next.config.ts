import type { NextConfig } from "next";
import { resolve } from "node:path";

// A11 audit fix note: this API origin is also what the backend's CORS
// allowlist must accept — see backend/app/main.py's `_CORS_ORIGINS`/
// `settings.frontend_url` for the other half of that relationship.
const apiOrigin = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// A Clerk publishable key encodes its own Frontend API host: `pk_(test|live)_`
// + base64(`${frontendApiHost}$`) — Clerk's own documented key format, not
// something specific to this app. Deriving the CSP origin from the same key
// that configures ClerkProvider (frontend/src/lib/config.ts) means
// script-src/connect-src always match whatever Clerk instance this build is
// actually wired to — dev, prod, or any future staging custom domain — with
// zero source changes when that changes, only the env var.
function deriveClerkFrontendOrigin(publishableKey: string | undefined): string | null {
  const match = publishableKey ? /^pk_(?:test|live)_(.+)$/.exec(publishableKey) : null;
  if (!match) return null;
  try {
    const host = Buffer.from(match[1], "base64").toString("utf-8").replace(/\$$/, "");
    // Reject anything that doesn't look like a bare hostname rather than
    // interpolate malformed/unexpected data into a security header.
    return /^[a-zA-Z0-9.-]+$/.test(host) ? `https://${host}` : null;
  } catch {
    return null;
  }
}

const clerkFrontendOrigin = deriveClerkFrontendOrigin(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
if (process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && !clerkFrontendOrigin) {
  // A key is set but doesn't decode — falling back to the generic domains
  // below silently would leave a misconfigured build passing the build step
  // with a CSP that may not match the actual Clerk instance in use.
  console.warn(
    "[HIRA] NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY did not decode to a Clerk Frontend API host — " +
      "falling back to the generic *.clerk.accounts.dev/*.clerk.com CSP allowlist. Verify the key is valid.",
  );
}

// Falls back to Clerk's generic domains only when the key is missing or
// didn't decode (e.g. a build with no env configured) — in normal operation
// the derived origin above is exact, covers dev/prod/staging alike, and is
// tighter than the old blanket wildcards.
const CLERK_SCRIPT = clerkFrontendOrigin
  ? `${clerkFrontendOrigin} https://challenges.cloudflare.com`
  : "https://*.clerk.accounts.dev https://*.clerk.com https://challenges.cloudflare.com";
const CLERK_CONNECT = clerkFrontendOrigin
  ? `${clerkFrontendOrigin} https://api.clerk.com`
  : "https://*.clerk.accounts.dev https://*.clerk.com https://api.clerk.com";
const CLERK_IMG = "https://img.clerk.com https://images.clerk.dev";
const CLERK_FRAME = "https://challenges.cloudflare.com";

// Next.js's dev server (Fast Refresh/HMR) genuinely needs 'unsafe-eval' —
// production builds don't. Keeping this dev-only avoids loosening the
// policy actually shipped to real users for a build-tool requirement they
// never hit.
const scriptSrc = ["'self'", "'unsafe-inline'", CLERK_SCRIPT];
if (process.env.NODE_ENV !== "production") {
  scriptSrc.push("'unsafe-eval'");
}

// A10 (Sprint S1 security audit): a baseline CSP plus the standard
// defense-in-depth headers that were previously entirely absent. 'unsafe-
// inline' remains on script-src/style-src — Next.js's own hydration data
// script and Clerk's inline initialization both rely on it; removing it
// would need a nonce-based setup, a bigger change than this "baseline"
// fix calls for. Every directive here is either 'self', a documented Clerk
// requirement, or this app's own configured API origin — nothing broader.
const CSP = [
  `default-src 'self'`,
  `script-src ${scriptSrc.join(" ")}`,
  `style-src 'self' 'unsafe-inline'`,
  `img-src 'self' data: ${CLERK_IMG}`,
  `font-src 'self' data:`,
  `connect-src 'self' ${apiOrigin} ${CLERK_CONNECT}`,
  `frame-src ${CLERK_FRAME}`,
  `worker-src 'self' blob:`,
  `frame-ancestors 'none'`,
  `base-uri 'self'`,
  `form-action 'self'`,
].join("; ");

const nextConfig: NextConfig = {
  // The frontend package is the tracing boundary. Without this, Next walks
  // upward to an unrelated home-directory lockfile and emits a warning.
  outputFileTracingRoot: resolve(process.cwd()),
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // Defense-in-depth against clickjacking — duplicates
          // frame-ancestors 'none' above for browsers that don't act on CSP.
          { key: "X-Frame-Options", value: "DENY" },
          // Stops the browser from guessing/re-interpreting a response's
          // MIME type (e.g. treating a user-uploaded file as executable JS).
          { key: "X-Content-Type-Options", value: "nosniff" },
          // Never send this app's URLs (which can carry sensitive path
          // segments) to a third-party site a user navigates to from here.
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Disables browser features this app never uses, so an embedded
          // context can't invoke them on a user's behalf.
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          { key: "Content-Security-Policy", value: CSP },
        ],
      },
    ];
  },
};

export default nextConfig;
