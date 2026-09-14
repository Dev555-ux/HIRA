import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/legal";

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
          "/dashboard-v2",
          "/inbox",
          "/pending",
          "/escalations",
          "/knowledge-base",
          "/demo",
          "/customers",
          "/leads",
          "/appointments",
          "/calendar",
          "/analytics",
          "/settings",
          "/connect-whatsapp",
          "/onboarding",
          "/ops",
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
