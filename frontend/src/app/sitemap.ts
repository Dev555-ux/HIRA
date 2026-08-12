import type { MetadataRoute } from "next";

const SITE_URL = "https://stoneveil.in";

// Only public pages belong in a sitemap — everything else in this app sits
// behind authentication. The legal/company pages ((legal) route group) are
// public and worth indexing, unlike the dashboard.
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: SITE_URL,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 1,
    },
    ...["/privacy", "/terms", "/data-deletion", "/contact", "/company"].map((path) => ({
      url: `${SITE_URL}${path}`,
      lastModified: new Date(),
      changeFrequency: "yearly" as const,
      priority: 0.3,
    })),
  ];
}
