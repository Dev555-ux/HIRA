import { afterEach, describe, expect, it, vi } from "vitest";

// The CSP is assembled from env vars at module load (same reason
// src/lib/config.test.ts reloads the module per case), so each case needs a
// fresh import with the flag stubbed first.
async function cspWithEmbeddedSignup(enabled: boolean): Promise<string> {
  vi.resetModules();
  vi.stubEnv("NEXT_PUBLIC_ENABLE_EMBEDDED_SIGNUP", enabled ? "true" : "false");
  const { default: config } = await import("../../next.config");
  const headers = await config.headers!();
  const csp = headers[0].headers.find((h) => h.key === "Content-Security-Policy");
  return csp!.value;
}

describe("Content-Security-Policy and Meta Embedded Signup", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  // Sprint 83 shipped the Embedded Signup flow but not the CSP origins it
  // needs; production refused connect.facebook.net with a script-src-elem
  // violation and the flow surfaced it as "couldn't reach Facebook".
  it("allows Meta's SDK and popup origins when Embedded Signup is on", async () => {
    const csp = await cspWithEmbeddedSignup(true);
    const scriptSrc = csp.split("; ").find((d) => d.startsWith("script-src "))!;
    const frameSrc = csp.split("; ").find((d) => d.startsWith("frame-src "))!;

    expect(scriptSrc).toContain("https://connect.facebook.net");
    expect(frameSrc).toContain("https://staticxx.facebook.com");
    // The two origins lib/facebook-sdk.ts trusts for the popup's postMessage
    // must also be loadable, or the result never reaches the page.
    expect(frameSrc).toContain("https://www.facebook.com");
    expect(frameSrc).toContain("https://web.facebook.com");
  });

  it("keeps Meta out of the policy when Embedded Signup is off", async () => {
    const csp = await cspWithEmbeddedSignup(false);
    expect(csp).not.toContain("facebook");
  });
});
