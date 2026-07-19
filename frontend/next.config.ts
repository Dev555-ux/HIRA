import type { NextConfig } from "next";

// A11 audit fix note: this API origin is also what the backend's CORS
// allowlist must accept — see backend/app/main.py's `_CORS_ORIGINS`/
// `settings.frontend_url` for the other half of that relationship.
const apiOrigin = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Clerk's own documented CSP requirements (frontend API + Cloudflare
// Turnstile bot-check + avatar images) — kept as named constants so the
// two policies below can't drift apart on which domains Clerk actually needs.
const CLERK_SCRIPT = "https://*.clerk.accounts.dev https://*.clerk.com https://challenges.cloudflare.com";
const CLERK_CONNECT = "https://*.clerk.accounts.dev https://*.clerk.com https://api.clerk.com";
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
