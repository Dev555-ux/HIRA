import type { Metadata } from "next";
import { PRODUCT_NAME } from "@/lib/legal";

// Next.js shallow-merges metadata per top-level key: a page that sets
// `openGraph` replaces the root layout's entirely rather than extending it.
// Building the whole set per page is what keeps og:url and og:site_name from
// silently disappearing on any page that customises one Open Graph field.
export function pageMetadata({
  title,
  description,
  path,
}: {
  title: string;
  description: string;
  path: string;
}): Metadata {
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: { title, description, url: path, siteName: PRODUCT_NAME, type: "website" },
    // The image comes from app/opengraph-image.tsx for both cards.
    twitter: { card: "summary_large_image", title, description },
  };
}
