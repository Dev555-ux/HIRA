import type { MetadataRoute } from "next";

const SITE_URL = "https://hira-tau.vercel.app";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // The dashboard is authenticated — nothing behind sign-in is worth
        // indexing, and it isn't public content anyway.
        disallow: [
          "/dashboard",
          "/inbox",
          "/pending",
          "/knowledge-base",
          "/demo",
          "/customers",
          "/leads",
          "/appointments",
          "/calendar",
          "/analytics",
          "/settings",
          "/onboarding",
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
