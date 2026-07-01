import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { authEnabled } from "@/lib/config";

// Real Clerk middleware when configured; a pass-through in dev/mock mode.
// The config guard (lib/config) prevents mock mode in production.
export default authEnabled ? clerkMiddleware() : () => NextResponse.next();

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)"],
};
