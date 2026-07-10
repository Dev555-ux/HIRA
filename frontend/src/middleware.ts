import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { authEnabled } from "@/lib/config";

// Default-deny: only "/", "/sign-in", and "/sign-up" are public. Everything
// else (the whole (dashboard) and (onboarding) route groups) requires a
// session — listed explicitly here rather than as an allowlist of protected
// paths so a new route added later is protected by default instead of
// silently public until someone remembers to add it to a list.
const isPublicRoute = createRouteMatcher(["/", "/sign-in(.*)", "/sign-up(.*)"]);

// Real Clerk middleware when configured; a pass-through in dev/mock mode.
// The config guard (lib/config) prevents mock mode in production.
export default authEnabled
  ? clerkMiddleware(async (auth, req) => {
      if (!isPublicRoute(req)) {
        await auth.protect();
      }
    })
  : () => NextResponse.next();

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)"],
};
