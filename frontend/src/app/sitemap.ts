import type { MetadataRoute } from "next";
import { LEGAL_LAST_UPDATED, SITE_URL } from "@/lib/legal";

// Only public pages belong in a sitemap — everything else in this app sits
// behind authentication. lastModified is only given where a real date exists:
// Google ignores lastmod site-wide once it proves unreliable, which the old
// `new Date()` on every request would have. changefreq/priority are omitted
// because Google ignores both.
export default function sitemap(): MetadataRoute.Sitemap {
  const legalUpdated = new Date(LEGAL_LAST_UPDATED);
  return [
    { url: SITE_URL },
    { url: `${SITE_URL}/privacy`, lastModified: legalUpdated },
    { url: `${SITE_URL}/terms`, lastModified: legalUpdated },
    { url: `${SITE_URL}/data-deletion`, lastModified: legalUpdated },
    { url: `${SITE_URL}/contact` },
    { url: `${SITE_URL}/company` },
  ];
}
