import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { type NextRequest, NextResponse } from "next/server";
import { authEnabled } from "@/lib/config";

// Default-deny: only "/", "/sign-in", "/sign-up", the legal pages Google's
// OAuth reviewers must be able to read without a session, and the generated
// Open Graph image (fetched unauthenticated by Googlebot/crawlers/link
// unfurlers — it has no file extension, so unlike /robots.txt or
// /sitemap.xml it isn't already excluded by this middleware's matcher) are
// public. Everything else (the whole (dashboard) and (onboarding) route
// groups) requires a session — listed explicitly here rather than as an
// allowlist of protected paths so a new route added later is protected by
// default instead of silently public until someone remembers to add it to a
// list.
const isPublicRoute = createRouteMatcher([
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/privacy",
  "/terms",
  "/data-deletion",
  "/contact",
  "/company",
  "/opengraph-image",
]);

// Signed-in visitors (and everyone in mock/dev mode) skip the marketing
// homepage for the dashboard. This lives here rather than in app/page.tsx so
// the homepage has no request-time API calls and is prerendered statically —
// a dynamic page gets its <title>/description/canonical streamed into <body>
// instead of <head>, and is never CDN-cached.
const toDashboard = (req: NextRequest) => NextResponse.redirect(new URL("/dashboard", req.url));

// Real Clerk middleware when configured; a pass-through in dev/mock mode.
// The config guard (lib/config) prevents mock mode in production.
export default authEnabled
  ? clerkMiddleware(async (auth, req) => {
      if (req.nextUrl.pathname === "/") {
        const { userId } = await auth();
        if (userId) return toDashboard(req);
      }
      if (!isPublicRoute(req)) {
        await auth.protect();
      }
    })
  : (req: NextRequest) => (req.nextUrl.pathname === "/" ? toDashboard(req) : NextResponse.next());

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)"],
};
