import { afterEach, describe, expect, it, vi } from "vitest";

// Sprint 77: clerkKeyLooksLikeTestKey is derived from
// process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY at module load, so each
// case needs a fresh module instance with that env var stubbed first.
async function loadConfigWith(publishableKey: string | undefined) {
  vi.resetModules();
  if (publishableKey === undefined) {
    vi.unstubAllEnvs();
  } else {
    vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", publishableKey);
  }
  return import("./config");
}

describe("clerkKeyLooksLikeTestKey", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("is true for a pk_test_ key", async () => {
    const config = await loadConfigWith("pk_test_abc123");
    expect(config.clerkKeyLooksLikeTestKey).toBe(true);
  });

  it("is false for a pk_live_ key", async () => {
    const config = await loadConfigWith("pk_live_abc123");
    expect(config.clerkKeyLooksLikeTestKey).toBe(false);
  });

  it("is false when no key is configured", async () => {
    const config = await loadConfigWith("");
    expect(config.clerkKeyLooksLikeTestKey).toBe(false);
  });
});
