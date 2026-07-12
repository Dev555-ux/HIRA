import type { MetadataRoute } from "next";

const SITE_URL = "https://hira-tau.vercel.app";

// Only the public marketing page belongs in a sitemap — everything else in
// this app sits behind authentication.
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: SITE_URL,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 1,
    },
  ];
}
