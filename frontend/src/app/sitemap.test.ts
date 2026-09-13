import { describe, expect, it } from "vitest";
import robots from "@/app/robots";
import sitemap from "@/app/sitemap";

describe("sitemap", () => {
  it("parses LEGAL_LAST_UPDATED into a real date", () => {
    for (const entry of sitemap()) {
      if (entry.lastModified) expect(Number.isNaN(new Date(entry.lastModified).getTime())).toBe(false);
    }
  });

  it("never lists a URL robots.txt disallows", () => {
    const [rule] = [robots().rules].flat();
    const disallow = [rule.disallow ?? []].flat();
    for (const { url } of sitemap()) {
      const path = new URL(url).pathname;
      expect(disallow.some((d) => path.startsWith(d))).toBe(false);
    }
  });
});
